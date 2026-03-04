"""
adapters/http/routes_certify.py

Certification routes — Step 1 (register) and Step 2 (upload).
SRP: this file only handles the certification lifecycle.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, field_validator

from domain.errors import HashAlreadyExistsError, CertificateNotFoundError
from ports.inbound import (
    ICertifyUseCase,
    RegisterCaptureCommand,
    UploadFileCommand,
)
from adapters.http.route_utils import validate_certificate_id


class RegisterCaptureRequest(BaseModel):
    id: str
    case_id: str = ""
    file_name: str
    file_size: int = 0
    mime_type: str
    device_hash: str
    captured_at: str
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    device_id: str = ""
    device_model: str = ""
    os_version: str = ""
    app_version: str = ""
    policyholder_name: str = ""
    policyholder_dni: str = ""

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


def create_certify_router(certify_uc: ICertifyUseCase) -> APIRouter:
    router = APIRouter()

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
            policyholder_name=body.policyholder_name,
            policyholder_dni=body.policyholder_dni,
        )

        try:
            result = await certify_uc.register_capture(cmd)
        except HashAlreadyExistsError as e:
            raise HTTPException(409, detail=str(e))
        except ValueError as e:
            raise HTTPException(400, detail=str(e))

        return {
            "certificate_id": result.certificate_id,
            "upload_url": result.upload_url,
        }

    @router.post("/api/v1/certificates/{certificate_id}/upload")
    async def upload_file(
        certificate_id: str,
        file: UploadFile = File(...),
    ):
        certificate_id = validate_certificate_id(certificate_id)
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
            "certificate_id": result.certificate_id,
            "hash_verified": result.hash_verified,
            "server_hash": result.server_hash,
            "device_hash": result.device_hash,
            "status": result.status.value,
            "pdf_download_url": result.pdf_download_url,
            "file_download_url": result.file_download_url,
        }

    return router