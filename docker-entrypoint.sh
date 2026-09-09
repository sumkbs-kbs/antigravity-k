#!/bin/bash
# Ssak-Ai Docker Entrypoint
set -e

# If AGK_ACCESS_PIN is set, export it for the application
if [ -n "$AGK_ACCESS_PIN" ]; then
    export AGK_ACCESS_PIN
fi

# If AGK_CORS_ORIGINS is set, export it
if [ -n "$AGK_CORS_ORIGINS" ]; then
    export AGK_CORS_ORIGINS
fi

echo "Starting Ssak-Ai server..."

# REL-02: Vault Git 기능 계약 — 런타임 git 존재를 기동 시 검증 (실패 = 즉시 중단, fail-fast).
# vault_data가 마운트되지 않은 경우를 대비해 소유권도 점검한다.
if ! command -v git >/dev/null 2>&1; then
    echo "FATAL: git not found in runtime image — Vault create/commit/read will fail." >&2
    exit 1
fi
if [ -d "vault_data" ] && [ ! -w "vault_data" ]; then
    echo "FATAL: vault_data is not writable by $(id -un) — check volume permissions." >&2
    exit 1
fi

exec "$@"
