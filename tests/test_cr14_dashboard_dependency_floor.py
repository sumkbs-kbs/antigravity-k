"""CR-14 F-06 회귀 — 대시보드 `uuid` 해석이 취약 범위로 되돌아가지 못하게 고정한다.

발견(F-06)
==========
`mermaid` 는 `uuid` 를 ``^9.0.0 || ^10 || ^11.1.0 || ^12 || ^13 || ^14.0.0`` 로 선언하는데,
두 lock 모두 **가장 낮은 가지(9.0.1)** 로 해석돼 있었다. 9.0.1 은
GHSA-w5hq-g745-h8pq(`v3/v5/v6` 에 `buf` 를 넘길 때 경계 검사가 없다, `<11.1.1`)의 영향권이고,
`dependency-audit-dashboard` 는 `--prod --audit-level high` 이므로 **moderate 인 이 결함을
차단하지 않는다** — 즉 "게이트 초록"과 "위험 0" 이 갈라져 있었다.

실측: mermaid 10.9.8 의 erDiagram 청크는 `import { v5 } from "uuid"` 후
``v5(str, MERMAID_ERDIAGRAM_UUID)`` — 인자 2개, 즉 **취약 서명(`buf` 전달)에 도달하지 않는다**.
그래서 이 결함은 악용 경로가 아니라 **의존 하한** 문제였다. 그렇다고 남겨 둘 이유는 없다:
잠금 하한은 미래의 호출 경로에도 그대로 적용되고, 선언 범위 안에 패치 버전이 존재한다.

계약
====
  C14-F06-1 `pnpm-lock.yaml`(설치·빌드 진실원)의 `uuid` 해석이 패치 버전이다.
  C14-F06-2 `package-lock.json`(SBOM·고지 진실원)의 해석도 패치 버전이고, **두 lock 이 같은 버전**을
            가리킨다. 한쪽만 올리면 "설치된 코드"와 "고지된 코드"가 갈라진다(F-03 과 같은 병).
  C14-F06-3 override 선언이 **양쪽 설정에 남아 있다** — 없으면 다음 `pnpm install`/`npm install` 이
            조용히 취약 버전으로 되돌린다(해석 결과만 검사하면 그 회귀를 놓친다).
  C14-F06-4 고정한 버전이 mermaid 의 **선언 범위 안**에 있다(상류가 허용한 버전이라 강제 downgrade 가 아니다).
  C14-F06-5 감사 gate 의 임계값은 `--prod --audit-level high` 그대로다 — 임계값을 낮춰 초록을 만드는
            변경은 이 결함을 "고친" 것이 아니라 "가린" 것이다.
  C14-F06-6 출하 번들(`src/antigravity_k/dashboard_dist/assets/**`)이 uuid v35 구현을 담고 있으면
            **패치 마커도 함께 담고 있다** — 잠금만 올리고 재빌드하지 않으면 출하물에는 옛 코드가 남는다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT / "dashboard"
PNPM_LOCK = DASHBOARD / "pnpm-lock.yaml"
NPM_LOCK = DASHBOARD / "package-lock.json"
PNPM_OVERRIDES = DASHBOARD / "pnpm-workspace.yaml"
PACKAGE_JSON = DASHBOARD / "package.json"
GATE_SPEC = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
SHIPPED_ASSETS = REPO_ROOT / "src" / "antigravity_k" / "dashboard_dist" / "assets"

PATCHED_FLOOR = (11, 1, 1)  # GHSA-w5hq-g745-h8pq patched_versions: >=11.1.1
PATCHED_FLOOR_TEXT = ".".join(str(part) for part in PATCHED_FLOOR)

# 번들·구현 판별자(F-06 증인과 같은 마커를 쓴다).
V35_PRESENT = "Namespace must be array-like"  # uuid 9·11 모두
V35_PATCHED = "out of buffer bounds"  # uuid 11.1.1 에서 추가된 경계 검사


def _version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    assert match, f"버전을 읽을 수 없다: {text!r}"
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _pnpm_uuid_resolutions() -> list[str]:
    """pnpm-lock 에서 uuid 로 해석된 버전들(패키지 키 + 의존 항목)."""
    found: list[str] = []
    for line in PNPM_LOCK.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        key = re.match(r"^'?uuid@([^':]+)'?:$", stripped)
        if key:
            found.append(key.group(1))
            continue
        dep = re.match(r"^uuid:\s*([^\s]+)$", stripped)
        if dep:
            found.append(dep.group(1))
    return found


def _npm_lock() -> dict[str, Any]:
    return json.loads(NPM_LOCK.read_text(encoding="utf-8"))


def _npm_uuid_resolutions() -> list[str]:
    """package-lock 에서 uuid 로 해석된 버전들(packages 항목 + 중첩 dependencies)."""
    found: list[str] = []
    lock = _npm_lock()
    for name, entry in lock.get("packages", {}).items():
        if name.endswith("node_modules/uuid") and isinstance(entry, dict):
            found.append(str(entry.get("version", "")))
    for name, entry in lock.get("dependencies", {}).items():
        if name == "uuid" and isinstance(entry, dict):
            found.append(str(entry.get("version", "")))
    return found


# ── C14-F06-1/2: 두 lock 의 해석 하한 ───────────────────────────


def test_pnpm_lock_resolves_patched_uuid() -> None:
    resolutions = _pnpm_uuid_resolutions()
    assert resolutions, "pnpm-lock.yaml 에서 uuid 해석을 찾지 못했다"
    for raw in resolutions:
        assert _version(raw) >= PATCHED_FLOOR, f"pnpm-lock 의 uuid 해석이 취약 범위다: {raw} < {PATCHED_FLOOR_TEXT}"


def test_npm_lock_resolves_patched_uuid() -> None:
    resolutions = _npm_uuid_resolutions()
    assert resolutions, "package-lock.json 에서 uuid 해석을 찾지 못했다"
    for raw in resolutions:
        assert _version(raw) >= PATCHED_FLOOR, f"package-lock 의 uuid 해석이 취약 범위다: {raw} < {PATCHED_FLOOR_TEXT}"


def test_both_locks_agree_on_the_same_uuid_version() -> None:
    """SBOM·고지는 npm lock 을 읽고 설치·빌드는 pnpm lock 을 쓴다 — 답이 하나여야 한다."""
    pnpm_versions = {_version(raw) for raw in _pnpm_uuid_resolutions()}
    npm_versions = {_version(raw) for raw in _npm_uuid_resolutions()}
    assert pnpm_versions == npm_versions, (
        f"두 lock 이 다른 uuid 를 가리킨다 — pnpm={sorted(pnpm_versions)} npm={sorted(npm_versions)}"
    )


# ── C14-F06-3: override 선언(해석 결과만이 아니라 규칙을 고정) ────


def test_pnpm_override_declares_uuid_floor() -> None:
    text = PNPM_OVERRIDES.read_text(encoding="utf-8")
    match = re.search(r"^\s*uuid:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    assert match, "dashboard/pnpm-workspace.yaml 에 uuid override 가 없다 — 다음 install 이 되돌린다"
    assert _version(match.group(1)) >= PATCHED_FLOOR


def test_npm_override_declares_uuid_floor() -> None:
    payload = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    overrides = payload.get("overrides", {})
    assert "uuid" in overrides, (
        "dashboard/package.json 에 npm override 가 없다 — package-lock 재생성 시 14.x 로 갈라진다"
    )
    assert _version(str(overrides["uuid"])) >= PATCHED_FLOOR


# ── C14-F06-4: 상류가 허용한 범위 안인가 ────────────────────────


def _loose_version(text: str) -> tuple[int, int, int]:
    """`^10` 처럼 생략된 자리를 0 으로 채운다(전체 semver 파서가 필요해서가 아니라 범위 비교용)."""
    numbers = [int(part) for part in re.findall(r"\d+", text)][:3]
    assert numbers, f"버전을 읽을 수 없다: {text!r}"
    padded = numbers + [0, 0, 0]
    return (padded[0], padded[1], padded[2])


def _satisfies_caret(version: tuple[int, int, int], caret: str) -> bool:
    """`^X.Y.Z` = [X.Y.Z, X+1.0.0). 이 결함에서 필요한 만큼만 구현한다."""
    base = _loose_version(caret)
    return base <= version < (base[0] + 1, 0, 0)


def test_override_stays_inside_mermaid_declared_range() -> None:
    """선언 범위 안의 최소 패치를 고른다 — 상류가 허용하지 않는 강제 downgrade/upgrade 가 아니다."""
    lock = _npm_lock()
    mermaid = lock.get("packages", {}).get("node_modules/mermaid", {})
    declared = str(mermaid.get("dependencies", {}).get("uuid", ""))
    assert declared, "package-lock 에서 mermaid 의 uuid 선언 범위를 찾지 못했다"

    pinned = _version(str(json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["overrides"]["uuid"]))
    branches = [branch.strip() for branch in declared.split("||")]
    assert any(_satisfies_caret(pinned, branch) for branch in branches if branch.startswith("^")), (
        f"고정한 uuid {pinned} 이 mermaid 의 선언 범위({declared}) 밖이다"
    )
    caret11 = [branch for branch in branches if branch.startswith("^11")]
    assert caret11, f"mermaid 가 ^11.x 를 허용하지 않는다: {declared}"
    assert pinned == PATCHED_FLOOR, f"최소 패치({PATCHED_FLOOR_TEXT})가 아니라 {pinned} 를 고정했다 — 이유를 기록할 것"


# ── C14-F06-5: 게이트 임계값을 낮춰 초록을 만들지 않았는가 ───────


def test_dashboard_audit_gate_threshold_is_unchanged() -> None:
    spec = json.loads(GATE_SPEC.read_text(encoding="utf-8"))
    gates = spec["gates"] if isinstance(spec, dict) and "gates" in spec else spec
    entry = next((gate for gate in gates if gate.get("id") == "dependency-audit-dashboard"), None)
    assert entry is not None, "dependency-audit-dashboard gate 정의를 찾지 못했다"
    assert entry["command"][-2:] == ["--audit-level", "high"], (
        "감사 임계값이 바뀌었다 — F-06 을 고친 것이 아니라 숨긴 것일 수 있다"
    )
    assert "--prod" in entry["command"]


# ── C14-F06-6: 출하 번들이 패치 코드를 담았는가 ─────────────────


def test_shipped_bundle_carries_patched_uuid() -> None:
    """잠금만 올리고 재빌드하지 않으면 출하물에는 옛 uuid 가 남는다(F-03 과 같은 병)."""
    if not SHIPPED_ASSETS.is_dir():
        pytest.skip("빌드 산출물 디렉터리가 없다 — 이 계약은 번들이 있는 트리에서만 의미가 있다")

    carriers: list[Path] = []
    for path in sorted(SHIPPED_ASSETS.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if V35_PRESENT in text:
            carriers.append(path)

    if not carriers:
        # mermaid 의 erDiagram 청크가 lazy 라 번들에 없을 수 있다 — 그때는 검사할 대상이 없다.
        pytest.skip("출하 번들에 uuid v35 구현이 없다(해당 청크 미포함)")

    unpached = [path.name for path in carriers if V35_PATCHED not in path.read_text(encoding="utf-8")]
    assert not unpached, "출하 번들이 uuid v35 를 담았지만 패치 경계 검사가 없다 — 재빌드가 필요하다: " + ", ".join(
        unpached
    )
