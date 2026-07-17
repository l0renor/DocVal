"""Tests for targeted mode (issue #17).

Targeted mode: POST /documents with a required_fields JSON form field.
The model extracts only the requested fields — no classification step.
Response shape: { status, submission_type, result } where result has
validation_status + deficiencies + extracted_data + confidence, but NO classification.
All tests go through the FastAPI HTTP boundary with a faked model client.
"""

import json

import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.model_client import FakeModelClient
from docval.schemas import FieldResult, Legibility


def _targeted_fake(fields=None):
    if fields is None:
        fields = [
            FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
            FieldResult(name="vorname", value="Erika", legibility=Legibility.LEGIBLE),
        ]
    return FakeModelClient(targeted_fields=fields)


def _upload_targeted(client, required_fields):
    resp = client.post(
        "/documents",
        files=[("files", ("id.jpg", b"fake-image-bytes", "image/jpeg"))],
        data={"required_fields": json.dumps(required_fields)},
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    return client.get(f"/jobs/{job_id}").json()


def _client(model=None):
    return TestClient(create_app(model_client=model or _targeted_fake()))


# ---------------------------------------------------------------------------
# #1 Tracer
# ---------------------------------------------------------------------------

def test_targeted_returns_verdict_and_extracted_data():
    required = [{"name": "nachname"}, {"name": "vorname"}]
    job = _upload_targeted(_client(), required)

    assert job["status"] == "done"
    result = job["result"]
    assert "validation_status" in result
    assert "extracted_data" in result
    assert "confidence" in result
    assert "deficiencies" in result


def test_targeted_result_has_no_classification():
    required = [{"name": "nachname"}]
    job = _upload_targeted(_client(), required)
    assert "classification" not in job["result"]


# ---------------------------------------------------------------------------
# #2 accepted when all requested fields present and legible
# ---------------------------------------------------------------------------

def test_targeted_accepted_when_all_fields_legible():
    fields = [
        FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
        FieldResult(name="vorname", value="Erika", legibility=Legibility.LEGIBLE),
    ]
    required = [{"name": "nachname"}, {"name": "vorname"}]
    job = _upload_targeted(_client(_targeted_fake(fields)), required)
    assert job["result"]["validation_status"] == "accepted"
    assert job["result"]["deficiencies"] == []


# ---------------------------------------------------------------------------
# #3 incomplete with deficiency when a field is missing or illegible
# ---------------------------------------------------------------------------

def test_targeted_incomplete_when_field_missing():
    fields = [
        FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
        # vorname not returned by model
    ]
    required = [{"name": "nachname"}, {"name": "vorname"}]
    job = _upload_targeted(_client(_targeted_fake(fields)), required)
    result = job["result"]
    assert result["validation_status"] == "incomplete"
    deficiency_fields = [d["field"] for d in result["deficiencies"]]
    assert "vorname" in deficiency_fields


def test_targeted_incomplete_when_field_illegible():
    fields = [
        FieldResult(name="nachname", value=None, legibility=Legibility.ILLEGIBLE),
    ]
    required = [{"name": "nachname"}]
    job = _upload_targeted(_client(_targeted_fake(fields)), required)
    result = job["result"]
    assert result["validation_status"] == "incomplete"
    assert result["deficiencies"][0]["field"] == "nachname"


# ---------------------------------------------------------------------------
# #4 extracted_data filtered to only requested fields
# ---------------------------------------------------------------------------

def test_targeted_extracted_data_filtered_to_requested_fields():
    fields = [
        FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
        FieldResult(name="vorname", value="Erika", legibility=Legibility.LEGIBLE),
        FieldResult(name="geburtsdatum", value="1990-01-01", legibility=Legibility.LEGIBLE),
    ]
    required = [{"name": "nachname"}]  # only request one of three
    job = _upload_targeted(_client(_targeted_fake(fields)), required)
    names = [f["name"] for f in job["result"]["extracted_data"]]
    assert names == ["nachname"]
    assert "vorname" not in names
    assert "geburtsdatum" not in names


# ---------------------------------------------------------------------------
# #5 conflict: config + required_fields → 422
# ---------------------------------------------------------------------------

def test_both_config_and_required_fields_returns_422():
    client = _client()
    resp = client.post(
        "/documents",
        files=[("files", ("id.jpg", b"fake-image-bytes", "image/jpeg"))],
        data={
            "config": json.dumps({"document_types": []}),
            "required_fields": json.dumps([{"name": "nachname"}]),
        },
    )
    assert resp.status_code == 422
