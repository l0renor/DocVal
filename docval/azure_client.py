"""Azure GPT-5.5 implementation of the ModelClient interface.

The Azure OpenAI SDK client is injected (constructor) so tests run offline;
`from_env()` builds the real client from environment variables (a local `.env`
is loaded if present). Both calls use structured outputs (Pydantic
`response_format`) so responses always conform to the schemas.
"""

from __future__ import annotations

import base64
import os
from typing import Mapping, Sequence

from .config import Config, ConfigError, DocumentTypeConfig
from .schemas import Classification, ExtractionOutcome

DEFAULT_API_VERSION = "2024-10-21"


def _data_url(image: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"


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
