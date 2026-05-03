# ── Stage 1: base — install deps ──────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# gcc + libpq-dev needed to compile asyncpg and psycopg2 headers
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

# ── Stage 3: production ───────────────────────────────────────────────────────
FROM base AS production

# Non-root user — required by App Runner and good practice everywhere
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8080

# Single uvicorn worker — App Runner scales via instances, not threads.
# --no-access-log reduces CloudWatch noise (structlog handles request logging).
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--no-access-log"]
