#!/usr/bin/env bash
# ============================================================================
# 배포 아티팩트 검증 — 저장소 밖 설치 (CR-11 / C11-01, C11-04)
# ============================================================================
# 왜 필요한가
# -----------
# ① `pip install -e ".[dev]"`(editable) + `PYTHONPATH=src`로 돌린 스모크는
#    **저장소 트리가 sys.path에 있기 때문에** 통과한다. 배포된 wheel 에서
#    어떤 파일이 빠져 있어도 그 사실을 알 수 없다.
# ② CI는 설치 후에도 cwd가 저장소라서 `python -m antigravity_k...`가
#    src-layout 우연(현재 디렉터리)으로 import 될 수 있다.
#
# 그래서 이 스크립트는 **저장소 밖**의 임시 디렉터리에서, **신규 venv**에
# wheel/sdist 를 실제로 설치한 뒤 CLI/API/auth 를 실행한다.
#
# 계약
# ----
#   대상: build 산출물 wheel + sdist (`--dist-dir`, 기본 `dist/`)
#   검사: 각 아티팩트마다 신규 venv 설치 →
#         ① 설치된 `antigravity_k`가 저장소 밖(site-packages)에서 온다
#         ② CLI   : `agk --version` (콘솔 스크립트) + `agk model list`
#         ③ 모듈  : `python -m antigravity_k.engine.release_sbom --help`
#                   (editable/PYTHONPATH 없이 내부 모듈 실행)
#         ④ API   : FastAPI TestClient 로 `/health` 200
#         ⑤ auth  : 토큰 발급/검증·PIN 해시/검증·정책 결정
#         ⑥ 의존성: `pip check`
#   종료코드: 0 = 통과, 1 = 아티팩트 실패, 2 = 사용법/인프라 오류
#
# 사용법
# -----
#   bash scripts/verify_release_artifacts.sh                 # build 후 wheel+sdist 검증
#   bash scripts/verify_release_artifacts.sh --skip-build    # 기존 dist/ 로 검증
#   bash scripts/verify_release_artifacts.sh --dist-dir out  # 다른 산출물 디렉터리
# ============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXIT_PASS=0
EXIT_FAIL=1
EXIT_INFRA=2

DIST_DIR="dist"
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dist-dir) DIST_DIR="${2:?--dist-dir 에는 경로가 필요합니다}"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -h|--help) sed -n '2,36p' "$0"; exit $EXIT_PASS ;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)" >&2; exit $EXIT_INFRA ;;
  esac
done

infra_error() {
  echo "ARTIFACT-STATUS: INFRA_ERROR — $*" >&2
  exit $EXIT_INFRA
}

command -v uv >/dev/null || infra_error "uv 가 필요합니다"

# ─── 1. 산출물 확보 ──────────────────────────────────────────────────────
if [[ $SKIP_BUILD -eq 1 ]]; then
  echo "ARTIFACT-NOTE: --skip-build — 기존 $DIST_DIR 산출물을 사용합니다"
else
  rm -rf "$DIST_DIR"
  if ! uv build --no-sources --out-dir "$DIST_DIR" >/tmp/agk-artifact-build.log 2>&1; then
    sed -n '1,40p' /tmp/agk-artifact-build.log >&2 || true
    infra_error "uv build 실패"
  fi
fi

WHEEL="$(ls -t "$DIST_DIR"/antigravity_k-*.whl 2>/dev/null | head -1)"
SDIST="$(ls -t "$DIST_DIR"/antigravity_k-*.tar.gz 2>/dev/null | head -1)"
[[ -n "$WHEEL" ]] || infra_error "wheel 을 찾지 못했습니다: $DIST_DIR"
[[ -n "$SDIST" ]] || infra_error "sdist 를 찾지 못했습니다: $DIST_DIR"

