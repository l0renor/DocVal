"""Tests for the new dynamic-config + validate-mode API contract (issue #15).

All tests go through the FastAPI HTTP boundary with a faked model client —
the same convention as test_api.py. The response shape for a dokument job is
{ status, submission_type, result } (not results[]).
"""

import json

import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.model_client import FakeModelClient
from docval.schemas import (
    Classification,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERSONALAUSWEIS_CONFIG = {
    "document_types": [
        {
            "id": "personalausweis",
            "description": "A German national identity card.",
            "expected_fields": [
                {"name": "nachname", "description": "Surname", "type_hint": "string"},
            ],
            "criteria": "Must be a valid German ID.",
        }
    ]
}


def _accepted_fake():
    return FakeModelClient(
        classification=Classification(document_type="personalausweis"),
        extraction=ExtractionOutcome(
            validation_status=ValidationStatus.ACCEPTED,
            fields=[FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE)],
            deficiencies=[],
        ),
    )


def _client(model=None):
    return TestClient(create_app(model_client=model or _accepted_fake()))


def _upload(client, *, files=None, config=None, submission_type=None):
    """POST /documents with the new multipart shape."""
    if files is None:
        files = [("files", ("id.jpg", b"fake-image-bytes", "image/jpeg"))]
    data = {}
    if config is not None:
        data["config"] = json.dumps(config)
    if submission_type is not None:
        data["submission_type"] = submission_type
    return client.post("/documents", files=files, data=data)


def _run(client, **kwargs):
    """Upload and return the completed job body."""
    resp = _upload(client, **kwargs)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    return client.get(f"/jobs/{job_id}").json()


# ---------------------------------------------------------------------------
# Tracer bullet — #1
# ---------------------------------------------------------------------------

def test_malformed_json_config_returns_422():
    resp = _client().post(
        "/documents",
        files=[("files", ("id.jpg", b"img", "image/jpeg"))],
        data={"config": "{not valid json"},
    )
    assert resp.status_code == 422


def test_schema_invalid_config_returns_422():
    bad_config = {"document_types": "not-a-list"}
    resp = _upload(_client(), config=bad_config)
    assert resp.status_code == 422


def test_dokument_with_more_than_one_file_returns_422():
    resp = _client().post(
        "/documents",
        files=[
            ("files", ("a.jpg", b"img", "image/jpeg")),
            ("files", ("b.jpg", b"img", "image/jpeg")),
        ],
        data={"config": json.dumps(PERSONALAUSWEIS_CONFIG)},
    )
    assert resp.status_code == 422


def test_empty_files_returns_422():
    resp = _client().post("/documents", data={"config": json.dumps(PERSONALAUSWEIS_CONFIG)})
    assert resp.status_code == 422


def test_unknown_submission_type_returns_422():
    resp = _upload(_client(), config=PERSONALAUSWEIS_CONFIG, submission_type="foobar")
    assert resp.status_code == 422


def test_no_config_returns_422_until_scan_mode_implemented():
    # Scan mode is issue #16. Until then, omitting config must not crash the
    # server — it returns a clear 422 explaining scan mode is not yet available.
    resp = _upload(_client())
    assert resp.status_code == 422
    assert "scan" in resp.json()["detail"].lower()


def test_dokument_with_inline_config_returns_new_job_shape():
    """POST with config + 1 file -> job has {status, submission_type, result}."""
    job = _run(_client(), config=PERSONALAUSWEIS_CONFIG)

    assert job["status"] == "done"
    assert job["submission_type"] == "dokument"
    result = job["result"]
    assert result["validation_status"] == "accepted"
    assert result["classification"]["document_type"] == "personalausweis"
