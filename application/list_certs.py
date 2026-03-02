"""
application/list_certs.py

ListCertificatesUseCase — implements IListCertificatesUseCase (inbound port).

SRP: this file has exactly one responsibility — paginated listing.
"""
from ports import ICertificateRepository
from ports.inbound import IListCertificatesUseCase, ListQuery, ListResult


class ListCertificatesUseCase(IListCertificatesUseCase):
    """
    Returns a paginated list of all certificates.
    Extends IListCertificatesUseCase — the HTTP adapter depends on the
    interface, never on this concrete class.
    """

    def __init__(self, repo: ICertificateRepository) -> None:
        self._repo = repo

    async def list(self, query: ListQuery) -> ListResult:
        limit = max(1, min(query.limit, 100))  # clamp: 1–100
        certs, total = await self._repo.find_all(limit, query.offset)
        return ListResult(certificates=certs, total=total)
