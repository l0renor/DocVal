"""Configuration model and loader.

config.yaml uses structured keys with natural-language values, and is
schema-validated on load — a malformed config fails loudly.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from .rules import Rule


class ConfigError(Exception):
    """Raised when a config file cannot be read, parsed, or validated."""


class ExpectedField(BaseModel):
    name: str
    description: str
    type_hint: str | None = None


class DocumentTypeConfig(BaseModel):
    id: str
    description: str
    required: bool = True
    expected_fields: list[ExpectedField] = Field(default_factory=list)
    criteria: str | None = None
    rules: list[Rule] = Field(default_factory=list)


class Config(BaseModel):
    document_types: list[DocumentTypeConfig]
    # Legibility-based threshold (0–1): sub-documents whose aggregated field
    # legibility score is strictly below this value have their page images
    # forwarded to analyze_antrag for cross-document visual inspection.
    # Note: this is a legibility aggregate, not a classification probability.
    confidence_threshold: float = 0.8
    image_cap: int = Field(default=50, ge=1, le=500)

    def get(self, type_id: str) -> DocumentTypeConfig | None:
        return next((d for d in self.document_types if d.id == type_id), None)


def parse_config(data: dict) -> Config:
    """Validate an already-parsed dict into a Config. Raises ConfigError on failure.

    Shared by load_config (file source) and the API layer (inline request payload).
    """
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Config failed validation:\n{exc}") from exc


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

    return parse_config(data)
