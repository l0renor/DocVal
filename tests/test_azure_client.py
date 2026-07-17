from types import SimpleNamespace

import pytest

from docval.azure_client import AzureModelClient
from docval.config import Config, DocumentTypeConfig, ExpectedField
from docval.config import ConfigError
from docval.schemas import (
    Classification,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)


class _FakeCompletions:
    def __init__(self, parsed):
        self._parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(parsed=self._parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _fake_client(parsed):
    completions = _FakeCompletions(parsed)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


FULL_ENV = {
    "AZURE_OPENAI_API_KEY": "k",
    "AZURE_OPENAI_ENDPOINT": "https://r.openai.azure.com",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-5.5",
}


def _config():
    return Config(
        document_types=[
            DocumentTypeConfig(
                id="personalausweis",
                description="A German national identity card.",
                expected_fields=[ExpectedField(name="nachname", description="Surname")],
                criteria="Must be a valid German ID.",
            )
        ]
    )


def _image_parts(call):
    parts = []
    for m in call["messages"]:
        if isinstance(m["content"], list):
            parts.extend(m["content"])
    return [p for p in parts if p.get("type") == "image_url"]


def test_from_env_missing_settings_fails_loudly():
    with pytest.raises(ConfigError):
        AzureModelClient.from_env(env={})


def test_from_env_with_full_settings_builds_client_with_deployment():
    mc = AzureModelClient.from_env(env=FULL_ENV)
    assert isinstance(mc, AzureModelClient)
    assert mc.deployment == "gpt-5.5"


def test_classify_uses_structured_output_and_sends_image():
    parsed = Classification(document_type="personalausweis")
    client, completions = _fake_client(parsed)
    mc = AzureModelClient(client, deployment="gpt-5.5")

    result = mc.classify([b"img-bytes"], _config())

    assert result == parsed
    call = completions.calls[0]
    assert call["model"] == "gpt-5.5"
    assert call["response_format"] is Classification
    assert len(_image_parts(call)) == 1


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"fake-jpeg-body"


def test_png_pages_are_sent_with_png_mime_type():
    # Ingest renders PDF pages as PNG; the data URL must not claim image/jpeg.
    client, completions = _fake_client(Classification(document_type="personalausweis"))
    mc = AzureModelClient(client, deployment="gpt-5.5")

    mc.classify([PNG_BYTES], _config())

    (image_part,) = _image_parts(completions.calls[0])
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_jpeg_pages_are_sent_with_jpeg_mime_type():
    client, completions = _fake_client(Classification(document_type="personalausweis"))
    mc = AzureModelClient(client, deployment="gpt-5.5")

    mc.classify([JPEG_BYTES], _config())

    (image_part,) = _image_parts(completions.calls[0])
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_extract_and_validate_returns_parsed_outcome_and_sends_images():
    parsed = ExtractionOutcome(
        validation_status=ValidationStatus.ACCEPTED,
        fields=[FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE)],
    )
    client, completions = _fake_client(parsed)
    mc = AzureModelClient(client, deployment="gpt-5.5")

    result = mc.extract_and_validate([b"p1", b"p2"], _config().get("personalausweis"))

    assert result == parsed
    call = completions.calls[0]
    assert call["response_format"] is ExtractionOutcome
    assert len(_image_parts(call)) == 2
