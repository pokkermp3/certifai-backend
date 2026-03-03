"""
adapters/http/route_utils.py

Shared utilities for HTTP route handlers.
Centralises input validation so every router benefits automatically.
"""
import re
from fastapi import HTTPException


_SAFE_ID = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')


def validate_certificate_id(certificate_id: str) -> str:
    """
    Validate and sanitize a certificate ID path parameter.
    Prevents path traversal attacks and injection via malformed IDs.
    Raises HTTP 400 if invalid.
    """
    if not _SAFE_ID.match(certificate_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid certificate ID format."
        )
    return certificate_id