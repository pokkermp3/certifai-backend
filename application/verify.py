"""
application/verify.py

VerifyUseCase — implements IVerifyUseCase (inbound port).

SRP: this file is only responsible for verification queries.
Each use case is in its own file:
  - certify_file.py  → CertifyFileUseCase
  - verify.py        → VerifyUseCase
  - list_certs.py    → ListCertificatesUseCase
  - download.py      → DownloadUseCase
"""
from domain import CertificateID, Hash
from domain.errors import CertificateNotFoundError, InvalidHashError
from ports import ICertificateRepository
from ports.inbound import (
    IVerifyUseCase,
    VerificationResult,
    VerifyByHashQuery,
    VerifyByIDQuery,
)


class VerifyUseCase(IVerifyUseCase):
    """
    Answers the question: "Is this file authentic?"

    Extends IVerifyUseCase — the HTTP adapter depends on the interface,
    never on this concrete class.

    Two verification paths:
    1. By certificate ID — direct lookup
    2. By hash — insurer drops the original file, we find its certificate
    """

    def __init__(self, repo: ICertificateRepository) -> None:
        self._repo = repo

    async def verify_by_id(self, query: VerifyByIDQuery) -> VerificationResult:
        cert = await self._repo.find_by_id(CertificateID(query.certificate_id))

        if cert is None:
            return VerificationResult(
                verified=False,
                certificate=None,
                message="No certificate found with this ID.",
            )

        return VerificationResult(
            verified=cert.is_integrity_verified(),
            certificate=cert,
            message=cert.verification_message(),
        )

    async def verify_by_hash(self, query: VerifyByHashQuery) -> VerificationResult:
        try:
            hash_obj = Hash(query.hash_value)
        except ValueError:
            raise InvalidHashError(query.hash_value)

        cert = await self._repo.find_by_hash(hash_obj)

        if cert is None:
            return VerificationResult(
                verified=False,
                certificate=None,
                message=(
                    "No certificate found for this hash. "
                    "The file may have been altered or was not "
                    "captured through CertifAI."
                ),
            )

        return VerificationResult(
            verified=cert.is_integrity_verified(),
            certificate=cert,
            message=cert.verification_message(),
        )
