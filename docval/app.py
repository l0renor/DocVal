"""FastAPI application factory (async job model, stateless)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from .config import Config, load_config
from .ingest import IngestError, IngestSettings, render_to_images
from .jobs import JobStore
from .model_client import ModelClient
from .pipeline import Pipeline


def create_app(
    config: Config,
    model_client: ModelClient,
    ingest_settings: IngestSettings | None = None,
) -> FastAPI:
    app = FastAPI(title="DocVerify")
    pipeline = Pipeline(config, model_client)
    jobs = JobStore()
    ingest_settings = ingest_settings or IngestSettings()

    @app.post("/documents", status_code=202)
    async def submit_document(file: UploadFile = File(...)):
        data = await file.read()
        try:
            images = render_to_images(file.filename, file.content_type, data, ingest_settings)
        except IngestError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        results = pipeline.run(images)
        job_id = jobs.create_done(results)
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"status": job.status, "results": job.results}

    return app


def build_app(config_path: str | Path, model_client: ModelClient) -> FastAPI:
    """Load + schema-validate the config from disk, then build the app.

    A malformed config raises ConfigError here — failing loudly on startup.
    """
    return create_app(load_config(config_path), model_client)
