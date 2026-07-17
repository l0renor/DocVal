"""Tests for the new dynamic-config + validate-mode API contract (issue #15).

All tests go through the FastAPI HTTP boundary with a faked model client —
the same convention as test_api.py. Validate mode returns one result per
sub-document ({ status, submission_type, results }); scan and targeted mode
return a single { ... result }.
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


def test_no_config_routes_to_scan_mode():
    # Omitting config triggers scan mode (issue #16) — not a 422.
    # Scan mode requires a FakeModelClient with scan_fields; the default
    # _accepted_fake has none, so just verify the request completes (202).
    from docval.schemas import FieldResult, Legibility
    scan_model = FakeModelClient(
        classification=Classification(document_type="personalausweis"),
        scan_fields=[FieldResult(name="nachname", value="X", legibility=Legibility.LEGIBLE)],
    )
    resp = _upload(TestClient(create_app(model_client=scan_model)))
    assert resp.status_code == 202


class _UnimplementedModesClient(FakeModelClient):
    """Mimics AzureModelClient before scan/targeted are implemented."""

    def scan(self, images):
        raise NotImplementedError("scan is not yet implemented")

    def extract_targeted(self, images, required_fields):
        raise NotImplementedError("extract_targeted is not yet implemented")


def test_scan_mode_returns_501_when_client_does_not_support_it():
    """A config-less upload against a client without scan must not be a 500."""
    client = TestClient(create_app(model_client=_UnimplementedModesClient(
        classification=Classification(document_type="personalausweis"),
    )))
    resp = _upload(client)  # no config -> scan mode
    assert resp.status_code == 501
    assert "scan" in resp.json()["detail"]


def test_targeted_mode_returns_501_when_client_does_not_support_it():
    client = TestClient(create_app(model_client=_UnimplementedModesClient(
        classification=Classification(document_type="personalausweis"),
    )))
    resp = client.post(
        "/documents",
        files=[("files", ("id.jpg", b"img", "image/jpeg"))],
        data={"required_fields": json.dumps([{"name": "nachname"}])},
    )
    assert resp.status_code == 501
    assert "extract_targeted" in resp.json()["detail"]


def test_dokument_with_inline_config_returns_new_job_shape():
    """POST with config + 1 file -> job has {status, submission_type, results}."""
    job = _run(_client(), config=PERSONALAUSWEIS_CONFIG)

    assert job["status"] == "done"
    assert job["submission_type"] == "dokument"
    (result,) = job["results"]
    assert result["validation_status"] == "accepted"
    assert result["classification"]["document_type"] == "personalausweis"


def test_bundled_pdf_with_inline_config_reports_every_sub_document():
    """A dokument upload that segments into two sub-documents must not drop the second."""
    import pymupdf

    from docval.model_client import ScriptedModelClient

    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page(width=200, height=200)
    pdf = doc.tobytes()
    doc.close()

    two_type_config = {
        "document_types": [
            {"id": "personalausweis", "description": "ID card"},
            {"id": "mietvertrag", "description": "Lease contract"},
        ]
    }
    accepted = ExtractionOutcome(validation_status=ValidationStatus.ACCEPTED)
    model = ScriptedModelClient(
        page_types=["personalausweis", "mietvertrag"],
        extractions={"personalausweis": accepted, "mietvertrag": accepted},
    )

    job = _run(
        _client(model),
        files=[("files", ("bundle.pdf", pdf, "application/pdf"))],
        config=two_type_config,
    )

    types = [r["classification"]["document_type"] for r in job["results"]]
    assert types == ["personalausweis", "mietvertrag"]
