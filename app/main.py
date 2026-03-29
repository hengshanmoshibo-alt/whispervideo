from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .jobs import JobRepository
from .models import ArtifactLinks, JobState, JobStatus, SubtitleStyle
from .pipeline import SubtitleRenderOptions, run_pipeline
from .utils.files import ensure_dir, safe_filename, save_upload


settings = load_settings()
app = FastAPI(title="WhisperVideo")
job_repo = JobRepository(settings.jobs_dir)


def prepare_workspace() -> None:
    ensure_dir(settings.workspace)
    ensure_dir(settings.uploads_dir)
    ensure_dir(settings.jobs_dir)
    ensure_dir(settings.outputs_dir)
    job_repo.ensure_dirs()


@app.on_event("startup")
def on_startup() -> None:
    prepare_workspace()


@app.post("/api/jobs", response_model=JobState)
async def create_job(
    audio: UploadFile = File(...),
    subtitle_position: str | None = Form(default=None, alias="subtitlePosition"),
    subtitle_font_size: int | None = Form(default=None, alias="subtitleFontSize"),
) -> JobState:
    filename = safe_filename(audio.filename or "audio.mp3")
    if not filename.lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="当前版本只支持上传 mp3 文件")

    resolved_position = normalize_subtitle_position(
        subtitle_position or settings.default_subtitle_position
    )
    resolved_font_size = normalize_subtitle_font_size(
        subtitle_font_size or settings.default_subtitle_font_size
    )
    job_id = uuid.uuid4().hex
    upload_dir = ensure_dir(settings.uploads_dir / job_id)
    input_path = upload_dir / filename
    await save_upload(audio, input_path)

    subtitle_style = SubtitleStyle(
        position=resolved_position,
        fontSize=resolved_font_size,
    )
    state = job_repo.create(job_id, filename, subtitle_style)
    thread = threading.Thread(
        target=run_job,
        args=(job_id, input_path),
        daemon=True,
    )
    thread.start()
    return state


@app.get("/api/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str) -> JobState:
    state = job_repo.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state


@app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
def get_artifact(job_id: str, artifact_name: str) -> FileResponse:
    state = job_repo.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    path = resolve_artifact_path(job_id, artifact_name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="产物不存在")
    return FileResponse(path)


static_dir = settings.app_root / "app" / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def run_job(job_id: str, input_path: Path) -> None:
    try:
        job_repo.update(job_id, status=JobStatus.running, step="starting", message="任务开始执行")
        output_dir = ensure_dir(settings.outputs_dir / job_id)
        current_state = job_repo.get(job_id)
        if current_state is None:
            raise RuntimeError("任务状态不存在")
        artifacts = run_pipeline(
            settings,
            input_audio=input_path,
            output_dir=output_dir,
            subtitle_options=SubtitleRenderOptions(
                position=current_state.subtitle_style.position,
                font_size=current_state.subtitle_style.font_size,
            ),
            on_step=lambda step, message: job_repo.update(
                job_id,
                status=JobStatus.running,
                step=step,
                message=message,
            ),
        )
        links = ArtifactLinks(
            audio=f"/api/jobs/{job_id}/artifacts/audio",
            json=f"/api/jobs/{job_id}/artifacts/json",
            srt=f"/api/jobs/{job_id}/artifacts/srt",
            text=f"/api/jobs/{job_id}/artifacts/text",
            video=f"/api/jobs/{job_id}/artifacts/video",
        )
        job_repo.update(
            job_id,
            status=JobStatus.succeeded,
            step="done",
            message="处理完成",
            artifacts=links,
        )
    except Exception as exc:
        job_repo.update(
            job_id,
            status=JobStatus.failed,
            step="failed",
            message="处理失败",
            error=str(exc),
        )


def resolve_artifact_path(job_id: str, artifact_name: str) -> Path | None:
    output_dir = settings.outputs_dir / job_id
    candidates = {
        "audio": list(output_dir.glob("*.mp3")),
        "json": list(output_dir.glob("*.json")),
        "srt": list(output_dir.glob("*.srt")),
        "text": list(output_dir.glob("*.txt")),
        "video": list(output_dir.glob("*_sub.mp4")),
    }
    items = candidates.get(artifact_name)
    if not items:
        return None
    return sorted(items)[0]


def normalize_subtitle_position(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in {"top", "middle", "bottom"}:
        return settings.default_subtitle_position
    return normalized


def normalize_subtitle_font_size(value: int) -> int:
    if value < 16:
        return 16
    if value > 96:
        return 96
    return value
