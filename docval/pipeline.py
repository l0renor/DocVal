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
    AntragsMetadata,
    Deficiency,
    FieldResult,
    Legibility,
    RequiredField,
    ScanResult,
    TargetedResult,
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
        config: Config | None,
        model_client: ModelClient,
        today: Callable[[], date] = date.today,
    ):
        self._config = config
        self._model = model_client
        self._today = today

    def run_targeted(self, images: Sequence[bytes], required_fields: list[RequiredField]) -> TargetedResult:
        """Targeted mode: extract only the requested fields, no classification."""
        all_fields = self._model.extract_targeted(images, required_fields)
        requested_names = {f.name for f in required_fields}
        filtered = [f for f in all_fields if f.name in requested_names]
        field_map = {f.name: f for f in filtered}

        deficiencies: list[Deficiency] = []
        for req in required_fields:
            field = field_map.get(req.name)
            if field is None:
                deficiencies.append(Deficiency(field=req.name, reason="Field not found"))
            elif field.legibility == Legibility.ILLEGIBLE:
                deficiencies.append(Deficiency(field=req.name, reason="Field not legible"))

        status = ValidationStatus.ACCEPTED if not deficiencies else ValidationStatus.INCOMPLETE
        return TargetedResult(
            validation_status=status,
            confidence=aggregate_confidence(filtered),
            extracted_data=filtered,
            deficiencies=deficiencies,
        )

    def run_antrag(
        self, images_per_file: Sequence[Sequence[bytes]], config: Config
    ) -> tuple[list[ValidationResult], AntragsMetadata]:
        """Antrag bundle: validate each file, union results, then cross-document analysis."""
        results: list[ValidationResult] = []
        for images in images_per_file:
            segments = segment_pages(images, self._model, config)
            results.extend(self._validate(segment) for segment in segments)

        # Deterministic completeness: required doc types with no matching sub-doc.
        found_types = {r.classification.document_type for r in results}
        missing = [
            dt.id for dt in config.document_types
            if dt.required and dt.id not in found_types
        ]
        missing_findings = [
            f"Pflichtdokument fehlt: {dt_id}" for dt_id in missing
        ]

        antrag_result = self._model.analyze_antrag(results)
        all_findings = antrag_result.cross_document_findings + missing_findings

        # Bundle verdict: accepted only when all docs accepted, no findings, no missing.
        all_accepted = all(r.validation_status == ValidationStatus.ACCEPTED for r in results)
        antrag_status = "accepted" if (all_accepted and not all_findings and not missing) else "incomplete"

        metadata = AntragsMetadata(
            antrag_status=antrag_status,
            cross_document_findings=all_findings,
            missing_required_documents=missing,
            summary=antrag_result.summary,
        )
        return results, metadata

    def run_scan(self, images: Sequence[bytes]) -> ScanResult:
        """Scan mode: classify freely, extract all fields, return no verdict."""
        classification = self._model.classify(images, config=None)
        fields = self._model.scan(images)
        return ScanResult(
            classification=classification,
            extracted_data=fields,
            confidence=aggregate_confidence(fields),
        )

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
