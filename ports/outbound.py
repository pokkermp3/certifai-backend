"""
ports/outbound.py

All outbound port interfaces in one file.
Each interface is small and focused (Interface Segregation Principle).
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

from domain import Certificate, Hash


class IFileStorage(ABC):
    """
    File persistence port.
    Currently: local filesystem
    Future: swap for S3, GCS, Azure Blob without touching application code.
    """

    @abstractmethod
    async def store(
        self,
        file_id: str,
        data: BinaryIO,
        mime_type: str,
    ) -> str:
        """
        Save file data and return a storage path/key.
        The returned path is opaque — callers don't care where it's stored.
        """
        ...

    @abstractmethod
    async def open(self, storage_path: str) -> tuple[BinaryIO, int]:
        """
        Open a stored file for reading.
        Returns (file_handle, size_in_bytes).
        """
        ...

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Remove a file from storage."""
        ...


class IHasher(ABC):
    """
    Cryptographic hashing port.
    Currently: SHA-256
    Swap for SHA-3 or any other algorithm without changing application code.
    """

    @abstractmethod
    async def hash_bytes(self, data: bytes) -> Hash:
        """Compute hash of raw bytes."""
        ...

    @abstractmethod
    async def hash_file(self, storage_path: str) -> Hash:
        """
        Compute hash by streaming a file.
        Memory-safe for large video files — never loads entire file into RAM.
        """
        ...


class IPDFGenerator(ABC):
    """
    PDF certificate generation port.
    Currently: WeasyPrint
    Swap for ReportLab or any other engine without changing application code.
    """

    @abstractmethod
    async def generate(
        self,
        certificate: Certificate,
    ) -> str:
        """
        Generate a PDF certificate and return its storage path.
        The certificate contains: hashes, GPS, device info, QR code.
        """
        ...
