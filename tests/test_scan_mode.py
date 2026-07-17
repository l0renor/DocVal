"""Tests for scan mode (issue #16).

Scan mode: POST /documents with no config field.
The model infers the document type and extracts all available fields.
Response shape: { status, submission_type, result } where result has
classification + extracted_data + confidence — no validation_status, no deficiencies.
All tests go through the FastAPI HTTP boundary with a faked model client.
"""

import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.model_client import FakeModelClient
from docval.schemas import Classification, FieldResult, Legibility


def _scan_fake(document_type="personalausweis", fields=None):
    if fields is None:
        fields = [
            FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
            FieldResult(name="vorname", value="Erika", legibility=Legibility.LEGIBLE),
        ]
    return FakeModelClient(
        classification=Classification(document_type=document_type),
        scan_fields=fields,
    )


def _scan_client(model=None):
    return TestClient(create_app(model_client=model or _scan_fake()))


def _upload_no_config(client):
    resp = client.post(
        "/documents",
        files=[("files", ("id.jpg", b"fake-image-bytes", "image/jpeg"))],
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    return client.get(f"/jobs/{job_id}").json()


# ---------------------------------------------------------------------------
# #1 Tracer
# ---------------------------------------------------------------------------

def test_scan_returns_classification_and_extracted_data():
    job = _upload_no_config(_scan_client())

    assert job["status"] == "done"
    result = job["result"]
    assert result["classification"]["document_type"] == "personalausweis"
    assert len(result["extracted_data"]) == 2
    assert result["extracted_data"][0]["name"] == "nachname"
    assert "confidence" in result


def test_scan_result_has_no_validation_status():
    job = _upload_no_config(_scan_client())
    assert "validation_status" not in job["result"]


def test_scan_result_has_no_deficiencies():
    job = _upload_no_config(_scan_client())
    assert "deficiencies" not in job["result"]


def test_scan_confidence_is_aggregated_from_field_legibility():
    # 1 legible (1.0) + 1 illegible (0.0) -> mean 0.5
    fields = [
        FieldResult(name="name", value="X", legibility=Legibility.LEGIBLE),
        FieldResult(name="date", value=None, legibility=Legibility.ILLEGIBLE),
    ]
    job = _upload_no_config(_scan_client(_scan_fake(fields=fields)))
    assert job["result"]["confidence"] == pytest.approx(0.5)


def test_scan_submission_type_is_dokument():
    job = _upload_no_config(_scan_client())
    assert job["submission_type"] == "dokument"
