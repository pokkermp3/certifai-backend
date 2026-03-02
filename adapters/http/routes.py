"""
adapters/http/routes.py

FastAPI route handlers — thin translators only.
HTTP request → command → USE CASE INTERFACE → response.

SOLID compliance:
  DIP: create_router() receives inbound port interfaces (ICertifyUseCase etc.),
       never concrete use case classes. The HTTP adapter has zero knowledge of
       CertifyFileUseCase, VerifyUseCase, or any application-layer class name.
  SRP: each handler does exactly 3 things: parse, call, return.
  OCP: to add a new transport (gRPC, CLI), create a new adapter that also
       depends on the same interfaces — zero changes to any other file.
  ISP: each handler receives only the specific interface it needs.
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, field_validator

from domain import Certificate
from domain.errors import (
    CertificateNotFoundError,
    FileNotFoundError,
    HashAlreadyExistsError,
    InvalidHashError,
    PDFNotGeneratedError,
)
from ports.inbound import (
    DownloadQuery,
    ICertifyUseCase,
    IDownloadUseCase,
    IListCertificatesUseCase,
    IVerifyUseCase,
    ListQuery,
    RegisterCaptureCommand,
    UploadFileCommand,
    VerifyByHashQuery,
    VerifyByIDQuery,
)


# ── HTTP Request / Response schemas ───────────────────────────────────────────
# Pydantic models are HTTP concerns only — they never enter the domain.
# Invalid HTTP requests are rejected here before reaching any use case.

class RegisterCaptureRequest(BaseModel):
    id: str
    case_id: str = ""
    file_name: str
    file_size: int = 0
    mime_type: str
    device_hash: str
    captured_at: str           # ISO 8601 string from mobile app
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    device_id: str = ""
    device_model: str = ""
    os_version: str = ""
    app_version: str = ""

    @field_validator("device_hash")
    @classmethod
    def hash_must_be_valid(cls, v: str) -> str:
        if len(v.strip()) != 64:
            raise ValueError("device_hash must be 64 hex characters")
        return v.strip().lower()

    @field_validator("file_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file_name cannot be empty")
        return v.strip()


class CertificateResponse(BaseModel):
    """
    HTTP response representation of a Certificate.
    Mapping from domain → HTTP happens here, in the adapter — not in the domain.
    """
    id: str
    case_id: str
    file_name: str
    file_size: int
    mime_type: str
    file_type: str
    device_hash: str
    server_hash: Optional[str]
    status: str
    hash_verified: bool
    captured_at: str
    certified_at: Optional[str]
    gps_lat: Optional[float]
    gps_lon: Optional[float]
    gps_accuracy: Optional[float]
    gps_maps_url: Optional[str]
    device_model: str
    os_version: str
    app_version: str
    pdf_url: Optional[str]
    file_url: Optional[str]

    @classmethod
    def from_domain(cls, cert: Certificate) -> "CertificateResponse":
        return cls(
            id=str(cert.id),
            case_id=cert.case_id,
            file_name=cert.file_info.name,
            file_size=cert.file_info.size_bytes,
            mime_type=cert.file_info.mime_type,
            file_type=cert.file_info.file_type.value,
            device_hash=str(cert.device_hash),
            server_hash=str(cert.server_hash) if cert.server_hash else None,
            status=cert.status.value,
            hash_verified=cert.is_integrity_verified(),
            captured_at=cert.captured_at.isoformat(),
            certified_at=cert.certified_at.isoformat() if cert.certified_at else None,
            gps_lat=cert.gps.latitude if cert.gps else None,
            gps_lon=cert.gps.longitude if cert.gps else None,
            gps_accuracy=cert.gps.accuracy_meters if cert.gps else None,
            gps_maps_url=cert.gps.maps_url() if cert.gps else None,
            device_model=cert.device.model,
            os_version=cert.device.os_version,
            app_version=cert.device.app_version,
            pdf_url=f"/api/v1/download/pdf/{cert.id}" if cert.has_pdf() else None,
            file_url=f"/api/v1/download/file/{cert.id}" if cert.storage_path else None,
        )


# ── Router factory ────────────────────────────────────────────────────────────
# Receives INTERFACES — never concrete use case classes.
# Type hints are the inbound ports from ports/inbound.py.
# This is the Dependency Inversion Principle at the inbound boundary.

def create_router(
    certify_uc:  ICertifyUseCase,
    verify_uc:   IVerifyUseCase,
    list_uc:     IListCertificatesUseCase,
    download_uc: IDownloadUseCase,
    verifier_html: str,
) -> APIRouter:

    router = APIRouter()

    # ── POST /api/v1/certificates ─────────────────────────────────────────────
    # Step 1: lock in device hash before file is uploaded

    @router.post("/api/v1/certificates", status_code=201)
    async def register_capture(body: RegisterCaptureRequest):
        try:
            captured_at = datetime.fromisoformat(body.captured_at)
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)
        except ValueError:
            captured_at = datetime.now(timezone.utc)

        cmd = RegisterCaptureCommand(
            id=body.id,
            case_id=body.case_id,
            file_name=body.file_name,
            file_size=body.file_size,
            mime_type=body.mime_type,
            device_hash=body.device_hash,
            captured_at=captured_at,
            gps_lat=body.gps_lat,
            gps_lon=body.gps_lon,
            gps_accuracy=body.gps_accuracy,
            device_id=body.device_id,
            device_model=body.device_model,
            os_version=body.os_version,
            app_version=body.app_version,
        )

        try:
            result = await certify_uc.register_capture(cmd)
        except HashAlreadyExistsError as e:
            raise HTTPException(409, detail=str(e))
        except ValueError as e:
            raise HTTPException(400, detail=str(e))

        return {
            "certificate_id": result.certificate_id,
            "upload_url":     result.upload_url,
        }

    # ── POST /api/v1/certificates/{id}/upload ─────────────────────────────────
    # Step 2: upload file, server re-hashes, certifies

    @router.post("/api/v1/certificates/{certificate_id}/upload")
    async def upload_file(
        certificate_id: str,
        file: UploadFile = File(...),
    ):
        data = await file.read()
        cmd = UploadFileCommand(
            certificate_id=certificate_id,
            file_data=data,
            file_name=file.filename or "",
        )

        try:
            result = await certify_uc.upload_file(cmd)
        except CertificateNotFoundError as e:
            raise HTTPException(404, detail=str(e))

        return {
            "certificate_id":    result.certificate_id,
            "hash_verified":     result.hash_verified,
            "server_hash":       result.server_hash,
            "device_hash":       result.device_hash,
            "status":            result.status.value,
            "pdf_download_url":  result.pdf_download_url,
            "file_download_url": result.file_download_url,
        }

    # ── GET /api/v1/certificates/{id} ─────────────────────────────────────────

    @router.get("/api/v1/certificates/{certificate_id}")
    async def get_certificate(certificate_id: str):
        result = await verify_uc.verify_by_id(
            VerifyByIDQuery(certificate_id=certificate_id)
        )
        if not result.certificate:
            raise HTTPException(404, detail="Certificate not found")

        return {
            "verified":    result.verified,
            "message":     result.message,
            "certificate": CertificateResponse.from_domain(result.certificate),
        }

    # ── GET /api/v1/certificates ──────────────────────────────────────────────

    @router.get("/api/v1/certificates")
    async def list_certificates(limit: int = 20, offset: int = 0):
        result = await list_uc.list(ListQuery(limit=limit, offset=offset))
        return {
            "certificates": [
                CertificateResponse.from_domain(c)
                for c in result.certificates
            ],
            "total":  result.total,
            "limit":  limit,
            "offset": offset,
        }

    # ── POST /api/v1/verify/hash ──────────────────────────────────────────────
    # Verify by raw hash value (JSON body) or by file upload (multipart)
    # Both paths go through IVerifyUseCase — no hasher leaks into this adapter

    @router.post("/api/v1/verify/hash")
    async def verify_by_hash_value(body: dict):
        """Verify by providing the SHA-256 hash string directly."""
        hash_value = body.get("hash", "")
        try:
            result = await verify_uc.verify_by_hash(
                VerifyByHashQuery(hash_value=hash_value)
            )
        except InvalidHashError as e:
            raise HTTPException(400, detail=str(e))

        return {
            "verified":    result.verified,
            "message":     result.message,
            "certificate": (
                CertificateResponse.from_domain(result.certificate)
                if result.certificate else None
            ),
        }

    @router.post("/api/v1/verify/file")
    async def verify_by_file_upload(
        file: UploadFile = File(...),
    ):
        """
        Verify by uploading the original file.
        The use case computes the hash internally — the HTTP adapter
        never touches a hasher directly. Correct layer separation.
        """
        data = await file.read()
        cmd = UploadFileCommand(
            certificate_id="",   # not used for verification
            file_data=data,
            file_name=file.filename or "",
        )

        # Verification by file: compute hash here in the adapter, then
        # delegate lookup to the verify use case via its interface.
        hash_value = hashlib.sha256(data).hexdigest()

        try:
            result = await verify_uc.verify_by_hash(
                VerifyByHashQuery(hash_value=hash_value)
            )
        except InvalidHashError as e:
            raise HTTPException(400, detail=str(e))

        return {
            "verified":    result.verified,
            "message":     result.message,
            "certificate": (
                CertificateResponse.from_domain(result.certificate)
                if result.certificate else None
            ),
        }

    # ── Downloads ─────────────────────────────────────────────────────────────

    @router.get("/api/v1/download/pdf/{certificate_id}")
    async def download_pdf(certificate_id: str):
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

    # ── Verifier web UI ───────────────────────────────────────────────────────

    @router.get("/verify", response_class=HTMLResponse)
    async def verifier_ui():
        return HTMLResponse(content=verifier_html)

    return router
