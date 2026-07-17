"""The event loop must stay free while a document is being processed.

Model calls are synchronous (Azure SDK); if they run directly inside the async
endpoint they block the whole event loop and all concurrent requests serialize.
The test drives two requests through the ASGI app on a single event loop with a
deliberately slow model: overlapping execution finishes in roughly one model
delay, serialized execution takes two.
"""

import asyncio
import json
import time

import httpx

from docval.app import create_app
from docval.model_client import FakeModelClient
from docval.schemas import Classification, ExtractionOutcome, ValidationStatus

MODEL_DELAY = 0.35

CONFIG = {"document_types": [{"id": "personalausweis", "description": "ID card"}]}


class _SlowModelClient(FakeModelClient):
    def extract_and_validate(self, images, doc_type):
        time.sleep(MODEL_DELAY)  # sync sleep, like a blocking SDK call
        return super().extract_and_validate(images, doc_type)


def test_concurrent_submissions_do_not_serialize_on_the_event_loop():
    model = _SlowModelClient(
        classification=Classification(document_type="personalausweis"),
        extraction=ExtractionOutcome(validation_status=ValidationStatus.ACCEPTED),
    )
    app = create_app(model_client=model)

    async def submit(client):
        resp = await client.post(
            "/documents",
            files=[("files", ("id.jpg", b"img", "image/jpeg"))],
            data={"config": json.dumps(CONFIG)},
        )
        assert resp.status_code == 202, resp.text

    async def main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.perf_counter()
            await asyncio.gather(submit(client), submit(client))
            return time.perf_counter() - start

    elapsed = asyncio.run(main())
    # Overlapping: ~1x MODEL_DELAY. Serialized: ~2x. Allow generous headroom.
    assert elapsed < MODEL_DELAY * 1.7, (
        f"two concurrent requests took {elapsed:.2f}s — the model call is blocking the event loop"
    )
