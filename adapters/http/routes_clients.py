"""
adapters/http/routes_clients.py

Agent-facing routes — client list, client detail, and auth.
Phase 2 addition.
"""
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from adapters.http.certificate_response import CertificateResponse
from ports.certificate_repo import ICertificateRepository


class AuthVerifyRequest(BaseModel):
    password: str


def create_clients_router(repo: ICertificateRepository) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/auth/verify")
    async def auth_verify(body: AuthVerifyRequest):
        expected = os.environ.get("CERTIFAI_AGENT_PASSWORD", "certifai2025")
        return {"valid": body.password == expected}

    @router.get("/api/v1/clients")
    async def list_clients():
        clients = await repo.find_clients()
        return {"clients": clients}

    @router.get("/api/v1/clients/{dni}/certificates")
    async def get_client_certificates(dni: str):
        certs = await repo.find_by_dni(dni)
        if not certs:
            raise HTTPException(404, detail=f"No certificates found for DNI: {dni}")
        return {
            "client": {
                "dni": dni,
                "name": certs[0].policyholder_name,
            },
            "certificates": [CertificateResponse.from_domain(c) for c in certs],
        }

    return router