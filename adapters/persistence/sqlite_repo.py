"""
adapters/persistence/sqlite_repo.py

Implements ICertificateRepository using SQLite via aiosqlite.
This is the anti-corruption layer — raw DB types never leak into the domain.

The mapping (DB row → domain entity) is the most important part of this file.
It reconstructs the Certificate entity from persisted state.
"""
import json
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

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


class SQLiteCertificateRepository(ICertificateRepository):

    def __init__(self, db_path: str):
        self._db_path = db_path

    async def init(self) -> None:
        """Create tables if they don't exist. Call once at startup."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS certificates (
                    id            TEXT PRIMARY KEY,
                    case_id       TEXT    NOT NULL DEFAULT '',
                    file_name     TEXT    NOT NULL,
                    file_size     INTEGER NOT NULL DEFAULT 0,
                    mime_type     TEXT    NOT NULL DEFAULT '',
                    device_hash   TEXT    NOT NULL,
                    server_hash   TEXT    NOT NULL DEFAULT '',
                    status        TEXT    NOT NULL DEFAULT 'pending_upload',
                    captured_at   TEXT    NOT NULL,
                    certified_at  TEXT,
                    gps_json      TEXT    NOT NULL DEFAULT 'null',
                    device_json   TEXT    NOT NULL DEFAULT '{}',
                    storage_path  TEXT    NOT NULL DEFAULT '',
                    pdf_path      TEXT    NOT NULL DEFAULT '',
                    policyholder_name  TEXT NOT NULL DEFAULT '',
                    policyholder_dni   TEXT NOT NULL DEFAULT ''
                )
            """)
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uidx_device_hash "
                "ON certificates(device_hash)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_server_hash "
                "ON certificates(server_hash)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_captured_at "
                "ON certificates(captured_at DESC)"
            )
            await db.commit()
        async with aiosqlite.connect(self._db_path) as db:
            for col, definition in [
                ("policyholder_name", "TEXT NOT NULL DEFAULT ''"),
                ("policyholder_dni",  "TEXT NOT NULL DEFAULT ''"),
            ]:
                try:
                    await db.execute(
                        f"ALTER TABLE certificates ADD COLUMN {col} {definition}"
                    )
                except Exception:
                    pass  # column already exists
            await db.commit()
    # ── ICertificateRepository ────────────────────────────────────────────────

    async def save(self, cert: Certificate) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO certificates (
                        id, case_id, file_name, file_size, mime_type,
                        device_hash, server_hash, status, captured_at,
                        certified_at, gps_json, device_json,
                        storage_path, pdf_path,
                        policyholder_name, policyholder_dni
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, self._to_row(cert))
                await db.commit()
            except aiosqlite.IntegrityError as e:
                if "UNIQUE constraint failed: certificates.device_hash" in str(e):
                    raise HashAlreadyExistsError(str(cert.device_hash))
                raise

    async def update(self, cert: Certificate) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                UPDATE certificates SET
                    server_hash  = ?,
                    status       = ?,
                    certified_at = ?,
                    storage_path = ?,
                    pdf_path     = ?
                WHERE id = ?
            """, (
                str(cert.server_hash) if cert.server_hash else "",
                cert.status.value,
                _dt_to_str(cert.certified_at),
                cert.storage_path,
                cert.pdf_path,
                str(cert.id),
            ))
            await db.commit()

    async def find_by_id(
        self, id: CertificateID
    ) -> Optional[Certificate]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM certificates WHERE id = ?",
                (str(id),)
            ) as cursor:
                row = await cursor.fetchone()
                return self._from_row(row) if row else None

    async def find_by_hash(
        self, hash: Hash
    ) -> Optional[Certificate]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM certificates "
                "WHERE device_hash = ? OR server_hash = ?",
                (str(hash), str(hash))
            ) as cursor:
                row = await cursor.fetchone()
                return self._from_row(row) if row else None

    async def find_all(
        self, limit: int, offset: int
    ) -> tuple[list[Certificate], int]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT * FROM certificates "
                "ORDER BY captured_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()

            async with db.execute(
                "SELECT COUNT(*) FROM certificates"
            ) as cursor:
                total = (await cursor.fetchone())[0]

        return [self._from_row(r) for r in rows], total

    async def exists_by_hash(self, hash: Hash) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT 1 FROM certificates WHERE device_hash = ?",
                (str(hash),)
            ) as cursor:
                return await cursor.fetchone() is not None

    # ── Row mapping ───────────────────────────────────────────────────────────

    def _to_row(self, cert: Certificate) -> tuple:
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
            _dt_to_str(cert.captured_at),
            _dt_to_str(cert.certified_at),
            gps_data or "null",
            device_data,
            cert.storage_path,
            cert.pdf_path,
            cert.policyholder_name,
            cert.policyholder_dni,
        )

    def _from_row(self, row: aiosqlite.Row) -> Certificate:
        """
        Reconstruct a Certificate domain entity from a raw database row.
        Uses Certificate.reconstitute() — the controlled factory method for
        rebuilding persisted state. Never calls __init__ directly.
        This is the anti-corruption layer — DB types never reach domain code.
        """
        gps = None
        gps_raw = row["gps_json"]
        if gps_raw and gps_raw != "null":
            g = json.loads(gps_raw)
            gps = GPSCoordinates(
                latitude=g["latitude"],
                longitude=g["longitude"],
                accuracy_meters=g.get("accuracy_meters", 0.0),
            )

        d = json.loads(row["device_json"])
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
            captured_at=_str_to_dt(row["captured_at"]),
            certified_at=_str_to_dt(row["certified_at"]) if row["certified_at"] else None,
            status=CertificateStatus(row["status"]),
            storage_path=row["storage_path"],
            pdf_path=row["pdf_path"],
            policyholder_name=row["policyholder_name"],
            policyholder_dni=row["policyholder_dni"],
        )
    async def find_clients(self) -> list[dict]:
        """Unique policyholders with at least one certificate."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT
                    policyholder_dni   AS dni,
                    policyholder_name  AS name,
                    COUNT(*)           AS certificate_count,
                    MAX(captured_at)   AS last_submission
                FROM certificates
                WHERE policyholder_dni != ''
                GROUP BY policyholder_dni
                ORDER BY last_submission DESC
            """) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def find_by_dni(self, dni: str) -> list[Certificate]:
        """All certificates for a given policyholder DNI, newest first."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM certificates "
                "WHERE policyholder_dni = ? "
                "ORDER BY captured_at DESC",
                (dni,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._from_row(r) for r in rows]


# ── Date helpers ──────────────────────────────────────────────────────────────

def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
