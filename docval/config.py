"""Configuration model and loader.

config.yaml uses structured keys with natural-language values, and is
schema-validated on load — a malformed config fails loudly.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    """Raised when a config file cannot be read, parsed, or validated."""


class ExpectedField(BaseModel):
    name: str
    description: str
    type_hint: str | None = None


class DocumentTypeConfig(BaseModel):
    id: str
    description: str
    expected_fields: list[ExpectedField] = Field(default_factory=list)
    criteria: str | None = None


class Config(BaseModel):
    document_types: list[DocumentTypeConfig]

    def get(self, type_id: str) -> DocumentTypeConfig | None:
        return next((d for d in self.document_types if d.id == type_id), None)


def load_config(path: str | Path) -> Config:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read config file {path!r}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file {path!r} is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}")

    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Config file {path!r} failed validation:\n{exc}") from exc
