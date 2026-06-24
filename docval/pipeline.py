"""Two-stage pipeline: Stufe 1 classify -> Stufe 2 extract + validate.

On a wrong type, extraction is skipped and the result reports `invalid_type`
(reported only — DocVerify never filters or blocks uploads).
"""

from __future__ import annotations

from typing import Sequence

from .config import Config
from .model_client import ModelClient
from .schemas import (
    FieldResult,
    Legibility,
    ValidationResult,
    ValidationStatus,
)

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
    def __init__(self, config: Config, model_client: ModelClient):
        self._config = config
        self._model = model_client

    def run(self, images: Sequence[bytes]) -> ValidationResult:
        # Stufe 1 looks at page 1 only; Stufe 2 sees all pages.
        classification = self._model.classify(list(images[:1]), self._config)
        doc_type = self._config.get(classification.document_type)

        if doc_type is None:
            return ValidationResult(
                validation_status=ValidationStatus.INVALID_TYPE,
                confidence=0.0,
                classification=classification,
            )

        outcome = self._model.extract_and_validate(images, doc_type)
        return ValidationResult(
            validation_status=outcome.validation_status,
            confidence=aggregate_confidence(outcome.fields),
            classification=classification,
            extracted_data=outcome.fields,
            deficiencies=outcome.deficiencies,
            internal_note=outcome.internal_note,
        )
