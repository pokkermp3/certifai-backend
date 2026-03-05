"""
infrastructure/config.py

All configuration in one place.
Uses pydantic-settings so values can come from:
  - Environment variables (production — all prefixed with CERTIFAI_)
  - A .env file (local development)
  - Defaults (zero-config local startup)

Production env vars to set in Render:
  CERTIFAI_DATABASE_URL      → Neon connection string
  CERTIFAI_R2_BUCKET         → certifai
  CERTIFAI_R2_ENDPOINT       → https://<account_id>.r2.cloudflarestorage.com
  CERTIFAI_R2_ACCESS_KEY_ID  → from Cloudflare R2 API token
  CERTIFAI_R2_SECRET_ACCESS_KEY → from Cloudflare R2 API token
  CERTIFAI_AGENT_PASSWORD    → your dashboard password
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Server ────────────────────────────────────────────────────────────────
    host:  str  = "0.0.0.0"
    port:  int  = 8080
    debug: bool = False

    # ── Auth ──────────────────────────────────────────────────────────────────
    agent_password: str = "certifai2025"

    # ── Database ──────────────────────────────────────────────────────────────
    # Set DATABASE_URL in production → uses PostgreSQL
    # Leave empty locally → uses SQLite (database_path)
    database_url:  str = ""
    database_path: str = "./certifai.db"

    # ── Storage ───────────────────────────────────────────────────────────────
    # Set R2_BUCKET in production → uses Cloudflare R2
    # Leave empty locally → uses local filesystem (upload_dir / cert_dir)
    upload_dir: str = "./uploads"
    cert_dir:   str = "./certificates"

    r2_bucket:            str = ""
    r2_endpoint:          str = ""
    r2_access_key_id:     str = ""
    r2_secret_access_key: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = "*"

    class Config:
        env_file   = ".env"
        env_prefix = "CERTIFAI_"   # all env vars must be prefixed — matches original


settings = Settings()