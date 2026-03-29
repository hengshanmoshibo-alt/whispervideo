from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict

from .models import ArtifactLinks, JobState, JobStatus, SubtitleStyle


class JobRepository:
    def __init__(self, jobs_dir: Path) -> None:
        self.jobs_dir = jobs_dir
        self._lock = threading.Lock()
        self._items: Dict[str, JobState] = {}

    def ensure_dirs(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create(self, job_id: str, filename: str, subtitle_style: SubtitleStyle) -> JobState:
        state = JobState(
            jobId=job_id,
            filename=filename,
            status=JobStatus.queued,
            step="queued",
            message="任务已创建，等待处理",
            subtitleStyle=subtitle_style,
            artifacts=ArtifactLinks(),
        )
        self.save(state)
        return state

    def save(self, state: JobState) -> JobState:
        with self._lock:
            self._items[state.job_id] = state
            self.jobs_dir.mkdir(parents=True, exist_ok=True)
            path = self.jobs_dir / f"{state.job_id}.json"
            path.write_text(
                json.dumps(state.model_dump(by_alias=True), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            state = self._items.get(job_id)
            if state is not None:
                return state
        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        state = JobState.model_validate(data)
        with self._lock:
            self._items[job_id] = state
        return state

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        step: str | None = None,
        message: str | None = None,
        error: str | None = None,
        artifacts: ArtifactLinks | None = None,
    ) -> JobState:
        state = self.get(job_id)
        if state is None:
            raise KeyError(job_id)
        payload = state.model_dump(by_alias=True)
        if status is not None:
            payload["status"] = status
        if step is not None:
            payload["step"] = step
        if message is not None:
            payload["message"] = message
        if error is not None:
            payload["error"] = error
        if artifacts is not None:
            payload["artifacts"] = artifacts.model_dump()
        next_state = JobState.model_validate(payload)
        return self.save(next_state)
