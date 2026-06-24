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


class ScriptedModelClient:
    """Fake driven by per-page classifications, for segmentation tests.

    `page_types` lists the Stufe-1 type each page classifies as, in page order
    (`classify` is called once per page during segmentation). `extractions` maps
    a configured type id to its Stufe-2 outcome; a type with no canned outcome
    raises if extraction is attempted (proving wrong types skip Stufe 2).
    """

    def __init__(
        self,
        page_types: Sequence[str],
        extractions: dict[str, ExtractionOutcome] | None = None,
    ):
        self._page_types = list(page_types)
        self._extractions = extractions or {}
        self._classify_calls = 0

    def classify(self, images: Sequence[bytes], config: Config) -> Classification:
        doc_type = self._page_types[self._classify_calls]
        self._classify_calls += 1
        return Classification(document_type=doc_type)

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome:
        outcome = self._extractions.get(doc_type.id)
        if outcome is None:
            raise AssertionError(
                f"ScriptedModelClient has no canned extraction for type {doc_type.id!r}"
            )
        return outcome
