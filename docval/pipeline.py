"""Two-stage pipeline: Stufe 1 classify -> Stufe 2 extract + validate.

An upload is first segmented into sub-documents (a single PDF may bundle
several distinct documents); each sub-document then runs the two stages
independently and contributes one result. On a wrong type, extraction is
skipped and that sub-document reports `invalid_type` (reported only —
DocVerify never filters or blocks uploads).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Sequence

from .config import Config
from .model_client import ModelClient
from .rules import apply_rules
from .schemas import (
    AntragsMetadata,
    AntragsResult,
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

_logger = logging.getLogger(__name__)

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
        result_pairs: list[tuple[ValidationResult, list[bytes]]] = []
        for images in images_per_file:
            segments = segment_pages(images, self._model, config)
            for segment in segments:
                result = self._validate(segment)
                result_pairs.append((result, segment.images))

        results = [r for r, _ in result_pairs]

        # Select images for analyze_antrag: only sub-docs below the confidence threshold.
        threshold = config.confidence_threshold
        cap = config.image_cap
        selected: list[list[bytes]] = []
        total = 0
        truncated = False
        for result, imgs in result_pairs:
            if result.confidence < threshold:
                remaining = cap - total
                if remaining <= 0:
                    selected.append([])
                    truncated = True
                elif len(imgs) > remaining:
                    selected.append(list(imgs[:remaining]))
                    total += remaining
                    truncated = True
                else:
                    selected.append(list(imgs))
                    total += len(imgs)
            else:
                selected.append([])

        if truncated:
            _logger.warning(
                "analyze_antrag: image cap of %d reached; some sub-document images were truncated", cap
            )

        # Deterministic completeness: required doc types with no matching sub-doc.
        found_types = {r.classification.document_type for r in results}
        missing = [
            dt.id for dt in config.document_types
            if dt.required and dt.id not in found_types
        ]
        # Cross-document analysis needs at least two sub-docs to compare; skip for one.
        if len(results) >= 2:
            antrag_result = self._model.analyze_antrag(results, selected)
        else:
            antrag_result = AntragsResult(cross_document_findings=[], summary="")

        # Bundle verdict: accepted only when all docs accepted, no model findings, no missing.
        all_accepted = all(r.validation_status == ValidationStatus.ACCEPTED for r in results)
        antrag_status = (
            "accepted"
            if (all_accepted and not antrag_result.cross_document_findings and not missing)
            else "incomplete"
        )

        metadata = AntragsMetadata(
            antrag_status=antrag_status,
            cross_document_findings=antrag_result.cross_document_findings,
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
