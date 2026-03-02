# CertifAI Backend

Python + FastAPI backend for the CertifAI file certification platform.

## Architecture

```
certifai-backend/
├── domain/              # Business logic — zero external dependencies
│   ├── certificate.py   # Certificate entity, Hash, GPS, DeviceInfo
│   └── errors.py        # Typed domain errors
│
├── ports/               # Interfaces (what the app needs from infrastructure)
│   ├── certificate_repo.py
│   └── outbound.py      # IFileStorage, IHasher, IPDFGenerator
│
├── application/         # Use cases — orchestrate domain + ports
│   ├── certify_file.py  # RegisterCapture + UploadFile
│   └── verify.py        # Verify + List + Download
│
├── adapters/            # Concrete implementations
│   ├── hashing/         # SHA-256
│   ├── storage/         # Local filesystem
│   ├── persistence/     # SQLite
│   ├── pdf/             # WeasyPrint
│   └── http/            # FastAPI routes + verifier UI
│
├── infrastructure/      # Wiring only
│   ├── container.py     # Dependency injection
│   └── config.py        # Settings (env vars / .env file)
│
├── tests/
│   └── unit/            # Domain tests — no DB, no HTTP needed
│
└── main.py              # Entry point
```

## Setup

### Requirements
- Python 3.12+
- WeasyPrint system dependencies (see below)

### Install

```bash
# Clone / download the project
cd certifai-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# WeasyPrint needs system fonts on Linux:
# sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0
```

### Run

```bash
# Development (auto-reload on file changes)
CERTIFAI_DEBUG=true python main.py

# Production
python main.py
```

### Environment variables

All variables are prefixed with `CERTIFAI_`.
Create a `.env` file or set them directly:

```env
CERTIFAI_PORT=8080
CERTIFAI_DATABASE_PATH=./certifai.db
CERTIFAI_UPLOAD_DIR=./uploads
CERTIFAI_CERT_DIR=./certificates
CERTIFAI_DEBUG=false
CERTIFAI_CORS_ORIGINS=*
```

## API

Once running, visit:
- **API docs**: http://localhost:8080/docs
- **Verifier UI**: http://localhost:8080/verify

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/certificates` | Register device hash (step 1) |
| POST | `/api/v1/certificates/{id}/upload` | Upload file (step 2) |
| GET  | `/api/v1/certificates/{id}` | Get certificate by ID |
| GET  | `/api/v1/certificates` | List all certificates |
| POST | `/api/v1/verify/hash` | Verify by hash or file upload |
| GET  | `/api/v1/download/pdf/{id}` | Download PDF certificate |
| GET  | `/api/v1/download/file/{id}` | Download original file |
| GET  | `/verify` | Verifier web UI |

## Running tests

```bash
pytest tests/unit/ -v
```

## Swapping implementations

To switch from SQLite to PostgreSQL:
1. Create `adapters/persistence/postgres_repo.py`
2. Implement `ICertificateRepository`
3. Change 1 line in `infrastructure/container.py`

To switch from local storage to S3:
1. Create `adapters/storage/s3_storage.py`
2. Implement `IFileStorage`
3. Change 1 line in `infrastructure/container.py`
