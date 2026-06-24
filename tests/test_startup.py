from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docval.app import build_app
from docval.config import ConfigError


def test_build_app_loads_and_validates_the_example_config(accepted_fake):
    app = build_app(Path("config.example.yaml"), accepted_fake)
    client = TestClient(app)
    assert client.get("/openapi.json").status_code == 200


def test_build_app_with_malformed_config_fails_loudly(tmp_path, accepted_fake):
    bad = tmp_path / "bad.yaml"
    bad.write_text("document_types: not-a-list\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        build_app(bad, accepted_fake)
