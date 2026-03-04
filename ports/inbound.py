"""
ports/inbound.py

Inbound port interfaces — what the application exposes to the outside world.

The HTTP adapter depends on THESE interfaces, not on the concrete use case
classes. This completes the hexagonal boundary on both sides:

  HTTP handler → IXxxUseCase (inbound port) → XxxUseCase → outbound ports → adapters

Without this, the HTTP layer depends on concrete application classes,
which violates DIP at the inbound boundary.

SRP: each interface covers exactly one use case.
ISP: handlers receive only the interface they need, not a fat combined one.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain import Certificate, CertificateStatus


# ── Shared data objects ───────────────────────────────────────────────────────
# Defined here so both inbound ports and application layer share the same types.

@dataclass(frozen=True)
class RegisterCaptureCommand:
    """
    Sent by the mobile app immediately after capture.
    Frozen — commands are immutable once created.
    """
    id: str
    case_id: str
    file_name: str
    file_size: int
    mime_type: str
    device_hash: str        # SHA-256 computed ON DEVICE
    captured_at: datetime
    gps_lat: Optional[float]
    gps_lon: Optional[float]
    gps_accuracy: Optional[float]
    device_id: str
    device_model: str
    os_version: str
    app_version: str
    policyholder_name: str = ""  
    policyholder_dni: str = ""    

@dataclass(frozen=True)
class RegisterCaptureResult:
    certificate_id: str
    upload_url: str


@dataclass(frozen=True)
class UploadFileCommand:
    """Sent when the mobile app uploads the actual file bytes."""
    certificate_id: str
    file_data: bytes
    file_name: str


@dataclass(frozen=True)
class UploadFileResult:
    certificate_id: str
    server_hash: str
    device_hash: str
    hash_verified: bool
    status: CertificateStatus
    pdf_download_url: str
    file_download_url: str


@dataclass(frozen=True)
class VerifyByIDQuery:
    certificate_id: str


@dataclass(frozen=True)
class VerifyByHashQuery:
    hash_value: str


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    certificate: Optional[Certificate]
    message: str


@dataclass(frozen=True)
class ListQuery:
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class ListResult:
    certificates: list
    total: int


@dataclass(frozen=True)
class DownloadQuery:
    certificate_id: str


@dataclass(frozen=True)
class DownloadResult:
    data: bytes
    file_name: str
    content_type: str


# ── Inbound Port Interfaces ───────────────────────────────────────────────────

class ICertifyUseCase(ABC):
    """
    Inbound port for the two-step certification protocol.
    The HTTP handler depends on this interface — never on CertifyFileUseCase.
    """

    @abstractmethod
    async def register_capture(
        self, cmd: RegisterCaptureCommand
    ) -> RegisterCaptureResult:
        """
        Step 1: Lock in the device hash before file is transferred.
        Raises: HashAlreadyExistsError, ValueError
        """
        ...

    @abstractmethod
    async def upload_file(
        self, cmd: UploadFileCommand
    ) -> UploadFileResult:
        """
        Step 2: Receive file, re-hash, compare with device hash.
        Raises: CertificateNotFoundError
        """
        ...


class IVerifyUseCase(ABC):
    """Inbound port for certificate verification queries."""

    @abstractmethod
    async def verify_by_id(
        self, query: VerifyByIDQuery
    ) -> VerificationResult:
        ...

    @abstractmethod
    async def verify_by_hash(
        self, query: VerifyByHashQuery
    ) -> VerificationResult:
        ...


class IListCertificatesUseCase(ABC):
    """Inbound port for listing certificates."""

    @abstractmethod
    async def list(self, query: ListQuery) -> ListResult:
        ...


class IDownloadUseCase(ABC):
    """Inbound port for downloading files and PDF certificates."""

    @abstractmethod
    async def download_pdf(self, query: DownloadQuery) -> DownloadResult:
        ...

    @abstractmethod
    async def download_file(self, query: DownloadQuery) -> DownloadResult:
        ...
