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


def _make_result(doc_type):
    from docval.schemas import Classification as Cls, ValidationResult, ValidationStatus
    return ValidationResult(
        validation_status=ValidationStatus.ACCEPTED,
        confidence=0.9,
        classification=Cls(document_type=doc_type),
        extracted_data=[],
        deficiencies=[],
    )


def test_analyze_antrag_labels_each_image_group_before_its_images():
    # Without per-group labels the model sees images as a flat blob with no
    # provenance. A text label specific to each sub-doc type must appear
    # immediately before that group's first image in the content list.
    # This rules out the opening JSON summary (which mentions all types) serving
    # as the "label" — each group needs its own dedicated text block.
    from docval.schemas import AntragsResult

    parsed = AntragsResult(cross_document_findings=[], summary="OK")
    client, completions = _fake_client(parsed)
    mc = AzureModelClient(client, deployment="gpt-5.5")

    mc.analyze_antrag(
        [_make_result("personalausweis"), _make_result("mietvertrag")],
        [[b"img-a"], [b"img-b"]],
    )

    call = completions.calls[0]
    user_content = next(m["content"] for m in call["messages"] if m["role"] == "user")

    # Build a list of (content_type, text_or_empty) for easy slicing.
    blocks = [(p.get("type"), p.get("text", "")) for p in user_content]

    # Find the index of each group's first image in the flat content list.
    # img-a is the image for group 0 (personalausweis); img-b for group 1 (mietvertrag).
    img_indices = [i for i, (t, _) in enumerate(blocks) if t == "image_url"]
    assert len(img_indices) == 2, f"expected exactly 2 images in content, got {len(img_indices)}"

    # Each group's first image must be immediately preceded by a dedicated text
    # block (not another image) that names the sub-doc type.
    def label_before(idx):
        if idx == 0:
            return ""
        prev_type, prev_text = blocks[idx - 1]
        return prev_text if prev_type == "text" else ""

    label_for_ausweis = label_before(img_indices[0])
    label_for_mietvertrag = label_before(img_indices[1])

    assert "personalausweis" in label_for_ausweis, \
        f"expected 'personalausweis' in text immediately before first image, got: {label_for_ausweis!r}"
    assert "mietvertrag" in label_for_mietvertrag, \
        f"expected 'mietvertrag' in text immediately before second image, got: {label_for_mietvertrag!r}"


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
