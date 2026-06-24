"""In-memory job store for the async job model (short-lived, non-durable)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .schemas import ValidationResult


@dataclass
class Job:
    status: str
    results: list[ValidationResult] | None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create_done(self, results: list[ValidationResult]) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = Job(status="done", results=results)
        return job_id

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
