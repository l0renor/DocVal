"""In-memory job store for the async job model (short-lived, non-durable)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from .schemas import AntragsMetadata, ScanResult, TargetedResult, ValidationResult

_DokumentResult = ValidationResult | ScanResult | TargetedResult

_DEFAULT_TTL = 300  # 5 minutes


@dataclass
class _Entry:
    job: "Job"
    created_at: float


@dataclass
class Job:
    status: str
    submission_type: str
    result: ValidationResult | ScanResult | TargetedResult | None = None
    results: list[ValidationResult] | None = None
    antrag_metadata: AntragsMetadata | None = None


class JobStore:
    def __init__(
        self,
        ttl_seconds: float = _DEFAULT_TTL,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jobs: dict[str, _Entry] = {}
        self._ttl = ttl_seconds
        self._now = now

    def _purge(self) -> None:
        cutoff = self._now() - self._ttl
        expired = [jid for jid, entry in self._jobs.items() if entry.created_at < cutoff]
        for jid in expired:
            del self._jobs[jid]

    def _store(self, job: Job) -> str:
        self._purge()
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = _Entry(job=job, created_at=self._now())
        return job_id

    def create_done(self, results: list[ValidationResult]) -> str:
        """Validate mode: one result per sub-document of the upload."""
        return self._store(Job(status="done", submission_type="dokument", results=results))

    def create_done_dokument(self, result: _DokumentResult) -> str:
        """New dokument path: single result + submission_type in response."""
        return self._store(Job(status="done", submission_type="dokument", result=result))

    def create_done_antrag(
        self, results: list[ValidationResult], antrag_metadata: AntragsMetadata
    ) -> str:
        return self._store(Job(
            status="done",
            submission_type="antrag",
            results=results,
            antrag_metadata=antrag_metadata,
        ))

    def get(self, job_id: str) -> Job | None:
        entry = self._jobs.get(job_id)
        if entry is None:
            return None
        if self._now() - entry.created_at >= self._ttl:
            del self._jobs[job_id]
            return None
        return entry.job
