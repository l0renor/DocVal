"""Tests for antrag bundle mode (issue #18).

Antrag mode: POST /documents with submission_type=antrag + a full config.
Multiple files are accepted; each is segmented and all sub-documents are
unioned in file order. A cross-document analysis seam (analyze_antrag) is
faked with canned output. Completeness and bundle verdict are deterministic.

Response shape:
  { status, submission_type, results, antrag_metadata:
      { cross_document_findings, missing_required_documents, summary, antrag_status } }

All tests go through the FastAPI HTTP boundary with model client faked.
"""

import json

import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.model_client import FakeModelClient
from docval.schemas import (
    AntragsResult,
    Classification,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)


_BASE_CONFIG = {
    "document_types": [
        {"id": "personalausweis", "description": "Personalausweis", "required": True},
        {"id": "mietvertrag", "description": "Mietvertrag", "required": False},
    ]
}

_REQUIRED_ONLY_CONFIG = {
    "document_types": [
        {"id": "personalausweis", "description": "Personalausweis", "required": True},
    ]
}


def _accepted_outcome():
    return ExtractionOutcome(
        validation_status=ValidationStatus.ACCEPTED,
        fields=[FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE)],
    )


def _invalid_type_fake(antrag_result=None):
    """Fake that classifies as an unknown type (→ invalid_type sub-doc)."""
    return FakeModelClient(
        classification=Classification(document_type="unbekannt"),
        antrag_result=antrag_result or AntragsResult(cross_document_findings=[], summary="OK"),
    )


def _accepted_fake(antrag_result=None):
    return FakeModelClient(
        classification=Classification(document_type="personalausweis"),
        extraction=_accepted_outcome(),
        antrag_result=antrag_result or AntragsResult(cross_document_findings=[], summary="Alles in Ordnung."),
    )


def _upload_antrag(client, config=None, files=None, required_fields=None):
    data = {"submission_type": "antrag"}
    if config is not None:
        data["config"] = json.dumps(config)
    if required_fields is not None:
        data["required_fields"] = json.dumps(required_fields)
    upload_files = files or [("files", ("id.jpg", b"fake-bytes", "image/jpeg"))]
    return client.post("/documents", files=upload_files, data=data)


def _client(model=None, config=None):
    return TestClient(create_app(model_client=model or _accepted_fake(), config=config))


# ---------------------------------------------------------------------------
# #1 Tracer: shape
# ---------------------------------------------------------------------------

def test_antrag_returns_results_and_antrag_metadata():
    client = _client(_accepted_fake(), config=None)
    resp = _upload_antrag(client, config=_REQUIRED_ONLY_CONFIG)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()

    assert job["status"] == "done"
    assert job["submission_type"] == "antrag"
    assert "results" in job
    meta = job["antrag_metadata"]
    assert "cross_document_findings" in meta
    assert "missing_required_documents" in meta
    assert "summary" in meta
    assert "antrag_status" in meta


# ---------------------------------------------------------------------------
# #2 antrag without config → 422
# ---------------------------------------------------------------------------

def test_antrag_without_config_returns_422():
    client = _client()
    resp = _upload_antrag(client, config=None)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# #3 antrag with required_fields instead of config → 422
# ---------------------------------------------------------------------------

def test_antrag_with_required_fields_returns_422():
    client = _client()
    resp = _upload_antrag(client, required_fields=[{"name": "nachname"}])
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# #4 missing required doc listed in missing_required_documents + German line
# ---------------------------------------------------------------------------

def test_antrag_missing_required_doc_is_in_missing_list_only():
    # Config requires personalausweis; model classifies as something else → missing.
    # The missing doc must appear in missing_required_documents but must NOT be
    # duplicated as a synthetic string in cross_document_findings.
    config = {
        "document_types": [
            {"id": "personalausweis", "description": "Personalausweis", "required": True},
            {"id": "mietvertrag", "description": "Meitvertrag", "required": False},
        ]
    }
    model = FakeModelClient(
        classification=Classification(document_type="mietvertrag"),
        extraction=_accepted_outcome(),
        antrag_result=AntragsResult(cross_document_findings=[], summary="Zusammenfassung."),
    )
    client = _client(model)
    resp = _upload_antrag(client, config=config)
    job = client.get(f"/jobs/{resp.json()['job_id']}").json()
    meta = job["antrag_metadata"]

    assert "personalausweis" in meta["missing_required_documents"]
    # cross_document_findings must contain only the model's own findings, not
    # synthetic "Pflichtdokument fehlt" strings that belong in missing_required_documents.
    assert meta["cross_document_findings"] == []


# ---------------------------------------------------------------------------
# #5 accepted: all accepted + no findings + no missing required
# ---------------------------------------------------------------------------

