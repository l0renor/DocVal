"""Optional hybrid deterministic rule layer.

After the model returns its verdict + extracted data, a document type may apply
deterministic rules (declared in config.yaml) for auditable, code-level checks
(expiry not in the past, value formats, allowed sets, required fields). Rules
only ever add to the Mängelliste and downgrade an `accepted` verdict — they
never upgrade. With no rules configured, the model verdict passes through
unchanged.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Sequence

from pydantic import BaseModel, model_validator

from .schemas import Deficiency, FieldResult, Legibility, ValidationResult, ValidationStatus


class RuleKind(str, Enum):
    REQUIRED = "required"
    FORMAT = "format"
    ALLOWED_VALUES = "allowed_values"
    NOT_IN_PAST = "not_in_past"


class Rule(BaseModel):
    field: str
    kind: RuleKind
    pattern: str | None = None
    allowed: list[str] | None = None
    message: str | None = None

    @model_validator(mode="after")
    def _require_params_for_kind(self) -> "Rule":
        if self.kind is RuleKind.FORMAT and self.pattern is None:
            raise ValueError("a 'format' rule requires a 'pattern'")
        if self.kind is RuleKind.ALLOWED_VALUES and not self.allowed:
            raise ValueError("an 'allowed_values' rule requires a non-empty 'allowed' list")
        return self


def apply_rules(
    rules: Sequence[Rule], result: ValidationResult, today: date
) -> ValidationResult:
    fields = {f.name: f for f in result.extracted_data}
    new_deficiencies: list[Deficiency] = []

    for rule in rules:
        reason = _evaluate(rule, fields.get(rule.field), today)
        if reason is not None:
            new_deficiencies.append(Deficiency(field=rule.field, reason=rule.message or reason))

    if not new_deficiencies:
        return result

    return result.model_copy(
        update={
            "validation_status": ValidationStatus.INCOMPLETE,
            "deficiencies": [*result.deficiencies, *new_deficiencies],
        }
    )


def _evaluate(rule: Rule, field: FieldResult | None, today: date) -> str | None:
    """Return a failure reason, or None if the rule passes."""
    value = field.value if field is not None else None

    if rule.kind is RuleKind.REQUIRED:
        if field is None or value is None or value == "" or field.legibility is Legibility.ILLEGIBLE:
            return "required field is missing or not legible"

    if rule.kind is RuleKind.FORMAT:
        if value is None or not re.fullmatch(rule.pattern, value):
            return f"value {value!r} does not match required format {rule.pattern!r}"

    if rule.kind is RuleKind.ALLOWED_VALUES:
        if value not in rule.allowed:
            return f"value {value!r} is not one of the allowed values {rule.allowed!r}"

    if rule.kind is RuleKind.NOT_IN_PAST:
        try:
            parsed = date.fromisoformat(value) if value is not None else None
        except ValueError:
            parsed = None
        if parsed is None:
            return f"value {value!r} is not a valid date (expected YYYY-MM-DD)"
        if parsed < today:
            return f"date {value} is in the past (as of {today.isoformat()})"

    return None
