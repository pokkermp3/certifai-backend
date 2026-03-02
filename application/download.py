"""
application/download.py

DownloadUseCase — implements IDownloadUseCase (inbound port).

SRP: this file has exactly one responsibility — serving file and PDF downloads.
All domain error imports are at the top of the file, not inside method bodies.
"""
from domain import CertificateID
from domain.errors import (
    CertificateNotFoundError,
    FileNotFoundError,
    PDFNotGeneratedError,
)
from ports import ICertificateRepository, IFileStorage
from ports.inbound import DownloadQuery, DownloadResult, IDownloadUseCase


class DownloadUseCase(IDownloadUseCase):
    """
    Serves file and PDF certificate downloads.
    Extends IDownloadUseCase — the HTTP adapter depends on the interface,
    never on this concrete class.
    """

    def __init__(
        self,
        repo:    ICertificateRepository,
        storage: IFileStorage,
    ) -> None:
        self._repo    = repo
        self._storage = storage

    async def download_pdf(self, query: DownloadQuery) -> DownloadResult:
        cert = await self._repo.find_by_id(CertificateID(query.certificate_id))

        if cert is None:
            raise CertificateNotFoundError(query.certificate_id)
        if not cert.has_pdf():
            raise PDFNotGeneratedError(query.certificate_id)

        handle, _ = await self._storage.open(cert.pdf_path)
        data = handle.read()

        return DownloadResult(
            data=data,
            file_name=f"certifai_{str(cert.id)[:8]}.pdf",
            content_type="application/pdf",
        )

    async def download_file(self, query: DownloadQuery) -> DownloadResult:
        cert = await self._repo.find_by_id(CertificateID(query.certificate_id))

        if cert is None:
            raise CertificateNotFoundError(query.certificate_id)
        if not cert.storage_path:
            raise FileNotFoundError(query.certificate_id)

        handle, _ = await self._storage.open(cert.storage_path)
        data = handle.read()

        return DownloadResult(
            data=data,
            file_name=cert.file_info.name,
            content_type=cert.file_info.mime_type,
        )
