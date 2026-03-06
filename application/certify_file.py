"""
application/certify_file.py

CertifyFileUseCase — implements ICertifyUseCase (inbound port).

By extending ICertifyUseCase:
  - The contract is enforced at class definition time (OCP, LSP)
  - The HTTP adapter depends only on ICertifyUseCase, never this class
  - Swapping implementations requires zero changes to routes.py

What this file knows about:
  - Domain entities and value objects
  - Outbound port interfaces (ICertificateRepository, IHasher, etc.)
  - Commands and Results from ports.inbound (shared contract)

What this file does NOT know about:
  - FastAPI, HTTP, request/response objects
  - SQLite, SQL queries, file paths
  - WeasyPrint or any concrete adapter class
"""
import io
import asyncio
from domain import (
    Certificate,
    CertificateID,
    DeviceInfo,
    FileInfo,
    GPSCoordinates,
    Hash,
)
from domain.errors import CertificateNotFoundError, HashAlreadyExistsError
from ports import ICertificateRepository, IFileStorage, IHasher, IPDFGenerator
from ports.inbound import (
    ICertifyUseCase,
    RegisterCaptureCommand,
    RegisterCaptureResult,
    UploadFileCommand,
    UploadFileResult,
)


class CertifyFileUseCase(ICertifyUseCase):
    """
    Implements the two-step certification protocol.

    Extends ICertifyUseCase — so the HTTP adapter depends only on the
    interface, never on this concrete class (DIP at inbound boundary).

    Step 1 — register_capture():
      Mobile app sends hash BEFORE uploading the file.
      Device hash is locked in. Nobody can claim it was different later.

    Step 2 — upload_file():
      Mobile app uploads actual bytes.
      We re-hash independently on the server and compare.
      Hashes match → CERTIFIED. Differ → HASH_MISMATCH.

    All dependencies injected as outbound port interfaces (DIP).
    This class never imports SQLite, FastAPI, or any concrete adapter.
    """

    def __init__(
        self,
        repo:    ICertificateRepository,
        storage: IFileStorage,
        hasher:  IHasher,
        pdf_gen: IPDFGenerator,
    ) -> None:
        self._repo    = repo
        self._storage = storage
        self._hasher  = hasher
        self._pdf_gen = pdf_gen

    async def register_capture(
        self, cmd: RegisterCaptureCommand
    ) -> RegisterCaptureResult:
        """
        Step 1: Lock in the device hash before the file is transferred.

        Raises:
            ValueError: if device_hash format is invalid
            HashAlreadyExistsError: if this exact file was already certified
        """
        device_hash = Hash(cmd.device_hash)

        if await self._repo.exists_by_hash(device_hash):
            raise HashAlreadyExistsError(cmd.device_hash)

        gps = None
        if cmd.gps_lat is not None and cmd.gps_lon is not None:
            gps = GPSCoordinates(
                latitude=cmd.gps_lat,
                longitude=cmd.gps_lon,
                accuracy_meters=cmd.gps_accuracy or 0.0,
            )

        certificate = Certificate.register(
            id=CertificateID(cmd.id),
            case_id=cmd.case_id,
            file_info=FileInfo(
                name=cmd.file_name,
                size_bytes=cmd.file_size,
                mime_type=cmd.mime_type,
            ),
            device_hash=device_hash,
            gps=gps,
            device=DeviceInfo(
                device_id=cmd.device_id,
                model=cmd.device_model,
                os_version=cmd.os_version,
                app_version=cmd.app_version,
            ),
            captured_at=cmd.captured_at,
            policyholder_name=cmd.policyholder_name,
            policyholder_dni=cmd.policyholder_dni,
        )

        await self._repo.save(certificate)

        return RegisterCaptureResult(
            certificate_id=str(certificate.id),
            upload_url=f"/api/v1/certificates/{certificate.id}/upload",
        )

    async def upload_file(
        self, cmd: UploadFileCommand
    ) -> UploadFileResult:
        """
        Step 2: Receive file, re-hash on server, certify.

        Raises:
            CertificateNotFoundError: if no certificate matches the ID
        """
        certificate = await self._repo.find_by_id(CertificateID(cmd.certificate_id))

        if certificate is None:
            raise CertificateNotFoundError(cmd.certificate_id)

        # ── Core trust operation ───────────────────────────────────────────
        # Server re-hashes independently — we do not trust the device claim.
        server_hash = await self._hasher.hash_bytes(cmd.file_data)

        storage_path = await self._storage.store(
            file_id=cmd.certificate_id,
            data=io.BytesIO(cmd.file_data),
            mime_type=certificate.file_info.mime_type,
        )

        # Business rule executes inside the domain entity — not here
        certificate.certify(server_hash, storage_path)

        
        await self._repo.update(certificate)

        # Generate PDF in background — don't block the response
        asyncio.create_task(self._generate_pdf_background(certificate))

        return UploadFileResult(
            certificate_id=str(certificate.id),
            server_hash=str(server_hash),
            device_hash=str(certificate.device_hash),
            hash_verified=certificate.is_integrity_verified(),
            status=certificate.status,
            pdf_download_url=f"/api/v1/download/pdf/{certificate.id}",
            file_download_url=f"/api/v1/download/file/{certificate.id}",

            
        )
    
    async def _generate_pdf_background(self, certificate: Certificate) -> None:
        import os
        local_path = None
        try:
            # 1. Generate PDF to local filesystem
            local_path = await self._pdf_gen.generate(certificate)

            # 2. Upload PDF to R2 (or local storage) so download_uc can find it
            with open(local_path, "rb") as f:
                r2_key = await self._storage.store(
                    file_id=f"pdf_{certificate.id}",
                    data=f,
                    mime_type="application/pdf",
                )

            # 3. Save R2 key (not local path) to DB
            certificate.set_pdf_path(r2_key)
            await self._repo.update(certificate)

        except Exception:
            pass
        finally:
            # 4. Clean up local temp file regardless of outcome
            if local_path:
                try:
                    os.unlink(local_path)
                except OSError:
                    pass