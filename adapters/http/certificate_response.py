"""
adapters/http/certificate_response.py

HTTP response model for Certificate domain objects.
Extracted from routes.py so all routers share the same mapping.
Single Responsibility: one file, one job — domain → HTTP response.
"""
from typing import Optional
from pydantic import BaseModel
from domain import Certificate


class CertificateResponse(BaseModel):
    id: str
    case_id: str
    file_name: str
    file_size: int
    mime_type: str
    file_type: str
    device_hash: str
    server_hash: Optional[str]
    status: str
    hash_verified: bool
    captured_at: str
    certified_at: Optional[str]
    gps_lat: Optional[float]
    gps_lon: Optional[float]
    gps_accuracy: Optional[float]
    gps_maps_url: Optional[str]
    device_model: str
    os_version: str
    app_version: str
    pdf_url: Optional[str]
    file_url: Optional[str]

    @classmethod
    def from_domain(cls, cert: Certificate) -> "CertificateResponse":
        return cls(
            id=str(cert.id),
            case_id=cert.case_id,
            file_name=cert.file_info.name,
            file_size=cert.file_info.size_bytes,
            mime_type=cert.file_info.mime_type,
            file_type=cert.file_info.file_type.value,
            device_hash=str(cert.device_hash),
            server_hash=str(cert.server_hash) if cert.server_hash else None,
            status=cert.status.value,
            hash_verified=cert.is_integrity_verified(),
            captured_at=cert.captured_at.isoformat(),
            certified_at=cert.certified_at.isoformat() if cert.certified_at else None,
            gps_lat=cert.gps.latitude if cert.gps else None,
            gps_lon=cert.gps.longitude if cert.gps else None,
            gps_accuracy=cert.gps.accuracy_meters if cert.gps else None,
            gps_maps_url=cert.gps.maps_url() if cert.gps else None,
            device_model=cert.device.model,
            os_version=cert.device.os_version,
            app_version=cert.device.app_version,
            pdf_url=f"/api/v1/download/pdf/{cert.id}" if cert.has_pdf() else None,
            file_url=f"/api/v1/download/file/{cert.id}" if cert.storage_path else None,
        )