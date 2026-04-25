from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Settings
from .utils.srt import write_plain_text_from_whisper_json, write_srt_from_whisper_json


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


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
    media_copy = output_dir / input_audio.name
    if media_copy.resolve() != input_audio.resolve():
        shutil.copy2(input_audio, media_copy)

    media_type = detect_media_type(media_copy)
    transcription_audio = media_copy if media_type == "audio" else output_dir / f"{media_copy.stem}.mp3"

    if media_type == "video":
        notify(on_step, "extracting_audio", "正在从视频中提取音频")
        extract_audio_track(settings.ffmpeg_bin, media_copy, transcription_audio)

    notify(on_step, "transcribing", "正在调用 Whisper 生成 JSON")
    transcript_json = run_whisper(settings, transcription_audio, output_dir)

    notify(on_step, "building_srt", "正在根据 JSON 生成字幕文件")
    subtitle_srt = output_dir / f"{transcription_audio.stem}.srt"
    write_srt_from_whisper_json(transcript_json, subtitle_srt)
    plain_text = output_dir / f"{transcription_audio.stem}.txt"
    write_plain_text_from_whisper_json(transcript_json, plain_text)

    notify(on_step, "rendering_video", "正在准备视频画面")
    video_source = media_copy
    if media_type == "audio":
        video_source = output_dir / f"{transcription_audio.stem}.mp4"
        audio_to_black_video(settings.ffmpeg_bin, transcription_audio, video_source)

    notify(on_step, "burning_subtitles", "正在压制字幕视频")
    subtitle_video = output_dir / f"{transcription_audio.stem}_sub.mp4"
    burn_subtitles(
        settings.ffmpeg_bin,
        video_source,
        subtitle_srt,
        subtitle_video,
        position=subtitle_options.position,
        font_size=subtitle_options.font_size,
        margin_v=settings.default_subtitle_margin_v,
        outline=settings.default_subtitle_outline,
    )

    return {
        "audio": transcription_audio,
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
    if settings.whisper_device.strip() and settings.whisper_device.strip().lower() != "auto":
        cmd.extend(["--device", settings.whisper_device.strip()])
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


def extract_audio_track(ffmpeg_bin: str, media_path: Path, audio_path: Path) -> None:
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ab",
        "192k",
        str(audio_path),
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
    subtitle_ass = subtitle_srt.with_suffix(".ass")
    write_ass_from_srt(
        subtitle_srt,
        subtitle_ass,
        position=position,
        font_size=font_size,
        margin_v=margin_v,
        outline=outline,
    )
    subtitle_filter = f"subtitles='{ffmpeg_filter_path(subtitle_ass)}'"
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


def write_ass_from_srt(
    srt_path: Path,
    ass_path: Path,
    *,
    position: str,
    font_size: int,
    margin_v: int,
    outline: int,
) -> Path:
    alignment = subtitle_alignment_value(position)
    events = []
    for start, end, text in parse_srt_entries(srt_path):
        events.append(
            "Dialogue: 0,"
            f"{format_ass_time(start)},"
            f"{format_ass_time(end)},"
            "Default,,0,0,0,,"
            f"{escape_ass_text(text)}"
        )

    ass_text = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1280",
            "PlayResY: 720",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,"
            f"{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H7F000000,"
            f"0,0,0,0,100,100,0,0,1,{max(1, outline)},0,{alignment},40,40,{margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            *events,
            "",
        ]
    )
    ass_path.write_text(ass_text, encoding="utf-8")
    return ass_path


def parse_srt_entries(srt_path: Path) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    blocks = srt_path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[1].split("-->", 1)]
        text = "\n".join(lines[2:]).strip()
        if text:
            entries.append((parse_srt_time(start_raw), parse_srt_time(end_raw), text))
    return entries


def parse_srt_time(value: str) -> float:
    hours_raw, minutes_raw, rest = value.split(":", 2)
    seconds_raw, millis_raw = rest.split(",", 1)
    return (
        int(hours_raw) * 3600
        + int(minutes_raw) * 60
        + int(seconds_raw)
        + int(millis_raw) / 1000
    )


def format_ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100.0))
    hours = centis // 360000
    minutes = (centis % 360000) // 6000
    secs = (centis % 6000) // 100
    cs = centis % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


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


def detect_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    raise RuntimeError(f"Unsupported media type: {suffix}")
