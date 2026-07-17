"""Domain and result schemas.

The result schema doubles as the public API contract.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    ACCEPTED = "accepted"
    INCOMPLETE = "incomplete"
    INVALID_TYPE = "invalid_type"


class Legibility(str, Enum):
    LEGIBLE = "legible"
    PARTIAL = "partial"
    ILLEGIBLE = "illegible"


class Classification(BaseModel):
    """Result of Stufe 1 — what type the model thinks the document is."""

    document_type: str


class FieldResult(BaseModel):
    """One extracted field with the model's per-field legibility judgement."""

    name: str
    value: str | None = None
    legibility: Legibility


class Deficiency(BaseModel):
    """A required field that was missing or not legible."""

    field: str
    reason: str


class ExtractionOutcome(BaseModel):
    """Result of Stufe 2 as returned by the model (verdict + observations)."""

    validation_status: ValidationStatus
    fields: list[FieldResult] = Field(default_factory=list)
    deficiencies: list[Deficiency] = Field(default_factory=list)
    internal_note: str | None = None


class ValidationResult(BaseModel):
    """The standardized result returned via the API."""

    validation_status: ValidationStatus
    confidence: float
    classification: Classification
    extracted_data: list[FieldResult] = Field(default_factory=list)
    deficiencies: list[Deficiency] = Field(default_factory=list)
    internal_note: str | None = None


class ScanResult(BaseModel):
    """Result of scan mode: type inferred, all fields extracted, no verdict.

    Honest polymorphism — validation_status and deficiencies are intentionally
    absent (not nullable) to reflect that no validation was requested.
    """

    classification: Classification
    extracted_data: list[FieldResult] = Field(default_factory=list)
    confidence: float
