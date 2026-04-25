from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_root: Path
    host: str
    port: int
    workspace: Path
    uploads_dir: Path
    jobs_dir: Path
    outputs_dir: Path
    whisper_python: str
    whisper_model: str
    whisper_model_dir: str
    whisper_language: str
    whisper_device: str
    ffmpeg_bin: str
    default_subtitle_position: str
    default_subtitle_font_size: int
    default_subtitle_margin_v: int
    default_subtitle_outline: int


def load_settings() -> Settings:
    app_root = Path(__file__).resolve().parent.parent
    env_file = app_root / ".env"
    env_map = load_dotenv(env_file)
    workspace_value = env_str("WHISPERVIDEO_WORKSPACE", "workspace")
    if workspace_value == "workspace":
        workspace_value = env_map.get("WHISPERVIDEO_WORKSPACE", workspace_value)
    workspace_path = Path(workspace_value)
    workspace = workspace_path if workspace_path.is_absolute() else app_root / workspace_path
    workspace = workspace.resolve()
    return Settings(
        app_root=app_root,
        host=env_value(env_map, "WHISPERVIDEO_HOST", "127.0.0.1"),
        port=int(env_value(env_map, "WHISPERVIDEO_PORT", "8000")),
        workspace=workspace,
        uploads_dir=workspace / "uploads",
        jobs_dir=workspace / "jobs",
        outputs_dir=workspace / "outputs",
        whisper_python=env_value(env_map, "WHISPERVIDEO_WHISPER_PYTHON", "python"),
        whisper_model=env_value(env_map, "WHISPERVIDEO_WHISPER_MODEL", "small"),
        whisper_model_dir=env_value(env_map, "WHISPERVIDEO_WHISPER_MODEL_DIR", ""),
        whisper_language=env_value(env_map, "WHISPERVIDEO_WHISPER_LANGUAGE", "en"),
        whisper_device=env_value(env_map, "WHISPERVIDEO_WHISPER_DEVICE", "auto"),
        ffmpeg_bin=env_value(env_map, "WHISPERVIDEO_FFMPEG_BIN", "ffmpeg"),
        default_subtitle_position=env_value(env_map, "WHISPERVIDEO_SUBTITLE_POSITION", "bottom"),
        default_subtitle_font_size=int(env_value(env_map, "WHISPERVIDEO_SUBTITLE_FONT_SIZE", "32")),
        default_subtitle_margin_v=int(env_value(env_map, "WHISPERVIDEO_SUBTITLE_MARGIN_V", "40")),
        default_subtitle_outline=int(env_value(env_map, "WHISPERVIDEO_SUBTITLE_OUTLINE", "1")),
    )


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    trimmed = value.strip()
    return trimmed if trimmed else default


def env_value(env_map: dict[str, str], name: str, default: str) -> str:
    runtime_value = os.getenv(name)
    if runtime_value is not None and runtime_value.strip():
        return runtime_value.strip()
    file_value = env_map.get(name)
    if file_value is not None and file_value.strip():
        return file_value.strip()
    return default


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values
