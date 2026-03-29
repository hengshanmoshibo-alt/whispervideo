from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Settings
from .utils.srt import write_plain_text_from_whisper_json, write_srt_from_whisper_json


@dataclass(frozen=True)
class SubtitleRenderOptions:
    position: str
    font_size: int


def run_pipeline(
    settings: Settings,
    *,
    input_audio: Path,
    output_dir: Path,
    subtitle_options: SubtitleRenderOptions,
    on_step: Callable[[str, str], None] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_copy = output_dir / input_audio.name
    if audio_copy.resolve() != input_audio.resolve():
        shutil.copy2(input_audio, audio_copy)

    notify(on_step, "transcribing", "正在调用 Whisper 生成 JSON")
    transcript_json = run_whisper(settings, audio_copy, output_dir)

    notify(on_step, "building_srt", "正在根据 JSON 生成 SRT")
    subtitle_srt = output_dir / f"{audio_copy.stem}.srt"
    write_srt_from_whisper_json(transcript_json, subtitle_srt)
    plain_text = output_dir / f"{audio_copy.stem}.txt"
    write_plain_text_from_whisper_json(transcript_json, plain_text)

    notify(on_step, "rendering_video", "正在生成黑底视频")
    plain_video = output_dir / f"{audio_copy.stem}.mp4"
    audio_to_black_video(settings.ffmpeg_bin, audio_copy, plain_video)

    notify(on_step, "burning_subtitles", "正在烧录字幕视频")
    subtitle_video = output_dir / f"{audio_copy.stem}_sub.mp4"
    burn_subtitles(
        settings.ffmpeg_bin,
        plain_video,
        subtitle_srt,
        subtitle_video,
        position=subtitle_options.position,
        font_size=subtitle_options.font_size,
        margin_v=settings.default_subtitle_margin_v,
        outline=settings.default_subtitle_outline,
    )

    return {
        "audio": audio_copy,
        "json": transcript_json,
        "srt": subtitle_srt,
        "text": plain_text,
        "video": subtitle_video,
    }


def run_whisper(settings: Settings, input_audio: Path, output_dir: Path) -> Path:
    model_value = settings.whisper_model.strip()
    model_path = Path(model_value)
    model_arg = str(model_path.resolve()) if model_path.exists() else model_value
    cmd = [
        settings.whisper_python,
        "-m",
        "whisper",
        str(input_audio),
        "--model",
        model_arg,
        "--language",
        settings.whisper_language,
        "--task",
        "transcribe",
        "--word_timestamps",
        "True",
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
        "--verbose",
        "False",
    ]
    if not model_path.exists() and settings.whisper_model_dir.strip():
        cmd.extend(["--model_dir", settings.whisper_model_dir.strip()])
    subprocess.run(cmd, check=True)
    json_path = output_dir / f"{input_audio.stem}.json"
    if not json_path.exists():
        raise RuntimeError(f"Whisper 未生成 JSON 文件: {json_path}")
    return json_path


def audio_to_black_video(ffmpeg_bin: str, audio_path: Path, video_path: Path) -> None:
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1280x720:r=30",
        "-i",
        str(audio_path),
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(video_path),
    ]
    subprocess.run(cmd, check=True)


def burn_subtitles(
    ffmpeg_bin: str,
    video_in: Path,
    subtitle_srt: Path,
    video_out: Path,
    *,
    position: str,
    font_size: int,
    margin_v: int,
    outline: int,
) -> None:
    alignment = subtitle_alignment_value(position)
    force_style = (
        f"Alignment={alignment},"
        f"MarginV={margin_v},"
        f"Fontsize={font_size},"
        f"Outline={outline},"
        "Shadow=0"
    )
    subtitle_filter = (
        f"subtitles='{ffmpeg_filter_path(subtitle_srt)}':charenc=UTF-8:"
        f"force_style='{force_style}'"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_in),
        "-vf",
        subtitle_filter,
        "-c:a",
        "copy",
        str(video_out),
    ]
    subprocess.run(cmd, check=True)


def ffmpeg_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:")


def notify(on_step: Callable[[str, str], None] | None, step: str, message: str) -> None:
    if on_step is not None:
        on_step(step, message)


def subtitle_alignment_value(position: str) -> int:
    mapping = {
        "bottom": 2,
        "middle": 5,
        "top": 8,
    }
    return mapping.get((position or "").strip().lower(), 2)
