import pytest

from docval.config import Config, ConfigError, load_config

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


def test_load_valid_config_returns_typed_model(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(VALID, encoding="utf-8")

    cfg = load_config(path)

    assert isinstance(cfg, Config)
    assert cfg.get("personalausweis").description.startswith("A German national identity card")
    assert cfg.get("personalausweis").expected_fields[0].name == "nachname"


def test_malformed_config_fails_loudly(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("document_types: not-a-list\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_fails_loudly(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")
