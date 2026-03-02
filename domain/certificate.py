"""
domain/certificate.py

The heart of CertifAI. Contains the Certificate entity and all value objects.
This file imports NOTHING outside the Python standard library.
Every business rule lives here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Value Objects ─────────────────────────────────────────────────────────────
# Value objects are immutable. Two value objects with the same data are equal.
# They validate themselves on creation — invalid state is impossible.

@dataclass(frozen=True)
class Hash:
    """
    A SHA-256 hexadecimal digest.
    Immutable and self-validating — you cannot create an invalid Hash.
    """
    value: str

    def __post_init__(self):
        cleaned = self.value.strip().lower()
        # frozen=True means we can't assign directly, use object.__setattr__
        object.__setattr__(self, "value", cleaned)

        if len(cleaned) != 64:
            raise ValueError(
                f"Hash must be 64 hex characters, got {len(cleaned)}"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", cleaned):
            raise ValueError("Hash must contain only hex characters (0-9, a-f)")

    def matches(self, other: "Hash") -> bool:
        return self.value == other.value

    def short(self) -> str:
        """First 16 chars — useful for display."""
        return self.value[:16] + "..."

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class GPSCoordinates:
    """
    GPS fix at the moment of capture.
    Validated on creation — invalid coordinates are impossible.
    """
    latitude: float
    longitude: float
    accuracy_meters: float = 0.0

    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValueError(
                f"Latitude {self.latitude} out of range [-90, 90]"
            )
        if not (-180 <= self.longitude <= 180):
            raise ValueError(
                f"Longitude {self.longitude} out of range [-180, 180]"
            )

    def maps_url(self) -> str:
        return (
            f"https://maps.google.com/?q="
            f"{self.latitude:.6f},{self.longitude:.6f}"
        )

    def __str__(self) -> str:
        return f"{self.latitude:.6f}, {self.longitude:.6f}"


@dataclass(frozen=True)
class DeviceInfo:
    """Metadata about the capture device."""
    device_id: str        # anonymous UUID per device install
    model: str            # e.g. "iPhone 15 Pro"
    os_version: str       # e.g. "iOS 17.4"
    app_version: str      # e.g. "1.0.0"


@dataclass(frozen=True)
class FileInfo:
    """Metadata about the certified file."""
    name: str
    size_bytes: int
    mime_type: str

    @property
    def file_type(self) -> "FileType":
        return FileType.from_mime(self.mime_type)

    @property
    def size_human(self) -> str:
        """Human readable file size."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class FileType(str, Enum):
    IMAGE    = "image"
    VIDEO    = "video"
    DOCUMENT = "document"
    UNKNOWN  = "unknown"

    @classmethod
    def from_mime(cls, mime: str) -> "FileType":
        if mime.startswith("image/"):
            return cls.IMAGE
        if mime.startswith("video/"):
            return cls.VIDEO
        if mime == "application/pdf":
            return cls.DOCUMENT
        return cls.UNKNOWN


class CertificateStatus(str, Enum):
    PENDING_UPLOAD = "pending_upload"   # hash registered, file not yet uploaded
    CERTIFIED      = "certified"        # hashes match, integrity confirmed
    HASH_MISMATCH  = "hash_mismatch"    # hashes differ — file was tampered


# ── Certificate ID ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CertificateID:
    value: str

    def __post_init__(self):
        if not self.value.strip():
            raise ValueError("CertificateID cannot be empty")

    def __str__(self) -> str:
        return self.value


# ── Certificate Entity (Aggregate Root) ───────────────────────────────────────
# This is the most important class in the entire codebase.
# All business rules around certification live here.
# Private attributes + methods enforce invariants — invalid state is impossible.

