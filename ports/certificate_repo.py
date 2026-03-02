"""
ports/certificate_repo.py

The persistence port.
The application layer depends on this interface, never on SQLite directly.
This is Dependency Inversion in action — high-level module depends on abstraction.

To swap SQLite for PostgreSQL:
  1. Create adapters/persistence/postgres_repo.py
  2. Implement ICertificateRepository
  3. Change one line in infrastructure/container.py
  4. Done — zero changes to application or domain
"""
from abc import ABC, abstractmethod
from typing import Optional

from domain import Certificate, CertificateID, Hash


class ICertificateRepository(ABC):

    @abstractmethod
    async def save(self, certificate: Certificate) -> None:
        """Persist a new certificate."""
        ...

    @abstractmethod
    async def update(self, certificate: Certificate) -> None:
        """Persist changes to an existing certificate."""
        ...

    @abstractmethod
    async def find_by_id(
        self, id: CertificateID
    ) -> Optional[Certificate]:
        """Return certificate by ID, or None if not found."""
        ...

    @abstractmethod
    async def find_by_hash(
        self, hash: Hash
    ) -> Optional[Certificate]:
        """
        Return certificate matching device_hash or server_hash.
        Used for verification — insurer drops a file, we find its certificate.
        """
        ...

    @abstractmethod
    async def find_all(
        self, limit: int, offset: int
    ) -> tuple[list[Certificate], int]:
        """Return paginated list of certificates + total count."""
        ...

    @abstractmethod
    async def exists_by_hash(self, hash: Hash) -> bool:
        """Check for duplicate without fetching the full record."""
        ...
