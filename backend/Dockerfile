# ── Stage 1: base — shared deps ───────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System deps needed to compile asyncpg + cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: development — adds watchfiles for hot reload ─────────────────────
FROM base AS development

RUN pip install --no-cache-dir watchfiles

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ── Stage 3: production — non-root user, no extras ───────────────────────────
FROM base AS production

# Run as non-root for security (App Runner requirement)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8080

# Single worker — App Runner scales via instances, not threads
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
