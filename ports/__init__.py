from .certificate_repo import ICertificateRepository
from .inbound import (
    DownloadQuery,
    DownloadResult,
    ICertifyUseCase,
    IDownloadUseCase,
    IListCertificatesUseCase,
    IVerifyUseCase,
    ListQuery,
    ListResult,
    RegisterCaptureCommand,
    RegisterCaptureResult,
    UploadFileCommand,
    UploadFileResult,
    VerificationResult,
    VerifyByHashQuery,
    VerifyByIDQuery,
)
from .outbound import IFileStorage, IHasher, IPDFGenerator

__all__ = [
    # Outbound ports (what application needs from infrastructure)
    "ICertificateRepository",
    "IFileStorage",
    "IHasher",
    "IPDFGenerator",
    # Inbound ports (what HTTP adapter depends on)
    "ICertifyUseCase",
    "IVerifyUseCase",
    "IListCertificatesUseCase",
    "IDownloadUseCase",
    # Commands and results (shared contract)
    "RegisterCaptureCommand",
    "RegisterCaptureResult",
    "UploadFileCommand",
    "UploadFileResult",
    "VerifyByIDQuery",
    "VerifyByHashQuery",
    "VerificationResult",
    "ListQuery",
    "ListResult",
    "DownloadQuery",
    "DownloadResult",
]
