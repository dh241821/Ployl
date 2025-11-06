from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


async def save_upload(
    file: UploadFile, base_dir: Path, *subdirectories: str | int | Path
) -> Path:
    parts: list[str] = [str(item) for item in subdirectories]

    destination_dir = base_dir.joinpath(*parts)
    destination_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "").suffix
    unique_name = f"{uuid4().hex}{suffix}"
    destination_path = destination_dir / unique_name

    async with file as upload:
        with destination_path.open("wb") as buffer:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)

    return destination_path.relative_to(base_dir)


__all__ = ["save_upload"]
