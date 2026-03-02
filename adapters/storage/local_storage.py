"""
adapters/storage/local_storage.py

Implements IFileStorage using the local filesystem.
To swap for S3: create s3_storage.py, implement IFileStorage, change container.py.
"""
import io
import os
from pathlib import Path
from typing import BinaryIO

from domain.errors import FileNotFoundError as DomainFileNotFound, FileStorageError
from ports import IFileStorage


# Maps MIME types to file extensions
MIME_TO_EXT = {
    "image/jpeg":       ".jpg",
    "image/png":        ".png",
    "image/webp":       ".webp",
    "image/heic":       ".heic",
    "video/mp4":        ".mp4",
    "video/quicktime":  ".mov",
    "video/avi":        ".avi",
    "application/pdf":  ".pdf",
}


class LocalFileStorage(IFileStorage):

    def __init__(self, base_dir: str):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    async def store(
        self,
        file_id: str,
        data: BinaryIO,
        mime_type: str,
    ) -> str:
        ext = MIME_TO_EXT.get(mime_type, ".bin")
        path = self._base / f"{file_id}{ext}"

        try:
            with open(path, "wb") as f:
                while chunk := data.read(1024 * 1024):
                    f.write(chunk)
        except OSError as e:
            # Clean up partial write
            path.unlink(missing_ok=True)
            raise FileStorageError(f"Failed to store file: {e}") from e

        return str(path)

    async def open(self, storage_path: str) -> tuple[BinaryIO, int]:
        path = Path(storage_path)
        if not path.exists():
            raise DomainFileNotFound(storage_path)
        size = path.stat().st_size
        return open(path, "rb"), size

    async def delete(self, storage_path: str) -> None:
        Path(storage_path).unlink(missing_ok=True)
