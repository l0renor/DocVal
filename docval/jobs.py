"""In-memory job store for the async job model (short-lived, non-durable)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .schemas import AntragsMetadata, ValidationResult


@dataclass
class Job:
    status: str
    submission_type: str
    result: ValidationResult | None = None
    results: list[ValidationResult] | None = None
    antrag_metadata: AntragsMetadata | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create_done(self, results: list[ValidationResult]) -> str:
        """Validate mode: one result per sub-document of the upload."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(status="done", submission_type="dokument", results=results)
        return job_id

    def create_done_dokument(self, result: ValidationResult) -> str:
        """New dokument path: single result + submission_type in response."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(status="done", submission_type="dokument", result=result)
        return job_id

    def create_done_antrag(
        self, results: list[ValidationResult], antrag_metadata: AntragsMetadata
    ) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(
            status="done",
            submission_type="antrag",
            results=results,
            antrag_metadata=antrag_metadata,
        )
        return job_id

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
