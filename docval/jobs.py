"""In-memory job store for the async job model (short-lived, non-durable)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .schemas import ValidationResult


@dataclass
class Job:
    status: str
    submission_type: str
    result: ValidationResult | None = None
    # Legacy list field retained so existing callers still work during the
    # migration; new code uses `result` (dokument) or `results` (antrag).
    results: list[ValidationResult] | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create_done(self, results: list[ValidationResult]) -> str:
        """Legacy: stores a list of results (existing callers, will migrate)."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(status="done", submission_type="dokument", results=results)
        return job_id

    def create_done_dokument(self, result: ValidationResult) -> str:
        """New dokument path: single result + submission_type in response."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(status="done", submission_type="dokument", result=result)
        return job_id

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
