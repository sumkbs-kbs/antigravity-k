#!/usr/bin/env bash
# ============================================================================
# Python 의존성 감사 (CR-11 / REL-03)
# ============================================================================
# 왜 다시 썼나
# ------------
# 이전 버전은 `uv export --no-dev` 한 번으로 감사 입력을 만들었다. 그 입력에는
# **base 의존성만** 들어가는데, 제품 컨테이너는 `pip install ".[rag]"`로 출하한다
# (Dockerfile). 즉 실제로 배포되는 `[rag]` 의존성(예: chromadb·sentence-transformers)은
# 한 번도 감사되지 않았다.
#
# 게다가 pip-audit는 "취약점 발견"과 "감사 인프라 실패"를 같은 종료코드로 보고한다.
# 게이트는 둘 다 비성공으로 다뤄야 하지만 **이유는 구분**되어야 한다.
#
# 계약
# ----
#   대상: base + **출하 extras**(기본값은 Dockerfile에서 파싱, `--extras`로 덮어쓰기)
#   입력 기록: 각 대상의 패키지 수와 합집합 핑거프린트를 항상 출력한다(감사 전에).
#   음성 입력 거부: pyproject에 없는 extra 이름은 실행을 거부한다(exit 2).
#   예외: REL-03 레지스트리(config/audit-exceptions.json)를 엔진과 같은 규칙으로 적용한다
#         — high/critical 만 대상, (id, package, ecosystem, version) 정확 일치, 만료 시 실패.
#   종료코드: 0 = 통과, 1 = 취약점 발견/만료된 예외, 2 = 사용법/인프라 오류(감사 미완료)
#
# 사용법
# -----
#   scripts/audit_python_dependencies.sh                 # 출하 extras 자동 감지
#   scripts/audit_python_dependencies.sh --extras rag,mlx
#   scripts/audit_python_dependencies.sh --print-targets # 대상만 확인(감사 생략)
#   scripts/audit_python_dependencies.sh --requirement-file deps.txt  # export 생략
#   scripts/audit_python_dependencies.sh --exceptions config/audit-exceptions.json
#
# 환경변수
#   AGK_AUDIT_RECORD   입력 기록 JSON을 남길 경로(기본: 없음)
#                      (과거 이름 AUDIT_RECORD도 계속 받는다)
#   AGK_AUDIT_EXCEPTIONS  REL-03 예외 레지스트리 경로(기본: config/audit-exceptions.json)
#   AGK_PIP_AUDIT_CMD  감사 명령(기본: uvx --from pip-audit==2.10.1 pip-audit)
#                      테스트가 스텁을 주입할 수 있게 열어 둔다.
# ============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXIT_PASS=0
EXIT_VULNS=1
EXIT_INFRA=2

EXTRAS_OVERRIDE=""
PRINT_TARGETS=0
REQUIREMENT_FILE=""
EXCEPTIONS_OVERRIDE=""

# 기록 경로는 접두사 있는 이름을 우선하고, 과거 이름도 받아 준다.
# (문서는 AGK_AUDIT_RECORD를 안내했지만 코드는 AUDIT_RECORD를 읽어
#  설정해도 파일이 남지 않던 불일치를 수정했다 — CR-11 테스트가 이걸 잡았다.)
AUDIT_RECORD_PATH="${AGK_AUDIT_RECORD:-${AUDIT_RECORD:-}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --extras)
      EXTRAS_OVERRIDE="${2:?--extras 에는 쉼표로 구분한 extra 목록이 필요합니다}"
      shift 2
      ;;
    --requirement-file)
      REQUIREMENT_FILE="${2:?--requirement-file 에는 경로가 필요합니다}"
      shift 2
      ;;
    --exceptions)
      EXCEPTIONS_OVERRIDE="${2:?--exceptions 에는 경로가 필요합니다}"
      shift 2
      ;;
    --print-targets)
      PRINT_TARGETS=1
      shift
      ;;
    -h|--help)
      sed -n '2,32p' "$0"
      exit $EXIT_PASS
      ;;
    *)
      echo "알 수 없는 옵션: $1 (--help 참고)" >&2
      exit $EXIT_INFRA
      ;;
  esac
