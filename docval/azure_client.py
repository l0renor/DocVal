"""Azure GPT-5.5 implementation of the ModelClient interface.

The Azure OpenAI SDK client is injected (constructor) so tests run offline;
`from_env()` builds the real client from environment variables (a local `.env`
is loaded if present). Both calls use structured outputs (Pydantic
`response_format`) so responses always conform to the schemas.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Mapping, Sequence

from .config import Config, ConfigError, DocumentTypeConfig
from .schemas import (
    AntragsResult,
    Classification,
    ExtractionOutcome,
    FieldResult,
    RequiredField,
    ValidationResult,
)

DEFAULT_API_VERSION = "2024-10-21"


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _data_url(image: bytes) -> str:
    """Base64 data URL with the MIME type sniffed from the image bytes.

    Ingest produces PNG for rendered PDF pages and passes uploaded JPEG/PNG
    through unchanged, so these two formats cover everything we send.
    """
    mime = "image/png" if image.startswith(_PNG_MAGIC) else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"


def _compact_doc(result: ValidationResult) -> dict:
    """Compact per-document summary for the analyze_antrag prompt."""
    return {
        "type": result.classification.document_type,
        "status": result.validation_status.value,
        "fields": {
            f.name: f.value
            for f in result.extracted_data
            if f.value is not None
        },
        "deficiencies": [d.field for d in result.deficiencies],
    }


class AzureModelClient:
    def __init__(self, client, deployment: str):
        self._client = client
        self._deployment = deployment

    @property
    def deployment(self) -> str:
        return self._deployment

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AzureModelClient":
        if env is None:
            from dotenv import load_dotenv

            load_dotenv()
            env = os.environ

        key = env.get("AZURE_OPENAI_API_KEY")
        endpoint = env.get("AZURE_OPENAI_ENDPOINT")
        deployment = env.get("AZURE_OPENAI_DEPLOYMENT")
        api_version = env.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)

        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_API_KEY", key),
                ("AZURE_OPENAI_ENDPOINT", endpoint),
                ("AZURE_OPENAI_DEPLOYMENT", deployment),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required Azure OpenAI settings: " + ", ".join(missing)
            )

        from openai import AzureOpenAI

        client = AzureOpenAI(api_key=key, azure_endpoint=endpoint, api_version=api_version)
        return cls(client, deployment)

    def classify(self, images: Sequence[bytes], config: Config) -> Classification:
        type_lines = "\n".join(f"- {dt.id}: {dt.description}" for dt in config.document_types)
        messages = [
            {
                "role": "system",
                "content": (
                    "You classify a scanned document for a German public authority. "
                    "Identify which configured document type it is. If it matches none, "
                    "set document_type to a short label for what it actually is (e.g. 'unknown')."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Configured document types:\n{type_lines}"},
                    {"type": "image_url", "image_url": {"url": _data_url(images[0])}},
                ],
            },
        ]
        completion = self._client.chat.completions.parse(
            model=self._deployment, messages=messages, response_format=Classification
        )
        return completion.choices[0].message.parsed

    def extract_and_validate(
        self, images: Sequence[bytes], doc_type: DocumentTypeConfig
    ) -> ExtractionOutcome:
        field_lines = "\n".join(
            f"- {f.name}: {f.description}" + (f" ({f.type_hint})" if f.type_hint else "")
            for f in doc_type.expected_fields
        )
        content = [
            {
                "type": "text",
                "text": (
                    f"Document type: {doc_type.id} — {doc_type.description}\n\n"
                    f"Criteria:\n{doc_type.criteria or '(none)'}\n\n"
                    f"Expected fields:\n{field_lines}\n\n"
                    "Extract each expected field with its value and per-field legibility "
                    "(legible / partial / illegible). List any missing or illegible required "
                    "field in deficiencies. Set validation_status to 'accepted' only if all "
                    "required fields are present and legible and the criteria are met; "
                    "otherwise 'incomplete'."
                ),
            }
        ]
        for image in images:
            content.append({"type": "image_url", "image_url": {"url": _data_url(image)}})

        messages = [
            {
                "role": "system",
                "content": (
                    "You validate and extract data from an official document for German "
                    "public administration. Return structured output only."
                ),
            },
            {"role": "user", "content": content},
        ]
        completion = self._client.chat.completions.parse(
            model=self._deployment, messages=messages, response_format=ExtractionOutcome
        )
        return completion.choices[0].message.parsed

    def scan(self, images: Sequence[bytes]) -> list[FieldResult]:
        """Extract all visible fields from a document without validation.

        Pending full implementation — scan mode on the Azure client is not yet
        wired up (see issue backlog). Raises if called in production.
        """
        raise NotImplementedError(
            "AzureModelClient.scan is not yet implemented. "
            "Use FakeModelClient in tests or implement this method."
        )

    def extract_targeted(
        self, images: Sequence[bytes], required_fields: Sequence[RequiredField]
    ) -> list[FieldResult]:
        """Extract specific requested fields only, no classification.

        Pending full implementation — targeted mode on the Azure client is not
        yet wired up (see issue backlog). Raises if called in production.
        """
        raise NotImplementedError(
            "AzureModelClient.extract_targeted is not yet implemented. "
            "Use FakeModelClient in tests or implement this method."
        )

    def analyze_antrag(
        self,
        results: Sequence[ValidationResult],
        images_per_result: Sequence[Sequence[bytes]],
    ) -> AntragsResult:
        """Cross-document analysis: check all sub-documents for genuine discrepancies.

        Builds a compact JSON summary of every sub-document (type, status, extracted
        fields, deficiencies) and appends the selected page images. The model is
        constrained to German output and must not assert a discrepancy unless at
        least two data-bearing documents carry comparable identity data.
        """
        docs_json = json.dumps(
            [_compact_doc(r) for r in results],
            ensure_ascii=False,
            indent=2,
        )

        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Eingereichte Dokumente (kompakte Zusammenfassung):\n"
                    f"{docs_json}\n\n"
                    "Prüfe die obigen Dokumente auf inhaltliche Widersprüche "
                    "(z. B. Namensabweichungen zwischen Ausweis und Mietvertrag). "
                    "Melde ausschließlich echte, belegbare Diskrepanzen. "
                    "Behaupte keine Diskrepanz, wenn nicht mindestens zwei Dokumente "
                    "vergleichbare Identitätsdaten enthalten. "
                    "Schreibe Befunde und Zusammenfassung auf Deutsch."
                ),
            }
        ]

        # Append selected page images (only those forwarded by the threshold logic).
        for imgs in images_per_result:
            for image in imgs:
                content.append({"type": "image_url", "image_url": {"url": _data_url(image)}})

        messages = [
            {
                "role": "system",
                "content": (
                    "Du bist ein Prüfsystem für deutsche Behörden. "
                    "Du analysierst mehrere eingereichte Dokumente auf inhaltliche Widersprüche. "
                    "Melde nur echte, belegbare Diskrepanzen — keine Vermutungen. "
                    "Behaupte keine Diskrepanz, wenn nicht mindestens zwei Dokumente "
                    "vergleichbare Identitätsdaten enthalten. "
                    "Gib Befunde (cross_document_findings) und Zusammenfassung (summary) "
                    "ausschließlich auf Deutsch aus."
                ),
            },
            {"role": "user", "content": content},
        ]

        completion = self._client.chat.completions.parse(
            model=self._deployment,
            messages=messages,
            response_format=AntragsResult,
        )
        return completion.choices[0].message.parsed
