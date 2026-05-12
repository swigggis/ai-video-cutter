from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class JobState:
    status: str = "queued"
    progress: int = 0
    message: str = "Waiting"
    output_filename: str | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create(self, job_id: str) -> JobState:
        with self._lock:
            state = JobState()
            self._jobs[job_id] = state
            return state

    def update(self, job_id: str, **kwargs: object) -> JobState:
        with self._lock:
            if job_id not in self._jobs:
                self._jobs[job_id] = JobState()
            state = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(state, key, value)
            return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)


job_store = JobStore()