done

infra_error() {
  echo "AUDIT-STATUS: INFRA_ERROR — $*" >&2
  exit $EXIT_INFRA
}

# ─── 1. 감사 대상(출하 extras) 결정 ────────────────────────────────────────
# 단일 진실원은 "우리가 실제로 출하하는 것"이다 → Dockerfile의 `".[extras]"`.
discover_shipped_extras() {
  python3 - "$REPO_ROOT/Dockerfile" <<'PY'
import re
import sys
from pathlib import Path

dockerfile = Path(sys.argv[1])
if not dockerfile.exists():
    print("", end="")
    raise SystemExit(0)
text = re.sub(r"\\\s*\n\s*", " ", dockerfile.read_text(encoding="utf-8"))
extras: set[str] = set()
for match in re.findall(r'"\.\[([^\]]+)\]"', text):
    extras.update(part.strip() for part in match.split(",") if part.strip())
print(",".join(sorted(extras)))
PY
}

if [[ -n "$EXTRAS_OVERRIDE" ]]; then
  SHIPPED_EXTRAS="$EXTRAS_OVERRIDE"
else
  SHIPPED_EXTRAS="$(discover_shipped_extras)" || infra_error "Dockerfile에서 출하 extras를 읽지 못했습니다"
fi

if [[ -z "$SHIPPED_EXTRAS" ]]; then
  infra_error "출하 extras를 결정하지 못했습니다 (Dockerfile에 '.[extras]' 설치가 없고 --extras도 없음)"
fi

IFS=',' read -r -a EXTRA_LIST <<<"$SHIPPED_EXTRAS"

# 선언되지 않은 extra 이름은 조용히 무시하지 않고 거부한다(음성 입력 거부).
declare -a AUDIT_TARGETS=()
for extra in "${EXTRA_LIST[@]}"; do
  [[ -n "$extra" ]] || continue
  # tomllib(3.11+)에 기대지 않는다 — 감사 스크립트는 어떤 인터프리터로도 돈다.
  if ! python3 - "$REPO_ROOT/pyproject.toml" "$extra" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
extra = sys.argv[2]
match = re.search(r"^\[project\.optional-dependencies\]\s*$", text, re.M)
if not match:
    raise SystemExit(1)
rest = text[match.end():]
next_section = re.search(r"^\[", rest, re.M)
section = rest[: next_section.start()] if next_section else rest
names = set(re.findall(r"^([A-Za-z0-9_.-]+)\s*=", section, re.M))
raise SystemExit(0 if extra in names else 1)
PY
  then
    infra_error "pyproject.toml에 없는 extra를 감사 대상으로 요청했습니다: '${extra}'"
  fi
  AUDIT_TARGETS+=("$extra")
done

# ─── 2. 입력 기록 — 무엇을 감사하는지 먼저 남긴다 ──────────────────────────
record_dir="$(mktemp -d "${TMPDIR:-/tmp}/agk-audit.XXXXXX")"
trap 'rm -rf "$record_dir"' EXIT

# 이미 만들어진 잠금 입력을 주면 export를 건너뛴다(CI 재사용·테스트).
if [[ -n "$REQUIREMENT_FILE" ]]; then
  [[ -f "$REQUIREMENT_FILE" ]] || infra_error "--requirement-file 경로가 없습니다: $REQUIREMENT_FILE"
  UNION_FILE_OVERRIDE="$(cd "$(dirname "$REQUIREMENT_FILE")" && pwd)/$(basename "$REQUIREMENT_FILE")"
fi

export_one() {  # $1 = label, 나머지 = 추가 인자
  local label="$1"; shift
  local out="$record_dir/${label}.txt"
  if ! uv export \
    --directory "$REPO_ROOT" \
    --quiet \
    --frozen \
    --no-dev \
    --no-editable \
    --no-emit-project \
    "$@" \
    --format requirements-txt \
    --output-file "$out" >/dev/null; then
    return 1
  fi
  printf '%s' "$out"
}

