from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    cleaned = Path(name).name.strip().replace(" ", "_")
    return cleaned or "audio.mp3"


async def save_upload(upload: UploadFile, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    await upload.close()
