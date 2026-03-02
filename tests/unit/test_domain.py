"""
tests/unit/test_domain.py

Domain layer unit tests.
No mocks, no database, no HTTP — pure Python.

This is one of the key benefits of hexagonal architecture:
domain logic is completely isolated and trivially testable.
"""
import pytest
from datetime import datetime, timezone

from domain import (
    Certificate,
    CertificateID,
    CertificateStatus,
    DeviceInfo,
    FileInfo,
    GPSCoordinates,
    Hash,
)


# ── Test fixtures ─────────────────────────────────────────────────────────────

HASH_A = Hash("a" * 64)
HASH_B = Hash("b" * 64)

def make_certificate(device_hash: Hash = HASH_A) -> Certificate:
    return Certificate.register(
        id=CertificateID("test-cert-001"),
        case_id="CLAIM-2024-001",
        file_info=FileInfo(name="damage.jpg", size_bytes=2_400_000, mime_type="image/jpeg"),
        device_hash=device_hash,
        gps=GPSCoordinates(40.4168, -3.7038, 5.0),
        device=DeviceInfo(
            device_id="device-uuid-123",
            model="iPhone 15 Pro",
            os_version="iOS 17.4",
            app_version="1.0.0",
        ),
        captured_at=datetime(2024, 3, 15, 14, 23, 7, tzinfo=timezone.utc),
    )


# ── Hash value object ─────────────────────────────────────────────────────────

class TestHash:

    def test_valid_hash_created(self):
        assert str(Hash("a" * 64)) == "a" * 64

    def test_hash_is_lowercased(self):
        assert str(Hash("A" * 64)) == "a" * 64

    def test_hash_too_short_raises(self):
        with pytest.raises(ValueError, match="64 hex characters"):
            Hash("abc")

    def test_hash_too_long_raises(self):
        with pytest.raises(ValueError):
            Hash("a" * 65)

    def test_invalid_chars_raises(self):
        with pytest.raises(ValueError, match="hex"):
            Hash("g" * 64)

    def test_matching_hashes_equal(self):
        assert Hash("b" * 64).matches(Hash("b" * 64))

    def test_different_hashes_not_equal(self):
        assert not Hash("a" * 64).matches(Hash("b" * 64))

    def test_short_display(self):
        h = Hash("a" * 64)
        assert h.short() == "a" * 16 + "..."


# ── GPS value object ──────────────────────────────────────────────────────────

class TestGPSCoordinates:

    def test_valid_coordinates(self):
        gps = GPSCoordinates(40.4168, -3.7038, 5.0)
        assert gps.latitude == 40.4168
        assert gps.longitude == -3.7038

    def test_latitude_out_of_range_raises(self):
        with pytest.raises(ValueError, match="Latitude"):
            GPSCoordinates(91.0, 0.0)

    def test_longitude_out_of_range_raises(self):
        with pytest.raises(ValueError, match="Longitude"):
            GPSCoordinates(0.0, 181.0)

    def test_maps_url_contains_coordinates(self):
        url = GPSCoordinates(40.4168, -3.7038).maps_url()
        assert "maps.google.com" in url
        assert "40.416800" in url


# ── Certificate entity ────────────────────────────────────────────────────────

class TestCertificateRegisterFactory:

    def test_new_certificate_is_pending(self):
        assert make_certificate().status == CertificateStatus.PENDING_UPLOAD

    def test_new_certificate_is_not_verified(self):
        assert not make_certificate().is_integrity_verified()

    def test_new_certificate_has_no_server_hash(self):
        assert make_certificate().server_hash is None

    def test_new_certificate_has_no_certified_at(self):
        assert make_certificate().certified_at is None