echo "ARTIFACT-INPUTS: {\"wheel\":\"$(basename "$WHEEL")\",\"sdist\":\"$(basename "$SDIST")\"}"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/agk-artifacts-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# ─── 2. 아티팩트별 스모크 ────────────────────────────────────────────────
run_artifact() {  # $1 = kind(wheel|sdist), $2 = 경로
  local kind="$1" artifact="$2"
  local venv="$TMP/$kind/venv" cwd="$TMP/$kind/cwd" log="$TMP/$kind.log"
  local status="PASS"
  mkdir -p "$(dirname "$venv")" "$cwd"

  local python="$venv/bin/python"
  if [[ "$OS_FAMILY" == "windows" ]]; then python="$venv/Scripts/python.exe"; fi

  # --seed: 실제 pip 를 넣어 `pip check`와 콘솔 스크립트를 그대로 검증한다.
  if ! uv venv --seed "$venv" >"$log" 2>&1; then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"venv\"}"
    sed -n '1,20p' "$log" >&2
    return 1
  fi

  if ! uv pip install --python "$python" "$artifact" >>"$log" 2>&1; then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"install\"}"
    sed -n '1,30p' "$log" >&2
    return 1
  fi

  # ①③④⑤ 모듈/API/auth — 저장소 밖 cwd, PYTHONPATH 제거
  if ! (cd "$cwd" && env -u PYTHONPATH AGK_REPO_ROOT="$REPO_ROOT" "$python" - <<'PY' >>"$log" 2>&1
import json
import os
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ["AGK_REPO_ROOT"]).resolve()
import antigravity_k

installed = Path(antigravity_k.__file__).resolve()
assert not installed.is_relative_to(repo), f"저장소 트리에서 import 됨: {installed}"
assert repo.as_posix() not in [Path(p).resolve().as_posix() for p in sys.path if p], "저장소가 sys.path 에 있음"

from fastapi.testclient import TestClient

from antigravity_k.api.auth_policy import resolve_auth_decision
from antigravity_k.api.server import app
from antigravity_k.engine.auth import TokenService, hash_pin, verify_pin

client = TestClient(app)
health = client.get("/health")
assert health.status_code == 200, f"/health {health.status_code}"

secret_dir = Path(tempfile.mkdtemp()) / "secret"
service = TokenService(secret_dir)
token = service.issue_token("install-smoke")
assert service.verify_token(token), "토큰 검증 실패"
assert not service.verify_token(token + "x"), "변조 토큰이 통과함"

pin_hash = hash_pin("1234")
assert verify_pin("1234", pin_hash) and not verify_pin("9999", pin_hash), "PIN 검증 실패"
decision = resolve_auth_decision(
    stored_pin_hash=None, plaintext_pin_configured="", host="127.0.0.1", dev_no_pin_allow=True
)
assert decision.level == "open_loopback", f"정책 결정 이상: {decision!r}"

print(json.dumps({
    "package": antigravity_k.__version__,
    "module_path": installed.as_posix(),
    "routes": len(app.routes),
    "health": health.status_code,
}, ensure_ascii=False))
PY
  ); then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"module-api-auth\"}"
    tail -20 "$log" >&2
    return 1
  fi

  local agk="$venv/bin/agk"
  if [[ "$OS_FAMILY" == "windows" ]]; then agk="$venv/Scripts/agk.exe"; fi
  if [[ ! -x "$agk" ]]; then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"console-script\"}"
    return 1
  fi
  if ! (cd "$cwd" && env -u PYTHONPATH "$agk" --version >>"$log" 2>&1); then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"cli-version\"}"
    tail -20 "$log" >&2
    return 1
  fi
  if ! (cd "$cwd" && env -u PYTHONPATH "$agk" model list >>"$log" 2>&1); then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"cli-model-list\"}"
    tail -20 "$log" >&2
    return 1
  fi

  # ③ 내부 모듈 실행 — editable/PYTHONPATH 없이
  if ! (cd "$cwd" && env -u PYTHONPATH "$python" -m antigravity_k.engine.release_sbom --help >>"$log" 2>&1); then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"module-entrypoint\"}"
    tail -20 "$log" >&2
    return 1
  fi

  # ⑥ 의존성 정합성
  if ! "$venv/bin/pip" check >>"$log" 2>&1; then
    echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"FAIL\",\"step\":\"pip-check\"}"
    tail -20 "$log" >&2
    return 1
  fi

  echo "ARTIFACT-RESULT: {\"kind\":\"$kind\",\"status\":\"$status\",\"artifact\":\"$(basename "$artifact")\"}"
  return 0
}

case "$(uname -s)" in
  *Windows*|*MSYS*|*CYGWIN*) OS_FAMILY="windows" ;;
  *) OS_FAMILY="posix" ;;
esac

FAILED=0
run_artifact wheel "$WHEEL" || FAILED=1
run_artifact sdist "$SDIST" || FAILED=1

if [[ $FAILED -eq 0 ]]; then
  echo "ARTIFACT-STATUS: PASS — wheel/sdist 모두 저장소 밖에서 CLI/API/auth 실행 성공"
  exit $EXIT_PASS
fi
echo "ARTIFACT-STATUS: FAIL — 위 실패 단계를 해소해야 합니다" >&2
exit $EXIT_FAIL
