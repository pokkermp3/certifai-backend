"""
infrastructure/config.py

All configuration in one place.
Uses pydantic-settings so values can come from:
  - Environment variables (production)
  - A .env file (local development)
  - Defaults (zero-config startup)
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Storage paths
    database_path: str = "./certifai.db"
    upload_dir:    str = "./uploads"
    cert_dir:      str = "./certificates"

    # CORS — comma-separated origins, or * for all
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        env_prefix = "CERTIFAI_"


# Singleton — import this anywhere you need settings
settings = Settings()
