# Multi-stage production-hardened Dockerfile for Climate Eye View S2 Intelligence Service
FROM python:3.11-slim-bookworm AS builder

WORKDIR /install

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY intelligence/requirements.txt /install/requirements.txt
RUN pip install --no-cache-dir --prefix=/install/deps -r /install/requirements.txt


# Final Runtime Stage
FROM python:3.11-slim-bookworm AS runner

# Security: Create non-root system user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install/deps /usr/local

# Copy application and shared schemas
COPY intelligence /app/intelligence
COPY shared /app/shared
COPY config /app/config

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Fix ownership
RUN chown -R appuser:appgroup /app

# Drop to unprivileged user
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# Bounded operational health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "intelligence.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