# 감사·기록에 쓰는 입력 목록(라벨=경로). base는 항상, 출하 extra 각각은 별도 입력이다.
#
# 왜 합집합 파일을 다시 만들지 않는가: 예전 구현은 `cat` 후 `sort -u`로 한 파일을
# 만들었는데, uv export의 requirements는 줄바꿈 연속(`\`)으로 `--hash=...`가
# 이어져 있어 정렬이 항목과 해시를 갈라놓는다. 그러면 pip-audit가 받는 파일이
# 손상된다. pip-audit `--requirement`는 여러 번 쓸 수 있으므로 입력을 그대로 넘긴다.
declare -a LABELED_INPUTS=()

if [[ -n "${UNION_FILE_OVERRIDE:-}" ]]; then
  LABELED_INPUTS+=("union=${UNION_FILE_OVERRIDE}")
  echo "AUDIT-NOTE: --requirement-file 사용 — export와 입력 대조를 건너뜁니다" >&2
else
  base_file="$(export_one base)" || infra_error "base 의존성 export 실패 (uv.lock/pyproject 확인)"
  LABELED_INPUTS+=("base=${base_file}")

  for extra in "${AUDIT_TARGETS[@]}"; do
    extra_file="$(export_one "extra-${extra}" --extra "$extra")" \
      || infra_error "extra '${extra}' export 실패"
    LABELED_INPUTS+=("extra-${extra}=${extra_file}")
  done
fi

python3 - \
  "$SHIPPED_EXTRAS" \
  "$AUDIT_RECORD_PATH" \
  "${LABELED_INPUTS[@]}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

shipped = sys.argv[1]
record_path = sys.argv[2]
entries: list[tuple[str, Path]] = []
for raw in sys.argv[3:]:
    label, _, path = raw.partition("=")
    entries.append((label, Path(path)))


def lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def digest(path: Path) -> str:
    """감사 입력의 지문.

    `uv export`는 출력 파일 경로를 헤더 주석에 적어 넣기 때문에 **바이트 그대로**
    해시하면 같은 입력도 실행할 때마다 다른 지문이 나온다(실측으로 확인).
    주석 줄을 제외한 정규화된 내용을 해시해 재실행에도 안정적인 지문을 만든다.
    """
    payload = "\n".join(lines(path))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def requirements(path: Path) -> set[str]:
    """`name==version` 항목만 뽑는다(해시/연속 줄 제외)."""
    found: set[str] = set()
    for line in lines(path):
        entry = line.split(" ", 1)[0].rstrip("\\").strip()
        if "==" in entry:
            found.add(entry)
    return found

targets: dict[str, dict[str, object]] = {}
union: set[str] = set()
for label, path in entries:
    # packages는 `name==version` 항목 수다 — 파일 라인 수(해시 연속 줄 포함)를
    # 세면 대상 간 비교가 무의미해진다.
    counted = {"packages": len(requirements(path)), "sha256_16": digest(path)}
    if label.startswith("extra-"):
        targets.setdefault("extras", {})[label[len("extra-") :]] = counted
    else:
        targets[label] = counted
    union |= requirements(path)

union_payload = "\n".join(sorted(union))
targets["union"] = {
    "packages": len(union),
    "sha256_16": hashlib.sha256(union_payload.encode("utf-8")).hexdigest()[:16],
}

record = {
    "schema": "agk-python-audit-inputs/1",
    "shipped_extras": [e for e in shipped.split(",") if e],
    "audit_record_file": "uv.lock",
    "targets": targets,
}
if len(entries) == 1 and entries[0][0] == "union":
    record["source"] = "--requirement-file"

print("AUDIT-INPUTS: " + json.dumps(record, ensure_ascii=False, separators=(",", ":")))
if record_path:
    Path(record_path).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
PY

