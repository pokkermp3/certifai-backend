"""
adapters/persistence/postgres_repo.py

PostgreSQL implementation of ICertificateRepository.
Drop-in replacement for SQLiteCertificateRepository — same interface, same
domain mapping, zero changes required in any other file.

Uses asyncpg with a connection pool (created once at startup via init()).
GPS and device data stored as JSONB (native Postgres type, indexed efficiently).

Requires: asyncpg  →  already in requirements.txt
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from domain import (
    Certificate,
    CertificateID,
    CertificateStatus,
    DeviceInfo,
    FileInfo,
    GPSCoordinates,
    Hash,
)
from domain.errors import HashAlreadyExistsError
from ports import ICertificateRepository

# Explicit column list — avoids SELECT * bleeding extra cols (e.g. _total from
# window functions) into _from_row, and makes schema changes explicit.
_COLUMNS = """
    id, case_id, file_name, file_size, mime_type,
    device_hash, server_hash, status, captured_at, certified_at,
    gps_json, device_json, storage_path, pdf_path,
    policyholder_name, policyholder_dni
"""


class PostgresCertificateRepository(ICertificateRepository):
    """
    Async PostgreSQL repository backed by an asyncpg connection pool.
    The pool is created once in init() and reused for the app lifetime —
    never open/close per request.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        """
        Create the connection pool and ensure the schema exists.
        All DDL runs inside a single transaction — if anything fails mid-init,
        the DB is left unchanged (no partial schema).
        Safe to run on an already-initialised DB (IF NOT EXISTS everywhere).
        Idempotent — calling twice is a no-op (guards against double-init).
        Called once at startup via container.init().
        """
        if self._pool is not None:
            return  # already initialised — prevent second pool from leaking

        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=5,          # Neon free tier supports ~10 concurrent connections
            command_timeout=30,
        )
        async with self._pool.acquire() as conn:
            async with conn.transaction():             # atomic — all or nothing
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS certificates (
                        id                TEXT        PRIMARY KEY,
                        case_id           TEXT        NOT NULL DEFAULT '',
                        file_name         TEXT        NOT NULL,
                        file_size         INTEGER     NOT NULL DEFAULT 0,
                        mime_type         TEXT        NOT NULL DEFAULT '',
                        device_hash       TEXT        NOT NULL,
                        server_hash       TEXT        NOT NULL DEFAULT '',
                        status            TEXT        NOT NULL DEFAULT 'pending_upload',
                        captured_at       TIMESTAMPTZ NOT NULL,
                        certified_at      TIMESTAMPTZ,
                        gps_json          JSONB,
                        device_json       JSONB       NOT NULL DEFAULT '{}',
                        storage_path      TEXT        NOT NULL DEFAULT '',
                        pdf_path          TEXT        NOT NULL DEFAULT '',
                        policyholder_name TEXT        NOT NULL DEFAULT '',
                        policyholder_dni  TEXT        NOT NULL DEFAULT ''
                    )
                """)
                # Unique constraint mirrors SQLite — prevents duplicate submissions
                await conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uidx_device_hash
                    ON certificates(device_hash)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_server_hash
                    ON certificates(server_hash)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_captured_at
                    ON certificates(captured_at DESC)
                """)
                # Speeds up dashboard DNI search and find_by_dni()
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_policyholder_dni
                    ON certificates(policyholder_dni)
                """)

    async def close(self) -> None:
        """
        Close the connection pool gracefully.
        Call from the FastAPI lifespan shutdown block to avoid stale
        connections on Neon's side after the process exits.
        """
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def save(self, cert: Certificate) -> None:
        """
        Persist a new certificate.
        Raises HashAlreadyExistsError if device_hash is a duplicate —
        mirrors the SQLite IntegrityError behaviour exactly.
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO certificates ({_COLUMNS})
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                """, *self._to_row(cert))
        except asyncpg.UniqueViolationError:
            raise HashAlreadyExistsError(str(cert.device_hash))

    async def update(self, cert: Certificate) -> None:
        """
        Persist changes to an existing certificate.

        Called in two scenarios:
          1. Upload verified → status transitions pending_upload → certified,
             server_hash + storage_path set, pdf_path still empty.
          2. PDF background task completes → pdf_path filled in,
             status remains certified.

        No status guard here — mirrors SQLite exactly. Duplicate protection
        is handled upstream by the UNIQUE INDEX on device_hash in save(),
        which prevents the same file being registered twice. Two concurrent
        uploads for the same cert_id would produce identical writes
        (same hash, same storage_path) so last-write-wins is safe.
        """
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE certificates SET
                    server_hash  = $1,
                    status       = $2,
                    certified_at = $3,
                    storage_path = $4,
                    pdf_path     = $5
                WHERE id = $6
            """,
                str(cert.server_hash) if cert.server_hash else "",
                cert.status.value,
                cert.certified_at,
                cert.storage_path,
                cert.pdf_path,
                str(cert.id),
            )

    # ── Read ──────────────────────────────────────────────────────────────────

    async def find_by_id(self, id: CertificateID) -> Optional[Certificate]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM certificates WHERE id = $1", str(id)
            )
        return self._from_row(row) if row else None

    async def find_by_hash(self, hash: Hash) -> Optional[Certificate]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM certificates "
                "WHERE device_hash = $1 OR server_hash = $1",
                str(hash),
            )
        return self._from_row(row) if row else None

    async def find_all(
        self, limit: int, offset: int
    ) -> tuple[list[Certificate], int]:
        """
        Paginated list + total count in a single round-trip.
        Uses a window function so we never issue two separate queries.
        The _total column is read before mapping rows to avoid
        passing it to _from_row.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT {_COLUMNS}, COUNT(*) OVER() AS _total
                FROM certificates
                ORDER BY captured_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)

        if not rows:
            return [], 0

        total = rows[0]["_total"]
        return [self._from_row(r) for r in rows], total

    async def exists_by_hash(self, hash: Hash) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM certificates WHERE device_hash = $1", str(hash)
            )
        return row is not None

    async def find_clients(self) -> list[dict]:
        """
        Unique policyholders with at least one certificate.
        Returns: [{ dni, name, certificate_count, last_submission }]
        Mirrors SQLite implementation exactly.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    policyholder_dni   AS dni,
                    policyholder_name  AS name,
                    COUNT(*)           AS certificate_count,
                    MAX(captured_at)   AS last_submission
                FROM certificates
                WHERE policyholder_dni != ''
                GROUP BY policyholder_dni, policyholder_name
                ORDER BY last_submission DESC
            """)
        return [dict(r) for r in rows]

    async def find_by_dni(self, dni: str) -> list[Certificate]:
        """All certificates for a given policyholder DNI, newest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM certificates "
                "WHERE policyholder_dni = $1 "
                "ORDER BY captured_at DESC",
                dni,
            )
        return [self._from_row(r) for r in rows]

    # ── Row mapping ───────────────────────────────────────────────────────────

    def _to_row(self, cert: Certificate) -> tuple:
        """Domain entity → flat tuple for parameterised INSERT (matches _COLUMNS order)."""
        gps_data = None
        if cert.gps:
            gps_data = json.dumps({
                "latitude":        cert.gps.latitude,
                "longitude":       cert.gps.longitude,
                "accuracy_meters": cert.gps.accuracy_meters,
            })

        device_data = json.dumps({
            "device_id":   cert.device.device_id,
            "model":       cert.device.model,
            "os_version":  cert.device.os_version,
            "app_version": cert.device.app_version,
        })

        return (
            str(cert.id),
            cert.case_id,
            cert.file_info.name,
            cert.file_info.size_bytes,
            cert.file_info.mime_type,
            str(cert.device_hash),
            str(cert.server_hash) if cert.server_hash else "",
            cert.status.value,
            cert.captured_at,        # asyncpg handles datetime → TIMESTAMPTZ natively
            cert.certified_at,
            gps_data,                # JSONB string — None stored as SQL NULL
            device_data,
            cert.storage_path,
            cert.pdf_path,
            cert.policyholder_name,
            cert.policyholder_dni,
        )

    def _from_row(self, row: asyncpg.Record) -> Certificate:
        """
        Reconstruct a Certificate domain entity from a raw DB row.
        Uses Certificate.reconstitute() — the controlled factory for
        rebuilding persisted state, never __init__ directly.
        This is the anti-corruption layer — DB types never reach domain code.
        """
        gps = None
        gps_raw = row["gps_json"]
        if gps_raw:
            # asyncpg returns JSONB columns as Python dicts already
            g = gps_raw if isinstance(gps_raw, dict) else json.loads(gps_raw)
            gps = GPSCoordinates(
                latitude=g["latitude"],
                longitude=g["longitude"],
                accuracy_meters=g.get("accuracy_meters", 0.0),
            )

        d = row["device_json"]
        if isinstance(d, str):
            d = json.loads(d)
        device = DeviceInfo(
            device_id=d.get("device_id", ""),
            model=d.get("model", ""),
            os_version=d.get("os_version", ""),
            app_version=d.get("app_version", ""),
        )

        return Certificate.reconstitute(
            id=CertificateID(row["id"]),
            case_id=row["case_id"],
            file_info=FileInfo(
                name=row["file_name"],
                size_bytes=row["file_size"],
                mime_type=row["mime_type"],
            ),
            device_hash=Hash(row["device_hash"]),
            server_hash=Hash(row["server_hash"]) if row["server_hash"] else None,
            gps=gps,
            device=device,
            captured_at=_ensure_utc(row["captured_at"]),
            certified_at=_ensure_utc(row["certified_at"]) if row["certified_at"] else None,
            status=CertificateStatus(row["status"]),
            storage_path=row["storage_path"],
            pdf_path=row["pdf_path"],
            policyholder_name=row["policyholder_name"],
            policyholder_dni=row["policyholder_dni"],
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_utc(dt: datetime) -> datetime:
    """Normalise to UTC — asyncpg returns tz-aware datetimes, this is a safety net."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
