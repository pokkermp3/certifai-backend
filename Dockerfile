# Using slim to keep image small — critical for Render free tier cold starts
FROM python:3.12-slim

# WeasyPrint system dependencies for PDF generation
# Verified package names for Debian bookworm (python:3.12-slim base)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fontconfig \
        fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first — Docker layer cache means pip only re-runs
# when requirements.txt actually changes, not on every code change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8080

# Single worker — Render free tier has 512 MB RAM, multiple workers would OOM
CMD ["python", "main.py"]