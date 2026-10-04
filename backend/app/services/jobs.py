"""In-memory job store with TTL and content-hash result cache.

Single-process only: run the API with one uvicorn worker. To scale horizontally,
swap this class for a Redis-backed implementation with the same interface.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    id: str
    doc_type: str
    mode: str
    filename: str
    cache_key: str
    status: str = "queued"  # queued | processing | completed | failed
    progress: float = 0.0
    message: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._jobs: dict[str, Job] = {}
        self._cache: dict[str, str] = {}  # cache_key -> completed job id
        self._lock = threading.Lock()

    def create(self, doc_type: str, mode: str, filename: str, cache_key: str) -> Job:
        with self._lock:
            self._evict_locked()
            job = Job(id=uuid.uuid4().hex, doc_type=doc_type, mode=mode,
                      filename=filename, cache_key=cache_key)
            self._jobs[job.id] = job
            return job

    def find_cached(self, cache_key: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(self._cache.get(cache_key, ""))
            return job if job and job.status == "completed" else None

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._evict_locked()
            return self._jobs.get(job_id)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ("queued", "processing"))

    def update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in fields.items():
                setattr(job, k, v)
            job.updated_at = time.time()
            if job.status == "completed":
                self._cache[job.cache_key] = job.id

    def _evict_locked(self) -> None:
        cutoff = time.time() - self._ttl
        for jid in [j.id for j in self._jobs.values()
                    if j.updated_at < cutoff and j.status in ("completed", "failed")]:
            job = self._jobs.pop(jid)
            if self._cache.get(job.cache_key) == jid:
                del self._cache[job.cache_key]
