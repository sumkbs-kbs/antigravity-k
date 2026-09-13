"""CR-14 F-09 회귀 — 대시보드 **dev 도구 체인**의 취약 의존을 고정하고, 그것이 **출하되지 않음**을 지킨다.

발견(F-09, attempt-006 에서 등록 / attempt-007 에서 폐쇄)
======================================================
`dependency-audit-dashboard` 게이트는 ``pnpm audit --prod --audit-level high`` 다. 그래서 dev
도구 체인의 취약점은 **초록과 공존**한다. 실측(2026-09-13): high 1건과 moderate 3건이 있었다.

  · ``eslint → @eslint/eslintrc → js-yaml``  4.3.1  (GHSA-2883-xcg3-v3hh, `<4.3.2`)
  · ``@stryker-mutator/core → typed-rest-client → qs``  6.15.1  (GHSA-4mjr-xmp4-gh2g 외 2건, `<6.16.0`)

그런데 실측은 그보다 더 불편한 사실을 보여줬다 — **js-yaml 은 두 lock 이 갈라져 있었다**:
pnpm 은 4.3.1(취약), npm 은 4.3.2(패치). F-03(고지문↔SBOM)·F-06(uuid 두 lock)에서 두 번 걸린 병이
**세 번째**로 나타난 것이다. 해결: 상류 선언 범위 안(``@eslint/eslintrc`` 는 ``js-yaml: ^4.3.0``)에서
override 로 4.3.2 를 고정한다. qs 는 사정이 다르다 — ``typed-rest-client@2.3.1`` 이 ``qs: 6.15.1`` 로
**정확히 고정**하고 상류 수정은 ``typed-rest-client`` 3.x(``qs: ^6.16.0``)에만 있는데, stryker(core 9·10)
는 ``~2.3.0`` 만 허용한다. 즉 **선언 범위 안에 수정판이 없다** — 같은 벤더의 후속 메이저가 선언한
``6.16.0`` 으로 고정하고, 그 편차를 이 파일의 계약과 증거팩에 명시한다.

계약
====
  C14-F09-1 `pnpm-lock.yaml` 의 `js-yaml`·`qs` 해석이 패치 버전이다.
  C14-F09-2 `package-lock.json` 의 해석도 패치 버전이다.
  C14-F09-3 **두 lock 이 같은 버전**을 말한다(갈라짐이 이 결함의 절반이었다).
  C14-F09-4 override 선언이 **양쪽 설정에** 남아 있다 — 해석 결과만 보면 선언이 사라진 회귀를 놓친다.
  C14-F09-5 js-yaml override 는 **상류가 선언한 범위 안**에 있다(강제 downgrade/upgrade 아님).
  C14-F09-6 이 패키지들은 **출하 SBOM·고지문에 없다** — dev 전용이라는 주장을 측정으로 고정한다.
            (override 로 dev 도구를 밀어 올리는 결정이 출하물의 라이선스/구성 계약을 건드리지 않는다.)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT / "dashboard"
PNPM_LOCK = DASHBOARD / "pnpm-lock.yaml"
NPM_LOCK = DASHBOARD / "package-lock.json"
PNPM_OVERRIDES = DASHBOARD / "pnpm-workspace.yaml"
PACKAGE_JSON = DASHBOARD / "package.json"
RELEASE = REPO_ROOT / "src" / "antigravity_k" / "release"
DASHBOARD_SBOM = RELEASE / "dashboard.cdx.json"
NOTICES = RELEASE / "THIRD_PARTY_NOTICES.txt"

# 감사 advisory 의 patched_versions 에서 온 하한.
FLOORS: dict[str, tuple[int, int, int]] = {"js-yaml": (4, 3, 2), "qs": (6, 16, 0)}
# 출하물에 나타나면 안 되는 dev 도구 체인(경계 계약 C14-F09-6).
DEV_ONLY = ("js-yaml", "qs", "eslint", "typed-rest-client", "@stryker-mutator/core")


def _version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    assert match, f"버전을 읽을 수 없다: {text!r}"
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _pnpm_resolutions(package: str) -> list[str]:
    """pnpm-lock 의 `pkg@x.y.z:` 키와 `pkg: x.y.z` 의존 항목."""
    found: list[str] = []
    for line in PNPM_LOCK.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        key = re.match(rf"^'?{re.escape(package)}@([^':]+)'?:$", stripped)
        if key:
            found.append(key.group(1))
            continue
        dep = re.match(rf"^{re.escape(package)}:\s*([^\s]+)$", stripped)
        if dep:
            found.append(dep.group(1))
    return found


def _npm_lock() -> dict[str, Any]:
    return json.loads(NPM_LOCK.read_text(encoding="utf-8"))


def _npm_resolutions(package: str) -> list[str]:
    lock = _npm_lock()
    return [
        str(entry.get("version", ""))
        for name, entry in lock.get("packages", {}).items()
        if name.endswith(f"node_modules/{package}") and isinstance(entry, dict)
    ]


def _declared_override(package: str) -> str | None:
    """pnpm-workspace.yaml 의 override 선언(주석 줄은 무시)."""
    text = PNPM_OVERRIDES.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(package)}:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else None


# ── C14-F09-1/2: 두 lock 의 해석 하한 ──────────────────────────


def test_pnpm_lock_resolves_patched_dev_toolchain() -> None:
    for package, floor in FLOORS.items():
        resolutions = _pnpm_resolutions(package)
        assert resolutions, f"pnpm-lock 에서 {package} 해석을 찾지 못했다"
        for raw in resolutions:
            assert _version(raw) >= floor, (
                f"pnpm-lock 의 {package} 해석이 취약 범위다: {raw} < {'.'.join(map(str, floor))}"
            )


def test_npm_lock_resolves_patched_dev_toolchain() -> None:
    for package, floor in FLOORS.items():
        resolutions = _npm_resolutions(package)
        assert resolutions, f"package-lock 에서 {package} 해석을 찾지 못했다"
        for raw in resolutions:
            assert _version(raw) >= floor, (
                f"package-lock 의 {package} 해석이 취약 범위다: {raw} < {'.'.join(map(str, floor))}"
            )


# ── C14-F09-3: 두 lock 일치(이 결함의 절반은 갈라짐이었다) ───────


def test_both_locks_agree_on_dev_toolchain_versions() -> None:
    for package in FLOORS:
        pnpm_versions = {_version(raw) for raw in _pnpm_resolutions(package)}
        npm_versions = {_version(raw) for raw in _npm_resolutions(package)}
        assert pnpm_versions == npm_versions, (
            f"{package}: 두 lock 이 다른 버전을 말한다 — pnpm={sorted(pnpm_versions)} npm={sorted(npm_versions)}"
        )


# ── C14-F09-4: 선언(해석 결과가 아니라 규칙) ────────────────────


def test_overrides_declared_in_both_configs_for_dev_toolchain() -> None:
    npm_overrides = json.loads(PACKAGE_JSON.read_text(encoding="utf-8")).get("overrides", {})
    for package, floor in FLOORS.items():
        declared = _declared_override(package)
        assert declared is not None, (
            f"dashboard/pnpm-workspace.yaml 에 {package} override 가 없다 — 다음 install 이 되돌린다"
        )
        assert _version(declared) >= floor
        assert package in npm_overrides, (
            f"dashboard/package.json overrides 에 {package} 가 없다 — npm lock 이 다시 갈라진다"
        )
        assert _version(str(npm_overrides[package])) >= floor


# ── C14-F09-5: 상류가 선언한 범위 안인가 ───────────────────────


def test_js_yaml_override_stays_inside_eslintrc_declared_range() -> None:
    """`@eslint/eslintrc` 는 `js-yaml: ^4.3.0` 을 선언한다 — 4.3.2 는 그 범위의 최소 패치다."""
    lock = _npm_lock()
    eslintrc = lock.get("packages", {}).get("node_modules/@eslint/eslintrc", {})
    declared = str(eslintrc.get("dependencies", {}).get("js-yaml", ""))
    assert declared, "package-lock 에서 @eslint/eslintrc 의 js-yaml 선언 범위를 찾지 못했다"

    base = _version(declared)
    override = _version(str(json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["overrides"]["js-yaml"]))
    assert declared.startswith("^"), f"예상과 다른 선언 형식: {declared}"
    assert base <= override < (base[0] + 1, 0, 0), f"js-yaml {override} 이 상류 선언 범위({declared}) 밖이다"


def test_qs_override_documents_the_deviation() -> None:
    """qs 는 상류가 ``6.15.1`` 로 **정확히 고정**했다 — 이 override 는 의도된 편차다.

    편차를 코드만 보고는 알 수 없으므로, 선언 옆에 근거(어떤 패키지가 왜 못 올리는지)가 남아 있어야 한다.
    """
    text = PNPM_OVERRIDES.read_text(encoding="utf-8")
    block = text.split("qs:", 1)[-1].split("\n\n", 1)[0]
    context = text[: text.index("qs:")][-600:] + block
    assert _declared_override("qs") == "6.16.0", "qs override 선언이 없다"
    assert "F-09" in text and "typed-rest-client" in text, (
        "qs override 의 근거(정확 고정한 상류와 수정판이 있는 위치)가 선언 옆에 기록돼야 한다"
    )
    assert "6.16.0" in context and "stryker" in context


# ── C14-F09-6: dev 전용 경계(출하물에 없다) ────────────────────


def test_dev_toolchain_is_absent_from_shipped_release_documents() -> None:
    """override 로 dev 도구를 밀어 올리는 결정이 **출하물의 구성/고지 계약**을 건드리지 않는다."""
    if not DASHBOARD_SBOM.is_file():
        import pytest

        pytest.skip("릴리스 SBOM 이 없다 — 이 계약은 생성된 출하 문서가 있는 트리에서만 의미가 있다")

    payload = json.loads(DASHBOARD_SBOM.read_text(encoding="utf-8"))
    names = {str(component.get("name", "")) for component in payload.get("components", [])}
    leaked = sorted(name for name in DEV_ONLY if name in names)
    assert not leaked, f"출하 SBOM 에 dev 도구가 들어 있다: {leaked}"

    if NOTICES.is_file():
        notices = NOTICES.read_text(encoding="utf-8")
        for name in DEV_ONLY:
            assert f"\n{name} " not in notices and f"\n{name}(" not in notices, (
                f"출하 고지문에 dev 도구가 들어 있다: {name}"
            )
