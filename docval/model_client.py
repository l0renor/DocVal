"""The model seam.

`ModelClient` is the single injection point for the vision model. The real
Azure GPT-5.5 implementation lands in a later slice; `FakeModelClient` returns
canned outputs so the whole pipeline is testable without a live model.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .config import Config, DocumentTypeConfig
from .schemas import AntragsResult, Classification, ExtractionOutcome, FieldResult, RequiredField, ValidationResult


class ModelClient(Protocol):
    def classify(self, images: Sequence[bytes], config: Config | None) -> Classification: ...

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome: ...

    def scan(self, images: Sequence[bytes]) -> list[FieldResult]: ...

    def extract_targeted(
        self, images: Sequence[bytes], required_fields: Sequence[RequiredField]
    ) -> list[FieldResult]: ...

    def analyze_antrag(
        self,
        results: Sequence[ValidationResult],
        images_per_result: Sequence[Sequence[bytes]],
    ) -> AntragsResult: ...


class FakeModelClient:
    """Returns pre-canned classification / extraction results for tests."""

    def __init__(
        self,
        classification: Classification | None = None,
        extraction: ExtractionOutcome | None = None,
        scan_fields: list[FieldResult] | None = None,
        targeted_fields: list[FieldResult] | None = None,
        antrag_result: AntragsResult | None = None,
    ):
        self._classification = classification
        self._extraction = extraction
        self._scan_fields = scan_fields
        self._targeted_fields = targeted_fields
        self._antrag_result = antrag_result

    def classify(self, images: Sequence[bytes], config: Config | None) -> Classification:
        if self._classification is None:
            raise AssertionError("FakeModelClient.classify called without a canned classification")
        return self._classification

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome:
        if self._extraction is None:
            raise AssertionError("FakeModelClient.extract_and_validate called without a canned extraction")
        return self._extraction

    def scan(self, images: Sequence[bytes]) -> list[FieldResult]:
        if self._scan_fields is None:
            raise AssertionError("FakeModelClient.scan called without canned scan_fields")
        return self._scan_fields

    def extract_targeted(
        self, images: Sequence[bytes], required_fields: Sequence[RequiredField]
    ) -> list[FieldResult]:
        if self._targeted_fields is None:
            raise AssertionError("FakeModelClient.extract_targeted called without canned targeted_fields")
        return self._targeted_fields

    def analyze_antrag(
        self,
        results: Sequence[ValidationResult],
        images_per_result: Sequence[Sequence[bytes]],
    ) -> AntragsResult:
        if self._antrag_result is None:
            raise AssertionError("FakeModelClient.analyze_antrag called without canned antrag_result")
        return self._antrag_result


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

    def classify(self, images: Sequence[bytes], config: Config | None) -> Classification:
        doc_type = self._page_types[self._classify_calls]
        self._classify_calls += 1
        return Classification(document_type=doc_type)

    def scan(self, images: Sequence[bytes]) -> list[FieldResult]:
        raise AssertionError("ScriptedModelClient.scan not expected in segmentation tests")

    def extract_targeted(
        self, images: Sequence[bytes], required_fields: Sequence[RequiredField]
    ) -> list[FieldResult]:
        raise AssertionError("ScriptedModelClient.extract_targeted not expected in segmentation tests")

    def analyze_antrag(
        self,
        results: Sequence[ValidationResult],
        images_per_result: Sequence[Sequence[bytes]],
    ) -> AntragsResult:
        raise AssertionError("ScriptedModelClient.analyze_antrag not expected in segmentation tests")

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome:
        outcome = self._extractions.get(doc_type.id)
        if outcome is None:
            raise AssertionError(
                f"ScriptedModelClient has no canned extraction for type {doc_type.id!r}"
            )
        return outcome
