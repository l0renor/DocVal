import pytest
from fastapi.testclient import TestClient

import pymupdf

from docval.app import create_app
from docval.config import Config, DocumentTypeConfig, ExpectedField
from docval.ingest import IngestError, IngestSettings, render_to_images
from docval.schemas import (
    Classification,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)


def make_pdf(num_pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    data = doc.tobytes()
    doc.close()
    return data


# ---- render_to_images (pure) ----

def test_image_upload_is_a_single_page():
    assert render_to_images("scan.png", "image/png", b"img-bytes") == [b"img-bytes"]


def test_pdf_renders_one_image_per_page():
    pages = render_to_images("doc.pdf", "application/pdf", make_pdf(3))
    assert len(pages) == 3
    assert all(isinstance(p, bytes) and p for p in pages)


def test_unsupported_type_raises():
    with pytest.raises(IngestError):
        render_to_images("notes.txt", "text/plain", b"hello")


def test_too_many_pages_raises():
    with pytest.raises(IngestError):
        render_to_images("doc.pdf", "application/pdf", make_pdf(3), IngestSettings(max_pages=2))


def test_oversize_file_raises():
    with pytest.raises(IngestError):
        render_to_images("scan.png", "image/png", b"x" * 100, IngestSettings(max_file_bytes=10))


# ---- HTTP seam ----

class _RecordingModel:
    def __init__(self):
        self.classify_page_counts = []
        self.extract_page_counts = []

    def classify(self, images, config):
        self.classify_page_counts.append(len(images))
        return Classification(document_type="personalausweis")

    def extract_and_validate(self, images, doc_type):
        self.extract_page_counts.append(len(images))
        return ExtractionOutcome(
            validation_status=ValidationStatus.ACCEPTED,
            fields=[FieldResult(name="nachname", value="X", legibility=Legibility.LEGIBLE)],
        )


def _config():
    return Config(
        document_types=[
            DocumentTypeConfig(
                id="personalausweis",
                description="A German ID.",
                expected_fields=[ExpectedField(name="nachname", description="Surname")],
                criteria="valid",
            )
        ]
    )


def test_pdf_classify_uses_page1_extract_uses_all_pages():
    model = _RecordingModel()
    client = TestClient(create_app(config=_config(), model_client=model))

    resp = client.post("/documents", files={"file": ("doc.pdf", make_pdf(3), "application/pdf")})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    result = client.get(f"/jobs/{job_id}").json()["result"]

    assert result["validation_status"] == "accepted"
    assert model.classify_page_counts == [1]
    assert model.extract_page_counts == [3]


def test_unsupported_upload_returns_400():
    client = TestClient(create_app(config=_config(), model_client=_RecordingModel()))
    resp = client.post("/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert resp.status_code == 400
