"""
adapters/pdf/weasyprint_generator.py

Implements IPDFGenerator using WeasyPrint.
Generates a professional PDF certificate from an HTML template.

Why HTML → PDF instead of drawing primitives?
  - Much easier to maintain and style
  - Designers can edit the HTML/CSS without touching Python
  - WeasyPrint handles page layout, fonts, and QR codes cleanly
"""
import base64
import hashlib
import io
import json
from pathlib import Path

import qrcode
import qrcode.image.pil
from weasyprint import HTML

from domain import Certificate
from domain.errors import PDFGenerationError
from ports import IPDFGenerator


class WeasyprintGenerator(IPDFGenerator):

    def __init__(self, output_dir: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, certificate: Certificate) -> str:
        try:
            html = self._render_html(certificate)
            output_path = self._output_dir / f"{certificate.id}.pdf"
            HTML(string=html).write_pdf(str(output_path))
            return str(output_path)
        except Exception as e:
            raise PDFGenerationError(f"PDF generation failed: {e}") from e

    def _render_html(self, cert: Certificate) -> str:
        gps_section = ""
        if cert.has_gps():
            gps = cert.gps
            gps_section = f"""
            <div class="section">
                <div class="section-title">GPS LOCATION AT CAPTURE</div>
                <div class="grid">
                    <div class="row">
                        <span class="label">Coordinates</span>
                        <span class="value">{gps.latitude:.6f}, {gps.longitude:.6f}</span>
                    </div>
                    <div class="row">
                        <span class="label">Accuracy</span>
                        <span class="value">±{gps.accuracy_meters:.1f} meters</span>
                    </div>
                    <div class="row">
                        <span class="label">Maps Link</span>
                        <span class="value">
                            <a href="{gps.maps_url()}">{gps.maps_url()}</a>
                        </span>
                    </div>
                </div>
            </div>
            """

        hash_match = cert.is_integrity_verified()
        match_class = "match-ok" if hash_match else "match-fail"
        match_icon  = "✓" if hash_match else "✗"
        match_text  = (
            "HASHES MATCH — File has not been altered since capture"
            if hash_match else
            "HASH MISMATCH — File integrity cannot be guaranteed"
        )

        certified_at = (
            cert.certified_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if cert.certified_at else "—"
        )

        qr_data_uri = self._generate_qr(cert)

        server_hash_display = str(cert.server_hash) if cert.server_hash else "Not yet computed"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'DM Sans', Helvetica, sans-serif;
    color: #0f172a;
    font-size: 10px;
    line-height: 1.5;
  }}

  /* Header */
  .header {{
    background: #0a0f1e;
    padding: 20px 28px 0;
    border-bottom: 3px solid #00d4aa;
  }}
  .header-inner {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 16px;
  }}
  .brand {{ color: #fff; font-size: 22px; font-weight: 600; }}
  .brand span {{ color: #00d4aa; }}
  .tagline {{ color: #94a3b8; font-size: 9px; margin-top: 3px; }}
  .stamp {{
    background: #00d4aa;
    color: #0a0f1e;
    padding: 8px 14px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 10px;
  }}

  /* Body */
  .body {{ padding: 20px 28px; }}

  /* Sections */
  .section {{ margin-bottom: 16px; }}
  .section-title {{
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 4px;
    padding-bottom: 4px;
    border-bottom: 1px solid #e2e8f0;
  }}

  /* Info grid */
  .grid {{ display: table; width: 100%; }}
  .row {{ display: table-row; }}
  .label, .value {{
    display: table-cell;
    padding: 4px 0;
    border-bottom: 1px solid #f1f5f9;
  }}
  .label {{
    color: #64748b;
    width: 120px;
    font-size: 9px;
  }}
  .value {{ font-weight: 500; font-size: 9.5px; }}

  /* Hash blocks */
  .hash-block {{
    background: #0a0f1e;
    border: 1px solid #00d4aa;
    border-radius: 4px;
    padding: 8px 12px;
    font-family: 'DM Mono', monospace;
    font-size: 8px;
    color: #00d4aa;
    word-break: break-all;
    margin: 6px 0;
  }}
  .hash-block.server {{
    background: #f8fafc;
    border-color: #cbd5e1;
    color: #0f172a;
  }}
  .hash-label {{
    font-size: 8px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 3px;
  }}

  /* Match indicator */
  .match-box {{
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 9px;
    margin-top: 8px;
  }}
  .match-ok  {{ background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }}
  .match-fail {{ background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}

  /* QR section */
  .qr-row {{
    display: flex;
    gap: 16px;
    align-items: flex-start;
    margin-top: 8px;
  }}
  .qr-img {{ width: 90px; height: 90px; }}
  .qr-text {{ font-size: 8.5px; color: #64748b; line-height: 1.6; }}

  /* Footer */
  .footer {{
    border-top: 1px solid #e2e8f0;
    padding: 10px 28px;
    display: flex;
    justify-content: space-between;
    color: #94a3b8;
    font-size: 8px;
  }}

  a {{ color: #0d9488; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div>
      <div class="brand">Certif<span>AI</span></div>
      <div class="tagline">Cryptographic File Integrity Certificate</div>
    </div>
    <div class="stamp">✓ CERTIFIED</div>
  </div>
</div>

<div class="body">

  <!-- Certificate Info -->
  <div class="section">
    <div class="section-title">Certificate Information</div>
    <div class="grid">
      <div class="row">
        <span class="label">Certificate ID</span>
        <span class="value" style="font-family:monospace;font-size:8px">{cert.id}</span>
      </div>
      {"<div class='row'><span class='label'>Case / Claim ID</span><span class='value'>" + cert.case_id + "</span></div>" if cert.case_id else ""}
      <div class="row">
        <span class="label">Status</span>
        <span class="value">{cert.status.value.replace("_", " ").upper()}</span>
      </div>
      <div class="row">
        <span class="label">Certified At</span>
        <span class="value">{certified_at}</span>
      </div>
    </div>
  </div>

  <!-- File Info -->
  <div class="section">
    <div class="section-title">File Information</div>
    <div class="grid">
      <div class="row">
        <span class="label">File Name</span>
        <span class="value">{cert.file_info.name}</span>
      </div>
      <div class="row">
        <span class="label">File Type</span>
        <span class="value">{cert.file_info.file_type.value} ({cert.file_info.mime_type})</span>
      </div>
      <div class="row">
        <span class="label">File Size</span>
        <span class="value">{cert.file_info.size_human}</span>
      </div>
      <div class="row">
        <span class="label">Captured At</span>
        <span class="value">{cert.captured_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</span>
      </div>
    </div>
  </div>

  <!-- Hash Proof -->
  <div class="section">
    <div class="section-title">Cryptographic Proof — SHA-256</div>
    <div class="hash-label">Hash computed ON DEVICE at moment of capture:</div>
    <div class="hash-block">{cert.device_hash}</div>
    <div class="hash-label">Hash recomputed ON SERVER after upload (must match):</div>
    <div class="hash-block server">{server_hash_display}</div>
    <div class="match-box {match_class}">{match_icon} {match_text}</div>
  </div>

  <!-- GPS -->
  {gps_section}

  <!-- Device Info -->
  <div class="section">
    <div class="section-title">Capture Device</div>
    <div class="grid">
      <div class="row">
        <span class="label">Device Model</span>
        <span class="value">{cert.device.model or "—"}</span>
      </div>
      <div class="row">
        <span class="label">OS Version</span>
        <span class="value">{cert.device.os_version or "—"}</span>
      </div>
      <div class="row">
        <span class="label">App Version</span>
        <span class="value">{cert.device.app_version or "—"}</span>
      </div>
      <div class="row">
        <span class="label">Device ID</span>
        <span class="value" style="font-family:monospace;font-size:8px">{cert.device.device_id[:16] + "..." if cert.device.device_id else "—"}</span>
      </div>
    </div>
  </div>

  <!-- QR Code -->
  <div class="section">
    <div class="section-title">Verification QR Code</div>
    <div class="qr-row">
      <img class="qr-img" src="{qr_data_uri}" />
      <div class="qr-text">
        Scan to verify this certificate offline.<br><br>
        Contains: Certificate ID, SHA-256 hash,<br>
        capture timestamp and GPS coordinates.<br><br>
        No internet required to verify the hash.<br>
        Compare with the original file using<br>
        any SHA-256 tool.
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <span>CertifAI — Cryptographic File Integrity Platform</span>
  <span>This certificate is cryptographically verifiable</span>
</div>

</body>
</html>"""

    def _generate_qr(self, cert: Certificate) -> str:
        """Generate QR code as a base64 data URI for embedding in HTML."""
        payload = {
            "id":   str(cert.id),
            "hash": str(cert.device_hash),
            "ts":   cert.captured_at.isoformat(),
        }
        if cert.has_gps():
            payload["lat"] = cert.gps.latitude
            payload["lon"] = cert.gps.longitude

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(json.dumps(payload))
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
