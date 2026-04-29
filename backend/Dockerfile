# ── Stage 1: build dependencies ─────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /build

# Install build tools needed for native extensions (asyncpg, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner
WORKDIR /app

# Only the runtime C library is needed at this stage (no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the build stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Run as a non-root user for security
RUN addgroup --system amendly && adduser --system --ingroup amendly amendly \
    && chown -R amendly:amendly /app
USER amendly

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
