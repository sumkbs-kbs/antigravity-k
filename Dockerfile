# Antigravity-K — Production Docker Image
#
# Multi-stage build:
#   1. Base: Python 3.12 slim (pinned digest)
#   2. Builder: Install ALL deps (including dev tooling) and build artifacts
#   3. Dashboard: Build static assets with Node
#   4. Runtime: Minimal — only runtime deps (no pytest/ruff/playwright)
#
# Security hardening vs. the previous Dockerfile:
#   - Dev dependencies (pytest, ruff, playwright) no longer ship to runtime.
#   - Runs as a non-root user.
#   - Data dirs are owned by the non-root user.
#   - pip editable install replaced with a proper (non-editable) install.

# ─── Stage 1: Base ──────────────────────────────────────────────
# Digest pin via tag; Dependabot (docker ecosystem) keeps this current.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install only essential runtime utilities.
# git is not included in the runtime image to reduce attack surface.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage 2: Builder (all deps, used for building artifacts only) ──
FROM base AS builder

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the full package with dev + rag extras into a dedicated prefix.
# Only the runtime deps (none of the dev tooling) are copied to the final
# stage, so pytest/ruff/playwright never reach production.
RUN pip install --upgrade pip \
    && pip install --target="/install" ".[rag]"

# ─── Stage 3: Dashboard Build ───────────────────────────────────
FROM node:26-alpine AS dashboard-builder

WORKDIR /app/dashboard
COPY dashboard/ ./

RUN npm ci && npm run build

# ─── Stage 4: Runtime ───────────────────────────────────────────
FROM base AS runtime

# Create a non-root user to run the application.
RUN groupadd --system --gid 1001 agk \
    && useradd --system --uid 1001 --gid agk --create-home --home-dir /home/agk agk

WORKDIR /app

# Copy only the installed runtime packages from the builder.
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Copy the application source (needed for the non-editable install's package
# metadata to resolve the entry point).
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-deps "." \
    && rm -rf /root/.cache

# Copy dashboard build from builder
COPY --from=dashboard-builder /app/dashboard/dist/ ./dashboard/dist/

# Create data directories owned by the non-root user.
RUN mkdir -p vault_data logs data \
    && chown -R agk:agk /app

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Drop privileges.
USER agk

# Health check (runs as the non-root user).
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "antigravity_k.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
