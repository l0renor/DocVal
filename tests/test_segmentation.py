"""HTTP-seam tests for Slice 4: multi-document PDF segmentation.

A bundled PDF (several documents scanned into one file) is split at the
boundaries where the classified document type changes, and each sub-document
runs the classify -> extract -> validate pipeline independently. The model is
faked with per-page canned types (`ScriptedModelClient`).
"""

import pymupdf
import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.config import Config, DocumentTypeConfig, ExpectedField
from docval.model_client import ScriptedModelClient
from docval.schemas import (
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)


def make_pdf(num_pages: int) -> bytes:
    doc = pymupdf.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def multi_type_config():
    def _type(type_id):
        return DocumentTypeConfig(
            id=type_id,
            description=f"A {type_id}.",
            expected_fields=[ExpectedField(name="feld", description="a field")],
            criteria="valid",
        )

    return Config(document_types=[_type("personalausweis"), _type("mietvertrag"), _type("sprachzertifikat")])


def _accepted(type_id):
    return ExtractionOutcome(
        validation_status=ValidationStatus.ACCEPTED,
        fields=[FieldResult(name="feld", value=type_id, legibility=Legibility.LEGIBLE)],
    )


def _extractions():
    return {t: _accepted(t) for t in ("personalausweis", "mietvertrag", "sprachzertifikat")}


def _submit(config, model, pdf):
    client = TestClient(create_app(config=config, model_client=model))
    job_id = client.post("/documents", files=[("files", ("bundle.pdf", pdf, "application/pdf"))]).json()["job_id"]
    return client.get(f"/jobs/{job_id}").json()["results"]


def test_bundled_pdf_is_split_into_one_result_per_document(multi_type_config):
    # Three single-page documents scanned into one PDF.
    model = ScriptedModelClient(
        page_types=["personalausweis", "mietvertrag", "sprachzertifikat"],
        extractions=_extractions(),
    )
    results = _submit(multi_type_config, model, make_pdf(3))

    assert len(results) == 3
    assert [r["classification"]["document_type"] for r in results] == [
        "personalausweis",
        "mietvertrag",
        "sprachzertifikat",
    ]
    # Each sub-document ran extraction independently.
    assert all(r["validation_status"] == "accepted" for r in results)
    assert [r["extracted_data"][0]["value"] for r in results] == [
        "personalausweis",
        "mietvertrag",
        "sprachzertifikat",
    ]


def test_consecutive_same_type_pages_form_one_document(multi_type_config):
    # A two-page lease followed by a one-page certificate -> two documents.
    model = ScriptedModelClient(
        page_types=["mietvertrag", "mietvertrag", "sprachzertifikat"],
        extractions=_extractions(),
    )
    results = _submit(multi_type_config, model, make_pdf(3))

    assert [r["classification"]["document_type"] for r in results] == ["mietvertrag", "sprachzertifikat"]


def test_single_document_pdf_yields_exactly_one_result(multi_type_config):
    model = ScriptedModelClient(
        page_types=["personalausweis", "personalausweis"],
        extractions=_extractions(),
    )
    results = _submit(multi_type_config, model, make_pdf(2))

    assert len(results) == 1
    assert results[0]["classification"]["document_type"] == "personalausweis"


def test_wrong_type_sub_document_reports_invalid_type_without_blocking_others(multi_type_config):
    # The middle page is junk; it must be reported, not filtered out.
    model = ScriptedModelClient(
        page_types=["personalausweis", "katzenfoto", "sprachzertifikat"],
        extractions=_extractions(),  # no "katzenfoto" entry -> extraction would raise if attempted
    )
    results = _submit(multi_type_config, model, make_pdf(3))

    statuses = [r["validation_status"] for r in results]
    assert statuses == ["accepted", "invalid_type", "accepted"]
    # Stufe 2 was skipped for the wrong type (no extracted data).
    assert results[1]["extracted_data"] == []
