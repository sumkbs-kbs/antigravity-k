#!/usr/bin/env bash
# ============================================================================
# 대시보드 번들 출처 검증 (CR-11 / C11-05)
# ============================================================================
# 왜 필요한가
# -----------
# `src/antigravity_k/dashboard_dist`는 **추적 대상**이라 체크아웃에 오래된 번들이
# 들어 있다. CI가 대시보드를 다시 빌드하지 않고 `python -m build`만 돌리면,
# 그 wheel은 방금 만든 UI가 아니라 **커밋된 낡은 번들**을 포장한다. 그런데도
# 모든 게이트는 초록이다.
#
# 그래서 이 스크립트는 "빌드한 번들"과 "wheel에 들어간 번들"을 **hash로 대조**한다.
# 한 파일이라도 다르면 성공처럼 포장하지 않는다.
#
# 계약
# ----
#   대상: vite outDir(`dashboard/vite.config.ts`의 build.outDir) = 기본
#         `src/antigravity_k/dashboard_dist`
#   검사: ① 소스 디렉터리 파일 ↔ wheel 내부 `antigravity_k/dashboard_dist/**`
#         파일별 sha256 일치 ② 누락/추가 파일 없음 ③ 엔트리(index.html) 존재
#   기록: Node/pnpm 조합과 디렉터리 지문(BUNDLE-FINGERPRINT)을 항상 출력한다.
#   종료코드: 0 = 일치, 1 = 불일치, 2 = 사용법/인프라 오류
#
# 사용법
# -----
#   bash scripts/verify_dashboard_bundle.sh                # 대시보드 재빌드 후 검증
#   bash scripts/verify_dashboard_bundle.sh --skip-build   # 이미 빌드된 번들로 검증
#   bash scripts/verify_dashboard_bundle.sh --dist-root src/antigravity_k/dashboard_dist
# ============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXIT_PASS=0
EXIT_MISMATCH=1
EXIT_INFRA=2

SKIP_BUILD=0
DIST_ROOT="src/antigravity_k/dashboard_dist"
WHEEL_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) SKIP_BUILD=1; shift ;;
    --dist-root) DIST_ROOT="${2:?--dist-root 에는 경로가 필요합니다}"; shift 2 ;;
    -h|--help) sed -n '2,32p' "$0"; exit $EXIT_PASS ;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)" >&2; exit $EXIT_INFRA ;;
  esac
done

infra_error() {
  echo "BUNDLE-STATUS: INFRA_ERROR — $*" >&2
  exit $EXIT_INFRA
}

command -v uv >/dev/null || infra_error "uv 가 필요합니다"

# ─── 1. Node/pnpm 조합 기록(무엇으로 빌드했는지 먼저 남긴다) ────────────────
if [[ $SKIP_BUILD -eq 0 ]]; then
  command -v node >/dev/null || infra_error "node 가 필요합니다 (대시보드 빌드)"
  command -v pnpm >/dev/null || infra_error "pnpm 이 필요합니다 (대시보드 빌드)"
fi

NODE_VERSION="$(node --version 2>/dev/null || echo 'unknown')"
PNPM_VERSION="$(pnpm --version 2>/dev/null || echo 'unknown')"
echo "BUNDLE-ENV: {\"node\":\"${NODE_VERSION}\",\"pnpm\":\"${PNPM_VERSION}\"}"

# ─── 2. 대시보드 재빌드(선택) ─────────────────────────────────────────────
if [[ $SKIP_BUILD -eq 1 ]]; then
  echo "BUNDLE-NOTE: --skip-build — 현재 트리의 번들을 그대로 검사합니다"
else
  echo "BUNDLE-STEP: pnpm --dir dashboard build"
  if ! pnpm --dir dashboard build; then
    infra_error "대시보드 빌드 실패"
  fi
fi

[[ -d "$DIST_ROOT" ]] || infra_error "번들 디렉터리가 없습니다: $DIST_ROOT"
[[ -f "$DIST_ROOT/index.html" ]] || infra_error "번들 엔트리가 없습니다: $DIST_ROOT/index.html"

# ─── 3. wheel 빌드 ────────────────────────────────────────────────────────
WHEEL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/agk-bundle-XXXXXX")"
trap 'rm -rf "$WHEEL_DIR"' EXIT

if ! uv build --no-sources --wheel --out-dir "$WHEEL_DIR" >"$WHEEL_DIR/build.log" 2>&1; then
  sed -n '1,40p' "$WHEEL_DIR/build.log" >&2 || true
  infra_error "wheel 빌드 실패"
fi

WHEEL_PATH="$(ls -t "$WHEEL_DIR"/antigravity_k-*.whl 2>/dev/null | head -1)"
[[ -n "$WHEEL_PATH" ]] || infra_error "빌드된 wheel 을 찾지 못했습니다"

# ─── 4. 소스 번들 ↔ wheel 내부 번들 hash 대조 ─────────────────────────────
AGK_DIST_ROOT="$DIST_ROOT" AGK_WHEEL="$WHEEL_PATH" python3 - <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path
from zipfile import ZipFile

dist_root = Path(os.environ["AGK_DIST_ROOT"]).resolve()
wheel_path = Path(os.environ["AGK_WHEEL"])
wheel_prefix = "antigravity_k/dashboard_dist/"

source: dict[str, str] = {}
for path in sorted(dist_root.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(dist_root).as_posix()
    source[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

with ZipFile(wheel_path) as wheel:
    packaged: dict[str, str] = {}
    for member in wheel.namelist():
        if not member.startswith(wheel_prefix) or member.endswith("/"):
            continue
        rel = member[len(wheel_prefix):]
        packaged[rel] = hashlib.sha256(wheel.read(member)).hexdigest()

missing = sorted(set(source) - set(packaged))
extra = sorted(set(packaged) - set(source))
changed = sorted(name for name in set(source) & set(packaged) if source[name] != packaged[name])


def fingerprint(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(files[name].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


report = {
    "schema": "agk-dashboard-bundle/1",
    "dist_root": dist_root.relative_to(Path.cwd()).as_posix() if dist_root.is_relative_to(Path.cwd()) else str(dist_root),
    "wheel": wheel_path.name,
    "source_files": len(source),
    "packaged_files": len(packaged),
    "source_fingerprint": fingerprint(source),
    "packaged_fingerprint": fingerprint(packaged),
    "missing_in_wheel": missing[:20],
    "extra_in_wheel": extra[:20],
    "content_mismatch": changed[:20],
}
print("BUNDLE-FINGERPRINT: " + json.dumps(report, ensure_ascii=False, separators=(",", ":")))

if "index.html" not in packaged:
    print("BUNDLE-STATUS: MISMATCH — wheel 에 dashboard_dist/index.html 이 없습니다", file=sys.stderr)
    raise SystemExit(1)
if missing or extra or changed:
    print("BUNDLE-STATUS: MISMATCH — 빌드한 번들과 wheel 내부 번들이 다릅니다", file=sys.stderr)
    raise SystemExit(1)
print("BUNDLE-STATUS: PASS — 빌드한 번들이 그대로 wheel 에 들어갔습니다")
raise SystemExit(0)
PY
status=$?

if [[ $status -eq 0 ]]; then
  exit $EXIT_PASS
fi
exit $EXIT_MISMATCH
