"""
adapters/hashing/sha256.py

Implements IHasher using SHA-256.
To swap algorithms: create a new file, implement IHasher, change container.py.
"""
import hashlib
import io

from domain import Hash
from ports import IHasher


class SHA256Hasher(IHasher):
    """
    SHA-256 implementation of IHasher.

    Files are streamed in 1MB chunks — never loads
    the entire file into memory. Safe for large videos.
    """

    CHUNK_SIZE = 1024 * 1024  # 1 MB

    async def hash_bytes(self, data: bytes) -> Hash:
        digest = hashlib.sha256(data).hexdigest()
        return Hash(digest)

    async def hash_file(self, storage_path: str) -> Hash:
        h = hashlib.sha256()
        with open(storage_path, "rb") as f:
            while chunk := f.read(self.CHUNK_SIZE):
                h.update(chunk)
        return Hash(h.hexdigest())