if [[ $PRINT_TARGETS -eq 1 ]]; then
  echo "AUDIT-STATUS: TARGETS_ONLY — 감사를 실행하지 않았습니다 (--print-targets)"
  exit $EXIT_PASS
fi

EXCEPTIONS_FILE="${EXCEPTIONS_OVERRIDE:-${AGK_AUDIT_EXCEPTIONS:-config/audit-exceptions.json}}"
[[ "$EXCEPTIONS_FILE" = /* ]] || EXCEPTIONS_FILE="$REPO_ROOT/$EXCEPTIONS_FILE"
if [[ ! -f "$EXCEPTIONS_FILE" ]]; then
  # 예외를 평가할 수 없으므로 취약점이 하나라도 나오면 INFRA_ERROR로 닫는다(fail-closed).
  echo "AUDIT-NOTE: 예외 레지스트리를 찾지 못했습니다 — 취약점이 있으면 실패로 닫습니다: $EXCEPTIONS_FILE" >&2
fi

# ─── 3. 감사 실행 — 취약점과 인프라 오류를 구분한다 ────────────────────────
read -r -a AUDIT_CMD <<<"${AGK_PIP_AUDIT_CMD:-uvx --from pip-audit==2.10.1 pip-audit}"

audit_json="$record_dir/audit.json"
audit_stderr="$record_dir/audit.stderr"

# 입력 파일을 그대로 넘긴다(pip-audit `--requirement`는 반복 가능).
AUDIT_REQUIREMENT_ARGS=()
for entry in "${LABELED_INPUTS[@]}"; do
  AUDIT_REQUIREMENT_ARGS+=(--requirement "${entry#*=}")
done

if ! "${AUDIT_CMD[@]}" \
  --strict \
  --desc \
  --disable-pip \
  "${AUDIT_REQUIREMENT_ARGS[@]}" \
  --format json \
  >"$audit_json" 2>"$audit_stderr"; then
  # pip-audit는 취약점 발견과 실행 실패를 모두 비영(非零)으로 보고한다.
  # 그래서 판정은 종료코드가 아니라 **출력이 해석 가능한가**로 한다.
  if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$audit_json" 2>/dev/null; then
    echo "--- 감사 명령 stderr ---" >&2
    sed -n '1,40p' "$audit_stderr" >&2 || true
    infra_error "감사 명령이 해석 가능한 출력을 내지 못했습니다(인프라 오류). 명령: ${AUDIT_CMD[*]}"
  fi
fi

# 판정: 취약점과 인프라 오류를 구분하고, REL-03 예외 레지스트리를 **같은 의미**로 적용한다.
#
# 왜 레지스트리를 여기서도 보는가: 출하 extras를 감사하기 시작하자 chromadb(=[rag] 의존)의
# 권고가 실제로 나왔다. 같은 입력에 대해 'raw gate는 실패, supply_chain_audit는 예외 적용'으로
# 갈라지면 게이트 간 진실이 둘로 쪼개진다. 그래서 엔진과 **동일한 판정 규칙**을 적용한다:
#   - high/critical 만 gate 실패 대상
#   - (id, package, ecosystem, installed_version) 정확히 일치할 때만 예외 유효
#   - 만료된 예외는 gate 실패 (deny-by-default)
# 규칙이 엔진과 어긋나지 않는지는 tests/test_cr11_release_bootstrap.py 가 대조한다.
python3 - "$audit_json" "$EXCEPTIONS_FILE" <<'PY'
import json
import sys
from datetime import date, datetime, timezone  # timezone: 3.9 호환(UTC 상수는 3.11+)
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
exceptions_path = Path(sys.argv[2])
dependencies = report.get("dependencies", [])


def severity_of(vuln_id: str) -> str:
    """pip-audit이 severity를 주지 않을 때의 보수적 기본값(엔진과 동일)."""
    return "high" if vuln_id.startswith(("GHSA-", "PYSEC-", "CVE-")) else "unknown"


findings: list[dict[str, object]] = []
for dep in dependencies:
    for vuln in dep.get("vulns", []):
        vuln_id = str(vuln.get("id", ""))
        findings.append(
            {
                "id": vuln_id,
                "package": str(dep.get("name", "")),
                "ecosystem": "pypi",
                "installed_version": str(dep.get("version", "")),
                "severity": str(vuln.get("severity") or severity_of(vuln_id)),
            }
        )

print(
    f"AUDIT-SUMMARY: audited={len(dependencies)}"
    f" vulnerable_packages={sum(1 for dep in dependencies if dep.get('vulns'))}"
    f" findings={len(findings)}"
)
for finding in findings:
    print(
        f"  {finding['package']}=={finding['installed_version']}  {finding['id']}"
        f"  (severity: {finding['severity']})"
    )

if not findings:
    print("AUDIT-STATUS: PASS — 취약점 없음")
    raise SystemExit(0)

if not exceptions_path.is_file():
    print(f"AUDIT-STATUS: INFRA_ERROR — 예외 레지스트리가 없다: {exceptions_path}", file=sys.stderr)
    raise SystemExit(2)

try:
    registry = json.loads(exceptions_path.read_text(encoding="utf-8"))
    entries = registry["exceptions"]
except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
    print(f"AUDIT-STATUS: INFRA_ERROR — 레지스트리를 읽을 수 없다: {error}", file=sys.stderr)
    raise SystemExit(2)

required = {"id", "package", "ecosystem", "installed_version", "owner", "justification", "expires", "compensating_controls"}
for entry in entries:
    if not isinstance(entry, dict) or not required <= set(entry):
        print(f"AUDIT-STATUS: INFRA_ERROR — 예외 항목이 4요소 계약을 위반한다: {entry}", file=sys.stderr)
        raise SystemExit(2)

today = datetime.now(timezone.utc).date()
expired = [str(entry["id"]) for entry in entries if date.fromisoformat(str(entry["expires"])) < today]
by_key = {
    (str(e["id"]), str(e["package"]), str(e["ecosystem"]), str(e["installed_version"])): e
    for e in entries
}

unresolved: list[str] = []
excepted: list[dict[str, str]] = []
for finding in findings:
    if str(finding["severity"]).lower() not in {"high", "critical"}:
        continue  # medium/low는 보고 전용(숨기지 않고 출력한다)
    key = (
        str(finding["id"]),
        str(finding["package"]),
        "pypi",
        str(finding["installed_version"]),
    )
    entry = by_key.get(key)
    if entry is None or date.fromisoformat(str(entry["expires"])) < today:
        unresolved.append(f"{finding['package']}=={finding['installed_version']} {finding['id']}")
    else:
        excepted.append(
            {
                "id": str(entry["id"]),
                "package": str(entry["package"]),
                "owner": str(entry["owner"]),
                "expires": str(entry["expires"]),
            }
        )

print("AUDIT-VERDICT: " + json.dumps(
    {"excepted": excepted, "unresolved": unresolved, "expired": expired},
    ensure_ascii=False,
    separators=(",", ":"),
))

if expired:
    print("AUDIT-STATUS: EXPIRED_EXCEPTION — 만료된 예외가 있다: " + ", ".join(expired), file=sys.stderr)
    raise SystemExit(1)
if unresolved:
    print("AUDIT-STATUS: VULNERABILITIES_FOUND — 미해결 high/critical 이 있습니다", file=sys.stderr)
    for item in unresolved:
        print(f"  {item}", file=sys.stderr)
    raise SystemExit(1)
print(f"AUDIT-STATUS: PASS — high/critical 미해결 0건 (예외 적용 {len(excepted)}건, 위 목록에 근거·만료일 기록)")
raise SystemExit(0)
PY
audit_rc=$?

if [[ $audit_rc -eq 0 ]]; then
  exit $EXIT_PASS
fi
if [[ $audit_rc -eq 2 ]]; then
  exit $EXIT_INFRA
fi
exit $EXIT_VULNS
