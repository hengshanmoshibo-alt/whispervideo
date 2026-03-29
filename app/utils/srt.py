from __future__ import annotations

import json
from pathlib import Path


def write_srt_from_whisper_json(
    json_path: Path,
    srt_path: Path,
    pause_threshold: float = 0.6,
    max_chars: int = 90,
) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    words = []
    for segment in data.get("segments", []):
        for word in segment.get("words", []):
            text = str(word.get("word", "")).strip()
            if text:
                words.append((text, float(word["start"]), float(word["end"])))

    if not words:
        raise RuntimeError(f"Whisper JSON 中没有可用的单词时间戳: {json_path}")

    entries = []
    current_words = []
    start_time = words[0][1]
    last_end = words[0][2]

    for text, start, end in words:
        gap = start - last_end
        current_len = sum(len(item[0]) for item in current_words) + max(0, len(current_words) - 1)
        if current_words and (gap >= pause_threshold or current_len + 1 + len(text) > max_chars):
            entries.append((start_time, last_end, " ".join(item[0] for item in current_words)))
            current_words = []
            start_time = start
        current_words.append((text, start, end))
        last_end = end

    if current_words:
        entries.append((start_time, last_end, " ".join(item[0] for item in current_words)))

    srt_path.write_text(build_srt_text(entries), encoding="utf-8")
    return srt_path


def write_plain_text_from_whisper_json(json_path: Path, text_path: Path) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    for segment in data.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if text:
            lines.append(text)
    if not lines:
        full_text = str(data.get("text", "")).strip()
        if full_text:
            lines.append(full_text)
    text_path.write_text("\n".join(lines), encoding="utf-8")
    return text_path


def build_srt_text(entries: list[tuple[float, float, str]]) -> str:
    lines: list[str] = []
    for index, (start, end, text) in enumerate(entries, start=1):
        lines.append(str(index))
        lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000.0))
    hours = millis // 3600000
    minutes = (millis % 3600000) // 60000
    secs = (millis % 60000) // 1000
    ms = millis % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
