"""FastAPI application factory (async job model, stateless)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .config import Config, ConfigError, load_config, parse_config
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

        # --- ingest ---
        file = files[0]
        data = await file.read()
        try:
            images = render_to_images(file.filename, file.content_type, data, ingest_settings)
        except IngestError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        # --- run pipeline ---
        if resolved_config is None:
            # No config: scan mode (issue #16). For now, return a placeholder
            # until scan mode is implemented.
            raise HTTPException(status_code=422, detail="config is required for dokument validation (scan mode not yet implemented).")

        pipeline = Pipeline(resolved_config, model_client)
        results = pipeline.run(images)

        if config_json is not None:
            # New inline-config path: single-result shape { status, submission_type, result }.
            result = results[0] if results else None
            job_id = jobs.create_done_dokument(result)
        else:
            # Legacy path: server-side config, list shape { results[] }.
            # Kept so existing tests remain green until antrag slice (#18) lands.
            job_id = jobs.create_done(results)

        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        # New dokument shape.
        if job.result is not None:
            return {
                "status": job.status,
                "submission_type": job.submission_type,
                "result": job.result,
            }

        # Legacy shape (existing tests; will be migrated).
        return {"status": job.status, "results": job.results}

    return app


def build_app(config_path: str | Path, model_client: ModelClient) -> FastAPI:
    """Load + schema-validate the config from disk, then build the app.

    Retained for the dev startup entrypoint; not used in tests.
    """
    _config = load_config(config_path)
    return create_app(model_client=model_client, config=_config)
