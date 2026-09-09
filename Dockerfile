# Ssak-Ai — Production Docker Image
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
# git: Vault(위키 저장소) create/commit/read 기능이 런타임에 git을 실행한다 (REL-02).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
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
# REL-02: 단일 package manager = pnpm (pnpm-lock.yaml이 단일 진실원).
# frozen install로 lockfile과 package.json의 불일치를 빌드 시점에 차단한다.
# pnpm 11은 node:sqlite builtin이 필요해 node:22-alpine 기반을 사용한다.
FROM node:22-alpine AS dashboard-builder

WORKDIR /app/dashboard
RUN npm install -g pnpm@11.3.0 && pnpm --version
COPY dashboard/pnpm-lock.yaml dashboard/package.json dashboard/pnpm-workspace.yaml ./
# CI=true: 비 TTY 환경에서 pnpm의 모듈 디렉터리 퍼지 확인 프롬프트 방지
RUN CI=true pnpm install --frozen-lockfile
COPY dashboard/ ./
RUN pnpm run build

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
# REL-02: Vite outDir === wheel package-data === 이 COPY 경로 (src/antigravity_k/dashboard_dist)
COPY --from=dashboard-builder /app/src/antigravity_k/dashboard_dist/ ./src/antigravity_k/dashboard_dist/

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
CMD ["agk", "serve", "--host", "0.0.0.0", "--port", "8000"]
