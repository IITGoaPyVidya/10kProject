"""In-memory store for multi-agent research runs, with an append-only event log for live UI updates.

Single-process only (like JobStore). Swap for Redis/Postgres to scale horizontally.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

MAX_EVENTS = 2000


@dataclass
class ResearchJob:
    id: str
    ticker: str
    company: str
    horizon: str
    status: str = "queued"  # queued | running | completed | failed
    agents: dict[str, dict] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    reports: dict[str, dict] = field(default_factory=dict)
    final: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ResearchStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._jobs: dict[str, ResearchJob] = {}
        self._lock = threading.Lock()

    def create(self, ticker: str, company: str, horizon: str, agents: dict[str, dict]) -> ResearchJob:
        with self._lock:
            self._evict_locked()
            job = ResearchJob(id=uuid.uuid4().hex, ticker=ticker, company=company, horizon=horizon,
                              agents={n: {"status": "pending", **meta} for n, meta in agents.items()})
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> ResearchJob | None:
        with self._lock:
            self._evict_locked()
            return self._jobs.get(job_id)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ("queued", "running"))

    def snapshot(self, job_id: str, since: int) -> dict | None:
        """Consistent copy of the job for the API (events after index `since`)."""
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None:
                return None
            finished = sum(1 for a in j.agents.values() if a["status"] in ("done", "skipped", "failed"))
            return {
                "id": j.id, "ticker": j.ticker, "company": j.company, "horizon": j.horizon, "status": j.status,
                "progress": 1.0 if j.status == "completed" else round(finished / max(len(j.agents), 1) * 0.95, 3),
                "agents": {k: dict(v) for k, v in j.agents.items()},
                "events": j.events[since:], "next_index": len(j.events),
                "reports": dict(j.reports), "final": j.final, "error": j.error,
                "started_at": j.created_at, "elapsed_s": round(time.time() - j.created_at, 1),
            }

    def set_status(self, job_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.status, j.error, j.updated_at = status, error, time.time()

    def emit(self, job_id: str, agent: str, message: str, level: str = "info", kind: str = "log",
             **fields: Any) -> None:
        """Append a log event and, for lifecycle kinds, update the agent's status."""
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None:
                return
            if len(j.events) < MAX_EVENTS:
                j.events.append({"i": len(j.events), "ts": round(time.time() - j.created_at, 1),
                                 "agent": agent, "level": level, "kind": kind, "message": message})
            a = j.agents.get(agent)
            if a is not None:
                if kind == "agent_start":
                    a["status"] = "working"
                elif kind == "agent_done":
                    a.update(status="done", **{k: v for k, v in fields.items() if k in ("rating", "score", "confidence")})
                    a["message"] = message
                elif kind == "agent_skipped":
                    a.update(status="skipped", message=message)
                elif kind == "agent_failed":
                    a.update(status="failed", message=message)
            j.updated_at = time.time()

    def set_report(self, job_id: str, name: str, report: dict) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.reports[name] = report

    def complete(self, job_id: str, final: dict | None) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.final, j.status, j.updated_at = final, "completed", time.time()

    def _evict_locked(self) -> None:
        cutoff = time.time() - self._ttl
        for jid in [j.id for j in self._jobs.values() if j.updated_at < cutoff and j.status in ("completed", "failed")]:
            del self._jobs[jid]
