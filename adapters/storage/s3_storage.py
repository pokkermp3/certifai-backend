"""
adapters/storage/s3_storage.py

Cloudflare R2 (S3-compatible) implementation of IFileStorage.
Drop-in replacement for LocalFileStorage — same interface, same method
signatures, zero changes required in any other file.

Uses aioboto3 (async wrapper around boto3).
A single session is reused across all requests — aioboto3 manages its own
internal connection pool per client context.

Requires: aioboto3, botocore  →  already in requirements.txt
"""
from __future__ import annotations

import io
from typing import BinaryIO

import aioboto3
from botocore.exceptions import ClientError

from domain.errors import FileNotFoundError as DomainFileNotFound, FileStorageError
from ports import IFileStorage

# Maps MIME types to file extensions — mirrors local_storage.py exactly
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


class S3FileStorage(IFileStorage):
    """
    Async S3-compatible file storage using aioboto3.
    Works with Cloudflare R2 and AWS S3 (same API, different endpoint_url).

    Files stored under:
      uploads/{file_id}{ext}      — original evidence files
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",    # "auto" is the correct value for Cloudflare R2
    ) -> None:
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        # Single session shared across all requests —
        # aioboto3 manages HTTP connection pooling internally per client context
        self._session = aioboto3.Session()

    def _client(self):
        """Return an async context manager that yields a configured S3 client."""
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name=self._region,
        )

    # ── IFileStorage interface ────────────────────────────────────────────────

    async def store(
        self,
        file_id: str,
        data: BinaryIO,
        mime_type: str,
    ) -> str:
        """
        Upload file to R2.
        Reads the BinaryIO stream fully before upload — same contract as
        LocalFileStorage which also reads the stream.
        Returns the storage key (opaque — callers never construct it themselves).
        """
        ext = MIME_TO_EXT.get(mime_type, ".bin")
        key = f"uploads/{file_id}{ext}"

        try:
            raw = data.read()
            async with self._client() as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=raw,
                    ContentType=mime_type,
                )
        except Exception as e:
            raise FileStorageError(f"Failed to store file in R2: {e}") from e

        return key

    async def open(self, storage_path: str) -> tuple[BinaryIO, int]:
        """
        Download file from R2 by its storage key.
        Returns (BytesIO handle, size_in_bytes) — same contract as LocalFileStorage.
        Raises DomainFileNotFound if the key does not exist in the bucket.
        """
        try:
            async with self._client() as s3:
                response = await s3.get_object(
                    Bucket=self._bucket,
                    Key=storage_path,
                )
                raw = await response["Body"].read()
        except ClientError as e:
            # R2 returns "NoSuchKey" on missing objects; some S3-compatible
            # stores return "404" — handle both
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise DomainFileNotFound(storage_path)
            raise FileStorageError(f"Failed to read file from R2: {e}") from e
        except Exception as e:
            raise FileStorageError(f"Failed to read file from R2: {e}") from e

        return io.BytesIO(raw), len(raw)

    async def delete(self, storage_path: str) -> None:
        """
        Remove a file from R2.
        S3 delete_object is a no-op if the key does not exist — intentionally
        silent, mirrors LocalFileStorage's unlink(missing_ok=True) behaviour.
        """
        try:
            async with self._client() as s3:
                await s3.delete_object(
                    Bucket=self._bucket,
                    Key=storage_path,
                )
        except Exception as e:
            raise FileStorageError(f"Failed to delete file from R2: {e}") from e
