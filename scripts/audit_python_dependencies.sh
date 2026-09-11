#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
requirements_file="$(mktemp "${TMPDIR:-/tmp}/antigravity-k-audit.XXXXXX")"
trap 'rm -f "${requirements_file}"' EXIT

uv export \
  --directory "${repo_root}" \
  --quiet \
  --frozen \
  --no-dev \
  --no-editable \
  --no-emit-project \
  --format requirements-txt \
  --output-file "${requirements_file}"

uvx --from 'pip-audit==2.10.1' pip-audit \
  --strict \
  --desc \
  --disable-pip \
  --requirement "${requirements_file}"
