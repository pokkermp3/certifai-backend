"""
adapters/http/routes_verify.py

Verification routes — verify by ID, hash, or file upload.
Fix: hash computation moved OUT of HTTP adapter and into IHasher port.
     The HTTP adapter now delegates hashing to the injected hasher — DIP correct.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from domain.errors import InvalidHashError
from ports.inbound import (
    IVerifyUseCase,
    IListCertificatesUseCase,
    VerifyByIDQuery,
    VerifyByHashQuery,
    ListQuery,
)
from ports.outbound import IHasher
from adapters.http.certificate_response import CertificateResponse
from adapters.http.route_utils import validate_certificate_id


def create_verify_router(
    verify_uc: IVerifyUseCase,
    list_uc: IListCertificatesUseCase,
    hasher: IHasher,
    verifier_html: str,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/certificates/{certificate_id}")
    async def get_certificate(certificate_id: str):
        certificate_id = validate_certificate_id(certificate_id)
        result = await verify_uc.verify_by_id(
            VerifyByIDQuery(certificate_id=certificate_id)
        )
        if not result.certificate:
            raise HTTPException(404, detail="Certificate not found")
        return {
            "verified": result.verified,
            "message": result.message,
            "certificate": CertificateResponse.from_domain(result.certificate),
        }

    @router.get("/api/v1/certificates")
    async def list_certificates(limit: int = 20, offset: int = 0):
        # Cap at 100 — never return unbounded results
        limit = min(max(limit, 1), 100)
        result = await list_uc.list(ListQuery(limit=limit, offset=offset))
        return {
            "certificates": [
                CertificateResponse.from_domain(c)
                for c in result.certificates
            ],
            "total": result.total,
            "limit": limit,
            "offset": offset,
        }

    @router.post("/api/v1/verify/hash")
    async def verify_by_hash_value(body: dict):
        hash_value = body.get("hash", "")
        try:
            result = await verify_uc.verify_by_hash(
                VerifyByHashQuery(hash_value=hash_value)
            )
        except InvalidHashError as e:
            raise HTTPException(400, detail=str(e))
        return {
            "verified": result.verified,
            "message": result.message,
            "certificate": (
                CertificateResponse.from_domain(result.certificate)
                if result.certificate else None
            ),
        }

    @router.post("/api/v1/verify/file")
    async def verify_by_file_upload(file: UploadFile = File(...)):
        """
        DIP fix: hash computation delegated to injected IHasher.
        The HTTP adapter no longer imports hashlib directly.
        """
        data = await file.read()
        # Delegate to injected hasher — correct layer separation
        hash_obj = await hasher.hash_bytes(data)
        hash_value = str(hash_obj)

        try:
            result = await verify_uc.verify_by_hash(
                VerifyByHashQuery(hash_value=hash_value)
            )
        except InvalidHashError as e:
            raise HTTPException(400, detail=str(e))

        return {
            "verified": result.verified,
            "message": result.message,
            "certificate": (
                CertificateResponse.from_domain(result.certificate)
                if result.certificate else None
            ),
        }

    @router.get("/verify", response_class=HTMLResponse)
    async def verifier_ui():
        return HTMLResponse(content=verifier_html)

    return router