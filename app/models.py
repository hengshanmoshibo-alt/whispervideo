from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class SubtitleStyle(BaseModel):
    position: str = "bottom"
    font_size: int = Field(default=32, alias="fontSize")

    model_config = {
        "populate_by_name": True,
    }


class ArtifactLinks(BaseModel):
    audio_url: Optional[str] = Field(default=None, alias="audio")
    json_url: Optional[str] = Field(default=None, alias="json")
    srt_url: Optional[str] = Field(default=None, alias="srt")
    text_url: Optional[str] = Field(default=None, alias="text")
    video_url: Optional[str] = Field(default=None, alias="video")

    model_config = {
        "populate_by_name": True,
    }


class JobState(BaseModel):
    job_id: str = Field(alias="jobId")
    filename: str
    status: JobStatus
    step: str
    message: str
    error: Optional[str] = None
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle, alias="subtitleStyle")
    artifacts: ArtifactLinks = Field(default_factory=ArtifactLinks)

    model_config = {
        "populate_by_name": True,
    }