class TestCertificateReconstitute:

    def test_reconstitute_restores_certified_status(self):
        cert = Certificate.reconstitute(
            id=CertificateID("r-001"),
            case_id="",
            file_info=FileInfo("f.jpg", 1000, "image/jpeg"),
            device_hash=HASH_A,
            server_hash=HASH_A,
            gps=None,
            device=DeviceInfo("d", "iPhone", "iOS", "1.0"),
            captured_at=datetime.now(timezone.utc),
            status=CertificateStatus.CERTIFIED,
            certified_at=datetime.now(timezone.utc),
            storage_path="/storage/f.jpg",
        )
        assert cert.status == CertificateStatus.CERTIFIED
        assert cert.is_integrity_verified()

    def test_reconstitute_restores_mismatch_status(self):
        cert = Certificate.reconstitute(
            id=CertificateID("r-002"),
            case_id="",
            file_info=FileInfo("f.jpg", 1000, "image/jpeg"),
            device_hash=HASH_A,
            server_hash=HASH_B,  # different — mismatch
            gps=None,
            device=DeviceInfo("d", "iPhone", "iOS", "1.0"),
            captured_at=datetime.now(timezone.utc),
            status=CertificateStatus.HASH_MISMATCH,
            certified_at=datetime.now(timezone.utc),
            storage_path="/storage/f.jpg",
        )
        assert cert.status == CertificateStatus.HASH_MISMATCH
        assert not cert.is_integrity_verified()


class TestCertificate:

    def test_certify_matching_hash_sets_certified(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_A, "/storage/cert.jpg")
        assert cert.status == CertificateStatus.CERTIFIED

    def test_certify_matching_hash_verifies_integrity(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_A, "/storage/cert.jpg")
        assert cert.is_integrity_verified()

    def test_certify_different_hash_sets_mismatch(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_B, "/storage/cert.jpg")
        assert cert.status == CertificateStatus.HASH_MISMATCH

    def test_certify_different_hash_fails_integrity(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_B, "/storage/cert.jpg")
        assert not cert.is_integrity_verified()

    def test_certify_sets_certified_at(self):
        cert = make_certificate()
        cert.certify(HASH_A, "/storage/cert.jpg")
        assert cert.certified_at is not None

    def test_double_certify_raises(self):
        cert = make_certificate()
        cert.certify(HASH_A, "/storage/cert.jpg")
        with pytest.raises(ValueError, match="PENDING_UPLOAD"):
            cert.certify(HASH_A, "/storage/cert.jpg")

    def test_has_gps_when_gps_provided(self):
        assert make_certificate().has_gps()

    def test_no_gps_when_not_provided(self):
        cert = Certificate.register(
            id=CertificateID("no-gps"),
            case_id="",
            file_info=FileInfo("f.jpg", 1000, "image/jpeg"),
            device_hash=HASH_A,
            gps=None,
            device=DeviceInfo("d", "iPhone", "iOS", "1.0"),
            captured_at=datetime.now(timezone.utc),
        )
        assert not cert.has_gps()

    def test_has_pdf_after_set(self):
        cert = make_certificate()
        assert not cert.has_pdf()
        cert.set_pdf_path("/certs/abc.pdf")
        assert cert.has_pdf()

    def test_file_size_human_readable(self):
        cert = make_certificate()
        assert "MB" in cert.file_info.size_human


class TestVerificationMessage:

    def test_certified_message(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_A, "/s")
        msg = cert.verification_message()
        assert "confirmed" in msg.lower()

    def test_mismatch_message_contains_warning(self):
        cert = make_certificate(HASH_A)
        cert.certify(HASH_B, "/s")
        msg = cert.verification_message()
        assert "WARNING" in msg

    def test_pending_certificate_message_contains_warning(self):
        # A pending certificate is not verified — message should reflect that
        cert = make_certificate()
        msg = cert.verification_message()
        assert "WARNING" in msg


class TestEncapsulation:
    """
    Verify that Certificate state can only be changed via business methods.
    Properties are read-only — no public setters.
    """

    def test_no_public_setter_for_status(self):
        cert = make_certificate()
        with pytest.raises(AttributeError):
            cert.status = CertificateStatus.CERTIFIED  # type: ignore

    def test_no_public_setter_for_device_hash(self):
        cert = make_certificate()
        with pytest.raises(AttributeError):
            cert.device_hash = HASH_B  # type: ignore

    def test_no_public_setter_for_server_hash(self):
        cert = make_certificate()
        with pytest.raises(AttributeError):
            cert.server_hash = HASH_A  # type: ignore
