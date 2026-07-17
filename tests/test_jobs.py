"""JobStore must not leak memory indefinitely.

Jobs are evicted after a configurable TTL. `now` is injectable (same pattern
as `today` in Pipeline) so tests don't need real sleeps.
"""

from docval.jobs import JobStore
from docval.schemas import (
    AntragsMetadata,
    Classification,
    ValidationResult,
    ValidationStatus,
)


def _result():
    return ValidationResult(
        validation_status=ValidationStatus.ACCEPTED,
        confidence=1.0,
        classification=Classification(document_type="personalausweis"),
    )


def _monotonic(value):
    return lambda: value


def test_job_is_retrievable_before_ttl_expires():
    store = JobStore(ttl_seconds=60, now=_monotonic(0.0))
    job_id = store.create_done([_result()])
    # Retrieve at t=59 — still within TTL.
    store._now = _monotonic(59.0)
    assert store.get(job_id) is not None


def test_job_is_evicted_after_ttl_expires():
    store = JobStore(ttl_seconds=60, now=_monotonic(0.0))
    job_id = store.create_done([_result()])
    # Retrieve at t=61 — TTL elapsed.
    store._now = _monotonic(61.0)
    assert store.get(job_id) is None


def test_expired_jobs_are_purged_from_store():
    store = JobStore(ttl_seconds=60, now=_monotonic(0.0))
    store.create_done([_result()])
    store.create_done([_result()])
    assert len(store._jobs) == 2

    store._now = _monotonic(61.0)
    # Trigger a new creation — purge should run and evict the two old entries.
    store.create_done([_result()])
    assert len(store._jobs) == 1
