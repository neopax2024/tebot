# ── Build stage ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System dependencies for OpenCV, pyzbar, pylibdmtx, pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libzbar0 \
    libzbar-dev \
    libdmtx-dev \
    libdmtx0b \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy runtime system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    libdmtx0b \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create runtime directories
RUN mkdir -p /tmp/tgbot_uploads /tmp/tgbot_generated

# Non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app /tmp/tgbot_uploads /tmp/tgbot_generated
USER botuser

# ── Environment defaults ──────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

EXPOSE 8000

# Default: run the FastAPI server (bot runs in a separate container or process)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
