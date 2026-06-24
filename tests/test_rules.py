"""Unit tests for the deterministic hybrid rule layer (Slice 5)."""

from datetime import date

from docval.rules import Rule, RuleKind, apply_rules
from docval.schemas import (
    Classification,
    FieldResult,
    Legibility,
    ValidationResult,
    ValidationStatus,
)

TODAY = date(2026, 6, 24)


def _result(status=ValidationStatus.ACCEPTED, fields=None):
    return ValidationResult(
        validation_status=status,
        confidence=1.0,
        classification=Classification(document_type="personalausweis"),
        extracted_data=fields or [],
    )


def _field(name, value, legibility=Legibility.LEGIBLE):
    return FieldResult(name=name, value=value, legibility=legibility)


def test_format_rule_failure_downgrades_accepted_to_incomplete():
    result = _result(fields=[_field("seriennummer", "ABC")])
    rules = [Rule(field="seriennummer", kind=RuleKind.FORMAT, pattern=r"^\d{9}$")]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE
    assert any(d.field == "seriennummer" for d in out.deficiencies)


def test_required_rule_fails_when_field_missing():
    result = _result(fields=[])  # nachname was never extracted
    rules = [Rule(field="nachname", kind=RuleKind.REQUIRED)]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE
    assert any(d.field == "nachname" for d in out.deficiencies)


def test_required_rule_fails_when_field_illegible():
    result = _result(fields=[_field("nachname", "Mustermann", Legibility.ILLEGIBLE)])
    rules = [Rule(field="nachname", kind=RuleKind.REQUIRED)]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE


def test_allowed_values_rule_fails_for_value_outside_set():
    result = _result(fields=[_field("ger_level", "B3")])
    rules = [Rule(field="ger_level", kind=RuleKind.ALLOWED_VALUES, allowed=["A1", "A2", "B1", "B2", "C1", "C2"])]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE
    assert any(d.field == "ger_level" for d in out.deficiencies)


def test_allowed_values_rule_passes_for_value_in_set():
    result = _result(fields=[_field("ger_level", "B1")])
    rules = [Rule(field="ger_level", kind=RuleKind.ALLOWED_VALUES, allowed=["A1", "A2", "B1", "B2", "C1", "C2"])]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.ACCEPTED


def test_not_in_past_rule_fails_for_expired_date():
    result = _result(fields=[_field("gueltig_bis", "2025-01-01")])
    rules = [Rule(field="gueltig_bis", kind=RuleKind.NOT_IN_PAST)]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE
    assert any(d.field == "gueltig_bis" for d in out.deficiencies)


def test_not_in_past_rule_passes_for_future_date():
    result = _result(fields=[_field("gueltig_bis", "2030-12-31")])
    rules = [Rule(field="gueltig_bis", kind=RuleKind.NOT_IN_PAST)]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.ACCEPTED


def test_not_in_past_rule_fails_for_unparseable_date():
    result = _result(fields=[_field("gueltig_bis", "not-a-date")])
    rules = [Rule(field="gueltig_bis", kind=RuleKind.NOT_IN_PAST)]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.INCOMPLETE


def test_no_rules_returns_the_model_verdict_unchanged():
    result = _result(
        status=ValidationStatus.ACCEPTED,
        fields=[_field("seriennummer", "anything")],
    )

    out = apply_rules([], result, today=TODAY)

    assert out == result


def test_passing_rule_leaves_verdict_unchanged():
    result = _result(fields=[_field("seriennummer", "T22000129")])
    rules = [Rule(field="seriennummer", kind=RuleKind.FORMAT, pattern=r"^.{9}$")]

    out = apply_rules(rules, result, today=TODAY)

    assert out.validation_status == ValidationStatus.ACCEPTED
    assert out.deficiencies == []
