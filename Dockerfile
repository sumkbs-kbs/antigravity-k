# Antigravity-K — Production Docker Image
#
# Multi-stage build:
#   1. Base: Python 3.12 slim
#   2. Builder: Install dependencies + build dashboard
#   3. Runtime: Minimal image with only what's needed

# ─── Stage 1: Base ──────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install only essential runtime utilities
# git is not included in the runtime image to reduce attack surface
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage 2: Python Dependencies ───────────────────────────────
FROM base AS python-deps

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package with all optional dependencies
RUN pip install --upgrade pip \
    && pip install -e ".[dev,rag]" \
    && pip install matplotlib numpy

# ─── Stage 3: Dashboard Build ───────────────────────────────────
FROM node:20-alpine AS dashboard-builder

WORKDIR /app/dashboard
COPY dashboard/ ./

RUN npm ci && npm run build

# ─── Stage 4: Runtime ───────────────────────────────────────────
FROM python-deps AS runtime

WORKDIR /app

# Copy dashboard build from builder
COPY --from=dashboard-builder /app/dashboard/dist/ ./dashboard/dist/

# Create data directories
RUN mkdir -p vault_data logs data

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "antigravity_k.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
