# DocVerify (DocVal)

Configurable, stateless, API-first **validate-and-extract** service for German
public administration. Submit a document; DocVerify classifies it, checks
required content, and returns a standardized structured result. It **reports**
the verdict — it never filters, blocks, or stores documents. Communication with
citizens (Nachforderungen) is handled by other systems.

See [issue #2](https://github.com/l0renor/DocVal/issues/2) for the full PRD and
the slice issues (#3–#8) for the build plan.

## Stack

Python 3.14 · FastAPI · Pydantic · Azure OpenAI (GPT-5.5) · `uv`

## Develop

```sh
uv sync
uv run pytest        # offline — the model client is faked, no Azure calls
```

## Run against Azure

The model deployment/hosting is provided externally; supply credentials via a
local `.env` (copied from `.env.example`, git-ignored):

```sh
cp .env.example .env   # then fill in AZURE_OPENAI_* values
uv run uvicorn --factory docval.main:create
```

API (async job model):

- `POST /documents` (multipart file) → `202 {"job_id": "..."}`
- `GET /jobs/{job_id}` → `{"status": "done", "results": [ { ... } ]}`
  — `results` is a list with one validation result per detected sub-document
  (a bundled PDF is segmented into individual documents; a single document
  yields a one-element list).
- OpenAPI docs at `/docs`.

## Configuration

`config.example.yaml` defines document types with structured keys and
natural-language values (edited by Fachaufsichten, schema-validated on load).
