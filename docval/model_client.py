"""The model seam.

`ModelClient` is the single injection point for the vision model. The real
Azure GPT-5.5 implementation lands in a later slice; `FakeModelClient` returns
canned outputs so the whole pipeline is testable without a live model.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .config import Config, DocumentTypeConfig
from .schemas import Classification, ExtractionOutcome


class ModelClient(Protocol):
    def classify(self, images: Sequence[bytes], config: Config) -> Classification: ...

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome: ...


class FakeModelClient:
    """Returns pre-canned classification / extraction results for tests."""

    def __init__(self, classification: Classification, extraction: ExtractionOutcome | None = None):
        self._classification = classification
        self._extraction = extraction

    def classify(self, images: Sequence[bytes], config: Config) -> Classification:
        return self._classification

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome:
        if self._extraction is None:
            raise AssertionError("FakeModelClient.extract_and_validate called without a canned extraction")
        return self._extraction
