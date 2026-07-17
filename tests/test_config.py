import pytest

from docval.config import Config, ConfigError, load_config
from docval.rules import RuleKind

VALID = """
document_types:
  - id: personalausweis
    description: A German national identity card (Personalausweis) or passport.
    expected_fields:
      - name: nachname
        description: Surname
        type_hint: string
    criteria: Must be a valid German ID document; core data must be unredacted.
"""

VALID_WITH_RULES = """
document_types:
  - id: personalausweis
    description: A German national identity card.
    expected_fields:
      - name: seriennummer
        description: 9-character serial number
    criteria: Must be valid.
    rules:
      - field: seriennummer
        kind: format
        pattern: '^.{9}$'
      - field: gueltig_bis
        kind: not_in_past
"""


def test_load_valid_config_returns_typed_model(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(VALID, encoding="utf-8")

    cfg = load_config(path)

    assert isinstance(cfg, Config)
    assert cfg.get("personalausweis").description.startswith("A German national identity card")
    assert cfg.get("personalausweis").expected_fields[0].name == "nachname"


def test_config_with_rules_block_loads(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(VALID_WITH_RULES, encoding="utf-8")

    cfg = load_config(path)

    rules = cfg.get("personalausweis").rules
    assert [r.field for r in rules] == ["seriennummer", "gueltig_bis"]
    assert rules[0].kind is RuleKind.FORMAT
    assert rules[1].kind is RuleKind.NOT_IN_PAST


def test_malformed_config_fails_loudly(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("document_types: not-a-list\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(path)


def test_format_rule_without_pattern_fails_loudly(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
document_types:
  - id: personalausweis
    description: A German ID.
    criteria: valid
    rules:
      - field: seriennummer
        kind: format
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_allowed_values_rule_without_allowed_fails_loudly(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
document_types:
  - id: sprachzertifikat
    description: A language certificate.
    criteria: valid
    rules:
      - field: ger_level
        kind: allowed_values
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_fails_loudly(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


# --- parse_config: inline dict source ---

from docval.config import parse_config  # noqa: E402


VALID_DICT = {
    "document_types": [
        {
            "id": "personalausweis",
            "description": "A German national identity card.",
            "expected_fields": [{"name": "nachname", "description": "Surname"}],
            "criteria": "Must be valid.",
        }
    ]
}


def test_parse_config_accepts_valid_dict():
    cfg = parse_config(VALID_DICT)
    assert cfg.get("personalausweis").id == "personalausweis"


def test_parse_config_raises_config_error_on_malformed_dict():
    with pytest.raises(ConfigError):
        parse_config({"document_types": "not-a-list"})