def test_antrag_accepted_when_all_ok():
    config = _REQUIRED_ONLY_CONFIG
    model = _accepted_fake(antrag_result=AntragsResult(cross_document_findings=[], summary="OK"))
    client = _client(model)
    resp = _upload_antrag(client, config=config)
    job = client.get(f"/jobs/{resp.json()['job_id']}").json()
    assert job["antrag_metadata"]["antrag_status"] == "accepted"


# ---------------------------------------------------------------------------
# #6 incomplete: cross-doc findings from faked analyze_antrag
# ---------------------------------------------------------------------------

def test_antrag_incomplete_when_cross_doc_findings():
    # Cross-doc analysis requires two or more sub-documents; use two files.
    config = _REQUIRED_ONLY_CONFIG
    model = _accepted_fake(
        antrag_result=AntragsResult(
            cross_document_findings=["Adresse im Personalausweis stimmt nicht mit Mietvertrag überein."],
            summary="Diskrepanz gefunden.",
        )
    )
    client = _client(model)
    resp = _upload_antrag(
        client,
        config=config,
        files=[
            ("files", ("a.jpg", b"img1", "image/jpeg")),
            ("files", ("b.jpg", b"img2", "image/jpeg")),
        ],
    )
    job = client.get(f"/jobs/{resp.json()['job_id']}").json()
    meta = job["antrag_metadata"]
    assert meta["antrag_status"] == "incomplete"
    assert len(meta["cross_document_findings"]) >= 1


# ---------------------------------------------------------------------------
# #7 incomplete: invalid_type sub-doc downgrades bundle
# ---------------------------------------------------------------------------

def test_antrag_incomplete_when_sub_doc_invalid_type():
    config = _REQUIRED_ONLY_CONFIG
    # Model classifies as unknown type → invalid_type sub-result
    model = _invalid_type_fake()
    client = _client(model)
    resp = _upload_antrag(client, config=config)
    job = client.get(f"/jobs/{resp.json()['job_id']}").json()
    # invalid_type sub-doc + missing required → incomplete bundle
    assert job["antrag_metadata"]["antrag_status"] == "incomplete"
    # invalid_type must never appear as antrag_status itself
    assert job["antrag_metadata"]["antrag_status"] != "invalid_type"


# ---------------------------------------------------------------------------
# #8 degenerate: missing required → incomplete, empty findings from model
# ---------------------------------------------------------------------------

class _AnalyzeCallCounter(FakeModelClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.analyze_calls = 0

    def analyze_antrag(self, results, images_per_result):
        self.analyze_calls += 1
        return super().analyze_antrag(results, images_per_result)


def test_analyze_antrag_not_called_for_single_sub_document():
    # Cross-document analysis needs at least two docs to compare; calling it for
    # a single doc wastes an Azure round-trip and can produce hallucinated findings.
    model = _AnalyzeCallCounter(
        classification=Classification(document_type="personalausweis"),
        extraction=_accepted_outcome(),
        antrag_result=AntragsResult(cross_document_findings=[], summary="OK"),
    )
    client = _client(model)
    resp = _upload_antrag(client, config=_REQUIRED_ONLY_CONFIG)
    assert resp.status_code == 202
    client.get(f"/jobs/{resp.json()['job_id']}")

    assert model.analyze_calls == 0


def test_analyze_antrag_called_when_multiple_sub_documents():
    model = _AnalyzeCallCounter(
        classification=Classification(document_type="personalausweis"),
        extraction=_accepted_outcome(),
        antrag_result=AntragsResult(cross_document_findings=[], summary="OK"),
    )
    client = _client(model)
    resp = _upload_antrag(
        client,
        config=_REQUIRED_ONLY_CONFIG,
        files=[
            ("files", ("a.jpg", b"img1", "image/jpeg")),
            ("files", ("b.jpg", b"img2", "image/jpeg")),
        ],
    )
    assert resp.status_code == 202
    client.get(f"/jobs/{resp.json()['job_id']}")

    assert model.analyze_calls == 1


def test_antrag_degenerate_missing_required_is_incomplete():
    # Config with a required doc that will never appear (no files classify as it)
    config = {
        "document_types": [
            {"id": "personalausweis", "description": "Personalausweis", "required": True},
        ]
    }
    model = FakeModelClient(
        classification=Classification(document_type="unbekannt"),
        antrag_result=AntragsResult(cross_document_findings=[], summary=""),
    )
    client = _client(model)
    resp = _upload_antrag(client, config=config)
    job = client.get(f"/jobs/{resp.json()['job_id']}").json()
    assert job["antrag_metadata"]["antrag_status"] == "incomplete"
    assert "personalausweis" in job["antrag_metadata"]["missing_required_documents"]
