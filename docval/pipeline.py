"""Two-stage pipeline: Stufe 1 classify -> Stufe 2 extract + validate.

An upload is first segmented into sub-documents (a single PDF may bundle
several distinct documents); each sub-document then runs the two stages
independently and contributes one result. On a wrong type, extraction is
skipped and that sub-document reports `invalid_type` (reported only —
DocVerify never filters or blocks uploads).
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Sequence

from .config import Config
from .model_client import ModelClient
from .rules import apply_rules
from .schemas import (
    FieldResult,
    Legibility,
    ValidationResult,
    ValidationStatus,
)
from .segment import Segment, segment_pages

_LEGIBILITY_SCORE = {
    Legibility.LEGIBLE: 1.0,
    Legibility.PARTIAL: 0.5,
    Legibility.ILLEGIBLE: 0.0,
}


def aggregate_confidence(fields: Sequence[FieldResult]) -> float:
    """Aggregate per-field legibility into a readability score (not a probability)."""
    if not fields:
        return 0.0
    return sum(_LEGIBILITY_SCORE[f.legibility] for f in fields) / len(fields)


class Pipeline:
    def __init__(
        self,
        config: Config,
        model_client: ModelClient,
        today: Callable[[], date] = date.today,
    ):
        self._config = config
        self._model = model_client
        self._today = today

    def run(self, images: Sequence[bytes]) -> list[ValidationResult]:
        """Segment the upload, then validate each sub-document independently."""
        segments = segment_pages(images, self._model, self._config)
        return [self._validate(segment) for segment in segments]

    def _validate(self, segment: Segment) -> ValidationResult:
        # Stufe 1 already produced the classification during segmentation.
        doc_type = self._config.get(segment.classification.document_type)

        if doc_type is None:
            return ValidationResult(
                validation_status=ValidationStatus.INVALID_TYPE,
                confidence=0.0,
                classification=segment.classification,
            )

        # Stufe 2 sees every page of this sub-document.
        outcome = self._model.extract_and_validate(segment.images, doc_type)
        result = ValidationResult(
            validation_status=outcome.validation_status,
            confidence=aggregate_confidence(outcome.fields),
            classification=segment.classification,
            extracted_data=outcome.fields,
            deficiencies=outcome.deficiencies,
            internal_note=outcome.internal_note,
        )

        # Optional hybrid layer: deterministic rules reconcile the model verdict.
        return apply_rules(doc_type.rules, result, self._today())
