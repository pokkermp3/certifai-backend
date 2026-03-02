"""
domain/errors.py

All domain errors are typed classes.
This means callers can catch specific errors without comparing strings.

Example:
    try:
        await use_case.certify(...)
    except CertificateNotFoundError:
        return 404
    except HashAlreadyExistsError:
        return 409
"""


class CertifAIError(Exception):
    """Base class for all CertifAI domain errors."""
    pass


class CertificateNotFoundError(CertifAIError):
    """Raised when a certificate lookup returns no result."""
    def __init__(self, identifier: str):
        super().__init__(f"Certificate not found: {identifier}")
        self.identifier = identifier


class HashAlreadyExistsError(CertifAIError):
    """
    Raised when trying to certify a file that was already certified.
    The same hash cannot be registered twice — prevents duplicate certifications.
    """
    def __init__(self, hash_value: str):
        super().__init__(
            f"A certificate with this hash already exists: {hash_value[:16]}..."
        )
        self.hash_value = hash_value


class InvalidCertificateStateError(CertifAIError):
    """Raised when a state transition is not allowed."""
    pass


class FileStorageError(CertifAIError):
    """Raised when file storage operations fail."""
    pass


class FileNotFoundError(CertifAIError):
    """Raised when a stored file cannot be located."""
    def __init__(self, path: str):
        super().__init__(f"File not found in storage: {path}")
        self.path = path


class PDFGenerationError(CertifAIError):
    """Raised when PDF certificate generation fails."""
    pass


class PDFNotGeneratedError(CertifAIError):
    """Raised when trying to download a PDF that hasn't been generated yet."""
    def __init__(self, certificate_id: str):
        super().__init__(
            f"PDF not yet generated for certificate: {certificate_id}"
        )
        self.certificate_id = certificate_id


class HashingError(CertifAIError):
    """Raised when file hashing fails."""
    pass


class InvalidHashError(CertifAIError):
    """Raised when a hash string is not valid SHA-256 format."""
    def __init__(self, value: str):
        super().__init__(
            f"Invalid hash format: '{value[:20]}...' "
            f"(expected 64 hex characters)"
        )
        self.value = value
