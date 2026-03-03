"""
adapters/http/routes_download.py

Download routes — PDF certificate and original file.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from domain.errors import CertificateNotFoundError, FileNotFoundError, PDFNotGeneratedError
from ports.inbound import IDownloadUseCase, DownloadQuery
from adapters.http.route_utils import validate_certificate_id


def create_download_router(download_uc: IDownloadUseCase) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/download/pdf/{certificate_id}")
    async def download_pdf(certificate_id: str):
        certificate_id = validate_certificate_id(certificate_id)
        try:
            result = await download_uc.download_pdf(
                DownloadQuery(certificate_id=certificate_id)
            )
        except CertificateNotFoundError:
            raise HTTPException(404, detail="Certificate not found")
        except PDFNotGeneratedError:
            raise HTTPException(404, detail="PDF not yet generated")

        return Response(
            content=result.data,
            media_type=result.content_type,
            headers={"Content-Disposition": f'attachment; filename="{result.file_name}"'},
        )

    @router.get("/api/v1/download/file/{certificate_id}")
    async def download_file(certificate_id: str):
        certificate_id = validate_certificate_id(certificate_id)
        try:
            result = await download_uc.download_file(
                DownloadQuery(certificate_id=certificate_id)
            )
        except (CertificateNotFoundError, FileNotFoundError):
            raise HTTPException(404, detail="File not found")

        return Response(
            content=result.data,
            media_type=result.content_type,
            headers={"Content-Disposition": f'attachment; filename="{result.file_name}"'},
        )

    return router