class Certificate:
    """
    The Certificate aggregate root.

    Lifecycle:
      1. Created via Certificate.register() — status: PENDING_UPLOAD
         (device hash is locked in at this point)
      2. Transitioned via .certify() after file upload
         (server re-hashes and compares)
         → CERTIFIED if hashes match
         → HASH_MISMATCH if they differ

    The trust chain:
      Device hash (computed on phone before upload)
        == Server hash (computed on server after upload)
      → File has not been tampered with
    """

    def __init__(
        self,
        id: CertificateID,
        case_id: str,
        file_info: FileInfo,
        device_hash: Hash,
        gps: Optional[GPSCoordinates],
        device: DeviceInfo,
        captured_at: datetime,
        status: CertificateStatus = CertificateStatus.PENDING_UPLOAD,
        server_hash: Optional[Hash] = None,
        certified_at: Optional[datetime] = None,
        storage_path: str = "",
        pdf_path: str = "",
    ):
        # All attributes are private — accessed only via properties
        self._id           = id
        self._case_id      = case_id
        self._file_info    = file_info
        self._device_hash  = device_hash
        self._gps          = gps
        self._device       = device
        self._captured_at  = captured_at
        self._status       = status
        self._server_hash  = server_hash
        self._certified_at = certified_at
        self._storage_path = storage_path
        self._pdf_path     = pdf_path

    # ── Factory methods ───────────────────────────────────────────────────────
    # These are the ONLY intended ways to create a Certificate.
    # __init__ accepts all fields so the repository can call reconstitute(),
    # but application code must always go through register() or reconstitute().

    @classmethod
    def register(
        cls,
        id: CertificateID,
        case_id: str,
        file_info: FileInfo,
        device_hash: Hash,
        gps: Optional[GPSCoordinates],
        device: DeviceInfo,
        captured_at: datetime,
    ) -> "Certificate":
        """
        Create a brand-new certificate in PENDING_UPLOAD state.
        The device hash is the trust anchor — locked in before any file transfer.
        Use this when a mobile device registers a new capture.
        """
        return cls(
            id=id,
            case_id=case_id,
            file_info=file_info,
            device_hash=device_hash,
            gps=gps,
            device=device,
            captured_at=captured_at,
        )

    @classmethod
    def reconstitute(
        cls,
        id: CertificateID,
        case_id: str,
        file_info: FileInfo,
        device_hash: Hash,
        gps: Optional[GPSCoordinates],
        device: DeviceInfo,
        captured_at: datetime,
        status: CertificateStatus,
        server_hash: Optional[Hash] = None,
        certified_at: Optional[datetime] = None,
        storage_path: str = "",
        pdf_path: str = "",
    ) -> "Certificate":
        """
        Rebuild a Certificate from persisted state (e.g. from a database row).
        Only the repository adapter should call this method.
        Unlike register(), this does not enforce PENDING_UPLOAD as the initial state
        because it is restoring an already-existing lifecycle state.
        """
        return cls(
            id=id,
            case_id=case_id,
            file_info=file_info,
            device_hash=device_hash,
            gps=gps,
            device=device,
            captured_at=captured_at,
            status=status,
            server_hash=server_hash,
            certified_at=certified_at,
            storage_path=storage_path,
            pdf_path=pdf_path,
        )

    # ── Business methods ──────────────────────────────────────────────────────

    def certify(self, server_hash: Hash, storage_path: str) -> None:
        """
        Transition certificate to CERTIFIED or HASH_MISMATCH state.

        This is the core business rule:
        - Server independently re-hashes the uploaded file
        - If it matches the device hash → file is authentic → CERTIFIED
        - If it differs → file was modified after capture → HASH_MISMATCH

        Raises:
            ValueError: if certificate is not in PENDING_UPLOAD state
        """
        if self._status != CertificateStatus.PENDING_UPLOAD:
            raise ValueError(
                f"Cannot certify a certificate in '{self._status}' state. "
                f"Only PENDING_UPLOAD certificates can be certified."
            )

        self._server_hash  = server_hash
        self._storage_path = storage_path
        self._certified_at = datetime.now(timezone.utc)

        if self._device_hash.matches(server_hash):
            self._status = CertificateStatus.CERTIFIED
        else:
            self._status = CertificateStatus.HASH_MISMATCH

    def set_pdf_path(self, path: str) -> None:
        """Record the location of the generated PDF certificate."""
        self._pdf_path = path

    # ── Business queries ──────────────────────────────────────────────────────

    def is_integrity_verified(self) -> bool:
        """True only if server confirmed the file was not modified after capture."""
        return (
            self._status == CertificateStatus.CERTIFIED
            and self._server_hash is not None
            and self._device_hash.matches(self._server_hash)
        )

    def verification_message(self) -> str:
        """
        Human-readable summary of this certificate's integrity status.
        Business logic about what a result means belongs in the domain,
        not scattered across use cases or HTTP handlers.
        """
        if self.is_integrity_verified():
            return "File integrity confirmed. Device hash matches server hash."
        return "WARNING: Hash mismatch detected. File may have been altered after capture."

    def has_gps(self) -> bool:
        return self._gps is not None

    def has_pdf(self) -> bool:
        return bool(self._pdf_path)

    # ── Read-only properties ──────────────────────────────────────────────────
    # Immutable view into the certificate state.
    # No setters — state changes only via business methods above.

    @property
    def id(self) -> CertificateID:
        return self._id

    @property
    def case_id(self) -> str:
        return self._case_id

    @property
    def file_info(self) -> FileInfo:
        return self._file_info

    @property
    def device_hash(self) -> Hash:
        return self._device_hash

    @property
    def server_hash(self) -> Optional[Hash]:
        return self._server_hash

    @property
    def gps(self) -> Optional[GPSCoordinates]:
        return self._gps

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def captured_at(self) -> datetime:
        return self._captured_at

    @property
    def certified_at(self) -> Optional[datetime]:
        return self._certified_at

    @property
    def status(self) -> CertificateStatus:
        return self._status

    @property
    def storage_path(self) -> str:
        return self._storage_path

    @property
    def pdf_path(self) -> str:
        return self._pdf_path

    def __repr__(self) -> str:
        return (
            f"Certificate(id={self._id}, "
            f"status={self._status}, "
            f"file={self._file_info.name})"
        )
