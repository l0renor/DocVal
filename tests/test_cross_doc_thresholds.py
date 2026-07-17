"""Tests for cross-doc image selection + thresholds (issue #19).

run_antrag forwards a sub-document's page images to analyze_antrag only when
that sub-document's aggregated confidence is below the configured threshold.
An image cap limits total forwarded images; truncation is logged.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.config import parse_config
from docval.model_client import FakeModelClient
from docval.schemas import (
    AntragsResult,
    Classification,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)

# ---------------------------------------------------------------------------
# Recording test double — records images_per_result passed to analyze_antrag
# ---------------------------------------------------------------------------

class RecordingAntragsClient(FakeModelClient):
    """FakeModelClient that records which images were passed to analyze_antrag."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.received_images_per_result: list[list[bytes]] | None = None

    def analyze_antrag(self, results, images_per_result):
        self.received_images_per_result = [list(imgs) for imgs in images_per_result]
        if self._antrag_result is not None:
            return self._antrag_result
        return AntragsResult(cross_document_findings=[], summary="")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FAKE_BYTES = b"fake-page"
_FAKE_BYTES_2 = b"fake-page-2"
_FAKE_BYTES_3 = b"fake-page-3"


def _make_spy(legibility=Legibility.ILLEGIBLE):
    """Spy with classification=personalausweis; legibility controls confidence."""
    fields = (
        []
        if legibility == Legibility.ILLEGIBLE
        else [FieldResult(name="nachname", value="Muster", legibility=legibility)]
    )
    return RecordingAntragsClient(
        classification=Classification(document_type="personalausweis"),
        extraction=ExtractionOutcome(
            validation_status=ValidationStatus.ACCEPTED,
            fields=fields,
        ),
        antrag_result=AntragsResult(cross_document_findings=[], summary=""),
    )


def _two_files():
    """Minimum file list that yields ≥2 sub-documents, so analyze_antrag is called."""
    return [
        ("files", ("a.jpg", _FAKE_BYTES, "image/jpeg")),
        ("files", ("b.jpg", _FAKE_BYTES_2, "image/jpeg")),
    ]


def _upload_antrag(client, config, files=None):
    upload_files = files or _two_files()
    return client.post(
        "/documents",
        files=upload_files,
        data={"submission_type": "antrag", "config": json.dumps(config)},
    )


def _app(spy):
    return TestClient(create_app(model_client=spy))


# ---------------------------------------------------------------------------
# Config seam: threshold and cap round-trip through parse_config
# ---------------------------------------------------------------------------

def test_config_confidence_threshold_parsed():
    config = parse_config({
        "document_types": [{"id": "x", "description": "X"}],
        "confidence_threshold": 0.6,
    })
    assert config.confidence_threshold == 0.6


def test_config_image_cap_parsed():
    config = parse_config({
        "document_types": [{"id": "x", "description": "X"}],
        "image_cap": 5,
    })
    assert config.image_cap == 5


# ---------------------------------------------------------------------------
# Tracer: low-confidence sub-doc images forwarded
# ---------------------------------------------------------------------------

def test_low_confidence_images_forwarded_to_analyze_antrag():
    # No fields extracted → confidence 0.0 < threshold 0.5 → images forwarded
    spy = _make_spy(Legibility.ILLEGIBLE)
    config = {
        "document_types": [{"id": "personalausweis", "description": "PA", "required": True}],
        "confidence_threshold": 0.5,
    }
    client = _app(spy)
    resp = _upload_antrag(client, config)
    assert resp.status_code == 202
    assert spy.received_images_per_result is not None
    assert any(len(imgs) > 0 for imgs in spy.received_images_per_result)


# ---------------------------------------------------------------------------
# High-confidence sub-doc: images withheld
# ---------------------------------------------------------------------------

def test_high_confidence_images_withheld():
    # LEGIBLE field → confidence 1.0 >= threshold 0.5 → images withheld
    spy = _make_spy(Legibility.LEGIBLE)
    config = {
        "document_types": [{"id": "personalausweis", "description": "PA", "required": True}],
        "confidence_threshold": 0.5,
    }
    client = _app(spy)
    resp = _upload_antrag(client, config)
    assert resp.status_code == 202
    assert spy.received_images_per_result is not None
    assert all(len(imgs) == 0 for imgs in spy.received_images_per_result)


# ---------------------------------------------------------------------------
# Boundary: confidence == threshold → withheld (strictly below)
# ---------------------------------------------------------------------------

def test_at_threshold_images_withheld():
    # LEGIBLE field → confidence 1.0, threshold 1.0 → NOT strictly below → withheld
    spy = _make_spy(Legibility.LEGIBLE)
    config = {
        "document_types": [{"id": "personalausweis", "description": "PA", "required": True}],
        "confidence_threshold": 1.0,
    }
    client = _app(spy)
    resp = _upload_antrag(client, config)
    assert resp.status_code == 202
    assert all(len(imgs) == 0 for imgs in spy.received_images_per_result)


# ---------------------------------------------------------------------------
# Image cap: total images across sub-docs capped; excess dropped
# ---------------------------------------------------------------------------

def test_image_cap_limits_total_forwarded_images():
    # 3 single-page JPEG uploads → 3 segments (one per file), each confidence 0.0
    # cap=2 → at most 2 images total forwarded
    spy = _make_spy(Legibility.ILLEGIBLE)
    config = {
        "document_types": [{"id": "personalausweis", "description": "PA", "required": True}],
        "confidence_threshold": 0.5,
        "image_cap": 2,
    }
    files = [
        ("files", ("a.jpg", _FAKE_BYTES, "image/jpeg")),
        ("files", ("b.jpg", _FAKE_BYTES_2, "image/jpeg")),
        ("files", ("c.jpg", _FAKE_BYTES_3, "image/jpeg")),
    ]
    client = _app(spy)
    resp = _upload_antrag(client, config, files=files)
    assert resp.status_code == 202
    total_forwarded = sum(len(imgs) for imgs in spy.received_images_per_result)
    assert total_forwarded <= 2


# ---------------------------------------------------------------------------
# Truncation logged: when cap is hit, a warning is emitted
# ---------------------------------------------------------------------------

def test_image_cap_truncation_is_logged(caplog):
    spy = _make_spy(Legibility.ILLEGIBLE)
    config = {
        "document_types": [{"id": "personalausweis", "description": "PA", "required": True}],
        "confidence_threshold": 0.5,
        "image_cap": 1,
    }
    files = [
        ("files", ("a.jpg", _FAKE_BYTES, "image/jpeg")),
        ("files", ("b.jpg", _FAKE_BYTES_2, "image/jpeg")),
    ]
    client = _app(spy)
    with caplog.at_level(logging.WARNING, logger="docval.pipeline"):
        resp = _upload_antrag(client, config, files=files)
    assert resp.status_code == 202
    assert caplog.records, "Expected a warning log when image cap is exceeded"
    assert any("cap" in r.message.lower() or "truncat" in r.message.lower() for r in caplog.records)
