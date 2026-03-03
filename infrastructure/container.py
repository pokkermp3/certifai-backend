"""
infrastructure/container.py

The composition root — the ONLY file in the codebase that knows which
concrete classes implement which interfaces.

Every other layer depends only on abstractions (port interfaces).
Only this file knows that SQLite, local filesystem, SHA-256, and
WeasyPrint are the concrete implementations in use.

To swap any implementation:
  1. Write a new adapter that implements the relevant port interface
  2. Change ONE line here
  3. Done — zero changes to any other file
"""
from adapters.hashing.sha256 import SHA256Hasher
from adapters.http.routes import create_router
from adapters.http.verifier import VERIFIER_HTML
from adapters.pdf.weasyprint_generator import WeasyprintGenerator
from adapters.persistence.sqlite_repo import SQLiteCertificateRepository
from adapters.storage.local_storage import LocalFileStorage
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
    """

    def __init__(self, settings: Settings) -> None:
        # ── Outbound adapters ─────────────────────────────────────────────────
        # Stored as their concrete types here only — everything else
        # receives them as port interfaces via constructor injection.
        repo    = SQLiteCertificateRepository(settings.database_path)
        storage = LocalFileStorage(settings.upload_dir)
        hasher  = SHA256Hasher()
        pdf_gen = WeasyprintGenerator(settings.cert_dir)

        # Keep a reference for init()
        self._repo = repo

        # ── Use cases (application layer) ─────────────────────────────────────
        # Each use case receives outbound port interfaces — never concrete adapters.
        # Typed as their INBOUND PORT INTERFACE so the container enforces
        # that create_router() can only see what the interface exposes.
        self.certify_uc:  CertifyFileUseCase    = CertifyFileUseCase(
            repo=repo, storage=storage, hasher=hasher, pdf_gen=pdf_gen,
        )
        self.verify_uc:   VerifyUseCase         = VerifyUseCase(repo=repo)
        self.list_uc:     ListCertificatesUseCase = ListCertificatesUseCase(repo=repo)
        self.download_uc: DownloadUseCase       = DownloadUseCase(repo=repo, storage=storage)

        # ── Inbound adapter (HTTP) ────────────────────────────────────────────
        # create_router() accepts inbound port interfaces — see routes.py.
        # Passing concrete use case instances is fine here because they
        # satisfy their respective interface contracts (they extend them).
        self.router = create_router(
            certify_uc=self.certify_uc,
            verify_uc=self.verify_uc,
            list_uc=self.list_uc,
            download_uc=self.download_uc,
            hasher=hasher,
            verifier_html=VERIFIER_HTML,
        )

    async def init(self) -> None:
        """Initialise the database schema. Call once at application startup."""
        await self._repo.init()
