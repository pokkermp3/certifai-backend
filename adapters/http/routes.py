"""
adapters/http/routes.py

Facade — assembles all sub-routers into one FastAPI router.
This file now has exactly one job: wiring.

Each concern lives in its own file:
  routes_certify.py   — certification lifecycle
  routes_verify.py    — verification + listing
  routes_download.py  — file + PDF downloads
"""
from fastapi import APIRouter
from adapters.http.routes_clients import create_clients_router
from ports.inbound import (
    ICertifyUseCase,
    IVerifyUseCase,
    IListCertificatesUseCase,
    IDownloadUseCase,
)
from ports.outbound import IHasher
from adapters.http.routes_certify import create_certify_router
from adapters.http.routes_verify import create_verify_router
from adapters.http.routes_download import create_download_router


def create_router(
    certify_uc: ICertifyUseCase,
    verify_uc: IVerifyUseCase,
    list_uc: IListCertificatesUseCase,
    download_uc: IDownloadUseCase,
    hasher: IHasher,
    verifier_html: str,
    repo,
) -> APIRouter:
    """
    Facade pattern: assembles sub-routers into one router.
    Each sub-router is independently testable.
    """
    router = APIRouter()
    router.include_router(create_certify_router(certify_uc))
    router.include_router(create_verify_router(verify_uc, list_uc, hasher, verifier_html))
    router.include_router(create_download_router(download_uc))
    router.include_router(create_clients_router(repo))
    return router