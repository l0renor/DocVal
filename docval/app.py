"""FastAPI application factory (async job model, stateless)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .config import Config, ConfigError, load_config, parse_config
from .schemas import RequiredField
from .ingest import IngestError, IngestSettings, render_to_images
from .jobs import JobStore
from .model_client import ModelClient
from .pipeline import Pipeline

_VALID_SUBMISSION_TYPES = {"dokument", "antrag"}


def create_app(
    model_client: ModelClient,
    ingest_settings: IngestSettings | None = None,
    # Legacy: kept so existing test fixtures that pass config= still compile.
    config: Config | None = None,
) -> FastAPI:
    app = FastAPI(title="DocVerify")
    jobs = JobStore()
    ingest_settings = ingest_settings or IngestSettings()

    @app.post("/documents", status_code=202)
    async def submit_document(
        files: Annotated[list[UploadFile], File()],
        submission_type: Annotated[str, Form()] = "dokument",
        config_json: Annotated[str | None, Form(alias="config")] = None,
        required_fields_json: Annotated[str | None, Form(alias="required_fields")] = None,
    ):
        # --- validate submission_type ---
        if submission_type not in _VALID_SUBMISSION_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown submission_type {submission_type!r}. Must be one of: {sorted(_VALID_SUBMISSION_TYPES)}",
            )

        # --- validate file count for dokument ---
        if submission_type == "dokument":
            if not files:
                raise HTTPException(status_code=422, detail="At least one file is required.")
            if len(files) > 1:
                raise HTTPException(
                    status_code=422,
                    detail="A 'dokument' submission must contain exactly one file.",
                )

        # --- conflict check ---
        if config_json is not None and required_fields_json is not None:
            raise HTTPException(
                status_code=422,
                detail="Sending both 'config' and 'required_fields' is ambiguous. Use one or the other.",
            )

        # --- parse inline config if provided ---
        resolved_config: Config | None = config  # legacy fallback
        if config_json is not None:
            try:
                raw = json.loads(config_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=422, detail=f"config is not valid JSON: {exc}") from exc
            try:
                resolved_config = parse_config(raw)
            except ConfigError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        # --- parse required_fields if provided ---
        required_fields: list[RequiredField] | None = None
        if required_fields_json is not None:
            try:
                raw_fields = json.loads(required_fields_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=422, detail=f"required_fields is not valid JSON: {exc}") from exc
            try:
                required_fields = [RequiredField.model_validate(f) for f in raw_fields]
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"required_fields failed validation: {exc}") from exc

        # --- antrag-specific guards ---
        if submission_type == "antrag":
            if resolved_config is None and config_json is None:
                raise HTTPException(status_code=422, detail="An 'antrag' submission requires a 'config'.")
            if required_fields_json is not None:
                raise HTTPException(status_code=422, detail="An 'antrag' submission cannot use 'required_fields'.")

        # --- ingest + pipeline ---
        # Rendering and model calls are synchronous and slow; they run in the
        # threadpool so the event loop stays free for concurrent requests.
        uploads = [(f.filename, f.content_type, await f.read()) for f in files]

        def _render(filename, content_type, data):
            try:
                return render_to_images(filename, content_type, data, ingest_settings)
            except IngestError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        def _process() -> str:
            pipeline = Pipeline(resolved_config, model_client)

            if submission_type == "antrag":
                images_per_file = [_render(*upload) for upload in uploads]
                results, antrag_metadata = pipeline.run_antrag(images_per_file, resolved_config)
                return jobs.create_done_antrag(results, antrag_metadata)

            images = _render(*uploads[0])
            if required_fields is not None:
                try:
                    result = pipeline.run_targeted(images, required_fields)
                except NotImplementedError as exc:
                    raise HTTPException(status_code=501, detail=str(exc)) from exc
                return jobs.create_done_dokument(result)
            if resolved_config is None:
                try:
                    result = pipeline.run_scan(images)
                except NotImplementedError as exc:
                    raise HTTPException(status_code=501, detail=str(exc)) from exc
                return jobs.create_done_dokument(result)
            # Validate mode (inline or legacy config): one result per
            # sub-document — a bundled PDF must not drop segments.
            return jobs.create_done(pipeline.run(images))

        job_id = await run_in_threadpool(_process)
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        # Antrag shape.
        if job.antrag_metadata is not None:
            return {
                "status": job.status,
                "submission_type": job.submission_type,
                "results": job.results,
                "antrag_metadata": job.antrag_metadata,
            }

        # New dokument shape.
        if job.result is not None:
            return {
                "status": job.status,
                "submission_type": job.submission_type,
                "result": job.result,
            }

        # Validate mode: one result per sub-document.
        return {
            "status": job.status,
            "submission_type": job.submission_type,
            "results": job.results,
        }

    return app


def build_app(config_path: str | Path, model_client: ModelClient) -> FastAPI:
    """Load + schema-validate the config from disk, then build the app.

    Retained for the dev startup entrypoint; not used in tests.
    """
    _config = load_config(config_path)
    return create_app(model_client=model_client, config=_config)
