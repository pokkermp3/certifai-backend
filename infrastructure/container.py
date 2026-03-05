"""
infrastructure/container.py

The composition root — the ONLY file in the codebase that knows which
concrete classes implement which interfaces.

Auto-selects adapters based on environment variables:
  CERTIFAI_DATABASE_URL set   → PostgreSQL  (production / Neon)
  CERTIFAI_DATABASE_URL empty → SQLite      (local dev)
  CERTIFAI_R2_BUCKET set      → Cloudflare R2 (production)
  CERTIFAI_R2_BUCKET empty    → Local filesystem (local dev)

To swap any implementation:
  1. Write a new adapter that implements the relevant port interface
  2. Change ONE line here
  3. Done — zero changes to any other file
"""
from adapters.hashing.sha256 import SHA256Hasher
from adapters.http.dashboard import dashboard_router
from adapters.http.routes import create_router
from adapters.http.verifier import VERIFIER_HTML
from adapters.pdf.weasyprint_generator import WeasyprintGenerator
from application import (
    CertifyFileUseCase,
    DownloadUseCase,
    ListCertificatesUseCase,
    VerifyUseCase,
)
from infrastructure.config import Settings


class Container:
    """
    Builds and wires all application dependencies.

    Exposes typed attributes using the INTERFACE types (ports), not the
    concrete adapter types. This enforces at the container level that no
    consumer can access implementation details they don't need.

    Call container.init() once at startup to initialise the database.
    Call container.shutdown() once at shutdown to close DB connections.
    """

    def __init__(self, settings: Settings) -> None:
        # ── Persistence adapter ───────────────────────────────────────────────
        if settings.database_url:
            from adapters.persistence.postgres_repo import PostgresCertificateRepository
            repo = PostgresCertificateRepository(settings.database_url)
        else:
            from adapters.persistence.sqlite_repo import SQLiteCertificateRepository
            repo = SQLiteCertificateRepository(settings.database_path)

        # ── Storage adapter ───────────────────────────────────────────────────
        if settings.r2_bucket:
            from adapters.storage.s3_storage import S3FileStorage
            storage = S3FileStorage(
                bucket=settings.r2_bucket,
                endpoint_url=settings.r2_endpoint,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
            )
        else:
            from adapters.storage.local_storage import LocalFileStorage
            storage = LocalFileStorage(settings.upload_dir)

        # ── Other adapters ────────────────────────────────────────────────────
        hasher  = SHA256Hasher()
        pdf_gen = WeasyprintGenerator(settings.cert_dir)

        # Keep reference for lifecycle management
        self._repo = repo

        # ── Use cases (application layer) ─────────────────────────────────────
        # Each use case receives outbound port interfaces — never concrete adapters.
        # Typed as their INBOUND PORT INTERFACE so the container enforces
        # that create_router() can only see what the interface exposes.
        self.certify_uc:  CertifyFileUseCase      = CertifyFileUseCase(
            repo=repo, storage=storage, hasher=hasher, pdf_gen=pdf_gen,
        )
        self.verify_uc:   VerifyUseCase           = VerifyUseCase(repo=repo)
        self.list_uc:     ListCertificatesUseCase = ListCertificatesUseCase(repo=repo)
        self.download_uc: DownloadUseCase         = DownloadUseCase(repo=repo, storage=storage)

        # ── Inbound adapter (HTTP) ────────────────────────────────────────────
        # create_router() accepts inbound port interfaces — see routes.py.
        # Passing concrete use case instances is fine because they satisfy
        # their respective interface contracts (they extend them).
        self.router = create_router(
            certify_uc=self.certify_uc,
            verify_uc=self.verify_uc,
            list_uc=self.list_uc,
            download_uc=self.download_uc,
            hasher=hasher,
            verifier_html=VERIFIER_HTML,
            repo=repo,
        )
        self.dashboard_router = dashboard_router

    async def init(self) -> None:
        """Initialise the database schema. Called once at application startup."""
        await self._repo.init()

    async def shutdown(self) -> None:
        """
        Graceful shutdown — close DB connection pool.
        PostgresCertificateRepository.close() drains in-flight queries and
        releases TCP connections back to Neon before the process exits.
        SQLiteCertificateRepository has no persistent connections — no-op.
        """
        if hasattr(self._repo, "close"):
            await self._repo.close()