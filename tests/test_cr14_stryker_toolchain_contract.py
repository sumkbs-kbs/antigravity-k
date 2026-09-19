"""CR-14 F-10 회귀 — 변이 테스트 도구 체인이 **실제로 실행 가능**하고, 그 실행이 F-09 의 `qs` 결정을
검증한다는 사실을 고정한다.

발견(F-10, attempt-007 에서 등록 / attempt-008 에서 폐쇄)
=========================================================
F-09 를 닫으면서 "출하 감사는 0건인데 dev 도구 체인에 high 1건·moderate 3건이 남아 있었다" 는 사실을
기록했고, 그 근거의 하나로 `pnpm run stryker:quick` 을 돌렸다. 그런데 그 명령이
``Cannot find TestRunner plugin "vitest"`` 로 죽었다.

진단(실측): Stryker 의 자동 플러그인 탐색은 **자기 자신의 설치 디렉터리**를 스캔한다 —
``.pnpm/@stryker-mutator+core@9.6.1_.../node_modules/@stryker-mutator`` 에는 core 의 의존
(api·instrumenter·util)만 있고 devDependency 인 ``vitest-runner`` 는 없다. pnpm 의 격리 레이아웃에서만
나타나는 모양이고, 프로젝트 루트에는 둘 다 있다. 수정은 러너를 **명시적으로 선언**하는 한 줄이다.

이 발견이 F-09 보다 더 값어치 있는 이유: **`qs` override 의 유일한 실행 소비자가 stryker 였다.**
도구가 죽어 있으면 그 편차는 감사 통과와 무관하게 end-to-end 로 검증되지 않는다 — 그래서 F-09 를 닫을 때
"그 편차는 검증되지 않았다" 고 정직하게 남겼고, 이번에 소비자 프로브로 그 구멍을 닫았다.

계약
====
  C14-F10-1 `stryker.config.mjs` 가 러너 플러그인을 **명시적으로** 선언한다(자동 탐색에 의존하지 않는다).
            선언이 없으면 도구가 죽고, 그래서 F-09 의 `qs` 결정이 검증 불가능해진다.
  C14-F10-2 선언한 플러그인이 **실재하는 devDependency** 다 — 오타 선언은 런타임에만 드러난다.
  C14-F10-3 두 lock 이 stryker 코어·러너에 대해 **같은 버전**을 말한다(npm lock 은 SBOM·고지의 진실원,
            pnpm lock 은 설치·빌드의 진실원 — F-03/F-06/F-09 에서 세 번 걸린 갈라짐의 재발 방지).
  C14-F10-4 설치 트리(node_modules 가 있을 때)에서 **러너가 대시보드 루트에서 해석되고**, 코어와 같은
            트리에 있다 — 선언이 실제로 로드되는지의 최소 관측.
  C14-F10-5 설치 트리에서 `typed-rest-client` 가 보는 `qs` 가 F-09 하한 이상이다 — "lock 은 X 인데
            설치된 코드는 Y" 를 막는다(F-06 C14-F06-6 과 같은 병).
  C14-F10-6 게이트가 읽는 설정과 스크립트가 그대로다 — `testRunner: 'vitest'` 이고 `stryker:quick` 이
            존재한다(러너를 바꿔 초록을 만드는 회귀를 막는다).
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
PACKAGE_JSON = DASHBOARD / "package.json"
STRYKER_CONFIG = DASHBOARD / "stryker.config.mjs"
NODE_MODULES = DASHBOARD / "node_modules"

# 러너 플러그인과 코어(둘이 함께 있어야 자동 탐색 없이도 로드된다).
RUNNER = "@stryker-mutator/vitest-runner"
CORE = "@stryker-mutator/core"
# F-09 하한 — typed-rest-client 가 실제로 보는 qs 가 이 아래면 override 가 설치까지 도달하지 않았다.
QS_FLOOR = (6, 16, 0)


def _version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    assert match, f"버전을 읽을 수 없다: {text!r}"
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _npm_lock() -> dict[str, Any]:
    return json.loads(NPM_LOCK.read_text(encoding="utf-8"))


def _package_json() -> dict[str, Any]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _npm_resolutions(package: str) -> list[str]:
    return [
        str(entry.get("version", ""))
        for name, entry in _npm_lock().get("packages", {}).items()
        if name.endswith(f"node_modules/{package}") and isinstance(entry, dict)
    ]


def _pnpm_resolutions(package: str) -> list[str]:
    """pnpm-lock 의 `pkg@x.y.z:` 키(peer 접미사는 잘라낸다)."""
    found: list[str] = []
    pattern = re.compile(rf"^'?{re.escape(package)}@([^':(]+)")
    for line in PNPM_LOCK.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.endswith(":"):
            continue
        match = pattern.match(stripped.rstrip(":"))
        if match:
            found.append(match.group(1))
    return found


# ── C14-F10-1/6: 설정 파일이 러너를 명시적으로 선언하는가 ───────


def test_stryker_config_declares_runner_plugin_explicitly() -> None:
    text = STRYKER_CONFIG.read_text(encoding="utf-8")
    assert RUNNER in text, (
        f"stryker.config.mjs 에 {RUNNER} 가 없다 — pnpm 격리 레이아웃에서 자동 탐색은 "
        "core 의 의존 디렉터리만 스캔하므로 러너를 찾지 못한다(도구가 죽는다)"
    )
    match = re.search(r"plugins:\s*\[([^\]]*)\]", text)
    assert match, "stryker.config.mjs 에 `plugins` 배열이 없다"
    declared = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    assert RUNNER in declared, f"plugins 배열에 러너가 없다: {declared}"


def test_stryker_config_pins_the_configured_runner() -> None:
    payload = _package_json()
    scripts = payload.get("scripts", {})
    assert "stryker:quick" in scripts, "stryker:quick 스크립트가 사라졌다 — 도구 신호를 잃는다"
    text = STRYKER_CONFIG.read_text(encoding="utf-8")
    assert re.search(r"testRunner:\s*['\"]vitest['\"]", text), (
        "testRunner 가 vitest 가 아니다 — 선언한 플러그인과 실제 러너가 갈라진다"
    )


# ── C14-F11: quick 스크립트가 선언한 범위를 실제로 덮는가 ───────
#
# 실측(attempt-008): `stryker run --mutate A --mutate B` 는 **마지막 하나만** 적용한다 —
# 도구가 2개 파일을 돌린다고 믿게 만들면서 실제로는 1개만 측정했다(변이 점수가 절반의 범위만 말한다).
# `--mutate` 의 강제 변환은 `createSplitter(',')` 이므로 **한 플래그에 쉼표로** 나열해야 둘 다 적용된다.


def test_stryker_quick_scope_is_declared_in_a_single_flag() -> None:
    script = str(_package_json().get("scripts", {}).get("stryker:quick", ""))
    assert script, "stryker:quick 스크립트를 찾지 못했다"
    mutate_flags = re.findall(r"--mutate|-m\b", script)
    assert len(mutate_flags) <= 1, (
        "`--mutate` 를 반복하면 마지막 하나만 적용된다 — 측정 범위가 조용히 줄어든다. 쉼표로 나열한 단일 플래그를 쓴다"
    )
    assert mutate_flags, "quick 스크립트가 mutate 범위를 지정하지 않는다"


def test_stryker_quick_scope_covers_both_store_files() -> None:
    script = str(_package_json().get("scripts", {}).get("stryker:quick", ""))
    scope = re.search(r"--mutate\s*'([^']+)'", script) or re.search(r'--mutate\s*"([^"]+)"', script)
    assert scope, f"quick 스크립트에서 mutate 범위를 읽지 못했다: {script!r}"
    files = [part.strip() for part in scope.group(1).split(",") if part.strip()]
    assert len(files) >= 2, f"quick scope 가 한 파일뿐이다: {files}"
    for name in ("terminalStore.ts", "outputStore.ts"):
        assert any(name in path for path in files), f"quick scope 에 {name} 이 없다: {files}"


# ── C14-F10-2: 선언이 실재하는 의존인가 ─────────────────────────


def test_runner_plugin_is_a_real_dev_dependency() -> None:
    dev = _package_json().get("devDependencies", {})
    assert RUNNER in dev, f"{RUNNER} 가 devDependencies 에 없다 — 선언만 있고 해석되지 않는다"
    assert CORE in dev, f"{CORE} 가 devDependencies 에 없다"


# ── C14-F10-3: 두 lock 이 도구 체인에 대해 일치하는가 ───────────


def test_both_locks_agree_on_stryker_toolchain_versions() -> None:
    for package in (CORE, RUNNER):
        pnpm_versions = {_version(raw) for raw in _pnpm_resolutions(package)}
        npm_versions = {_version(raw) for raw in _npm_resolutions(package)}
        assert pnpm_versions, f"pnpm-lock 에서 {package} 해석을 찾지 못했다"
        assert npm_versions, f"package-lock 에서 {package} 해석을 찾지 못했다"
        assert pnpm_versions == npm_versions, (
            f"{package}: 두 lock 이 다른 버전을 말한다 — pnpm={sorted(pnpm_versions)} npm={sorted(npm_versions)}"
        )


def test_runner_and_core_share_a_major_version() -> None:
    runner = _version(_npm_resolutions(RUNNER)[0])
    core = _version(_npm_resolutions(CORE)[0])
    assert runner[0] == core[0], (
        f"러너({runner})와 코어({core})의 메이저가 다르다 — 러너의 peer 는 코어를 정확히 고정한다"
    )


# ── C14-F10-4/5: 설치 트리 관측(없으면 skip) ───────────────────


def test_installed_tree_links_runner_and_core_at_dashboard_root() -> None:
    """pnpm 은 직접 의존을 루트 node_modules 에 심볼릭 링크한다 — 설정에서 해석되는 경로다."""
    if not NODE_MODULES.is_dir():
        pytest.skip("node_modules 가 없다 — 이 계약은 설치된 트리에서만 의미가 있다")

    for package in (CORE, RUNNER):
        linked = NODE_MODULES / package / "package.json"
        assert linked.is_file(), f"대시보드 루트에서 {package} 를 해석할 수 없다 — 플러그인 로딩이 실패한다"


def test_installed_typed_rest_client_sees_patched_qs() -> None:
    """ "lock 은 패치인데 설치된 코드는 취약" 을 막는다(F-06 의 출하 바이트 계약과 같은 병)."""
    if not NODE_MODULES.is_dir():
        pytest.skip("node_modules 가 없다 — 이 계약은 설치된 트리에서만 의미가 있다")

    consumers = sorted((NODE_MODULES / ".pnpm").glob("typed-rest-client@*/node_modules/qs/package.json"))
    if not consumers:
        pytest.skip("typed-rest-client 의 qs 사본이 없다 — F-09 소비자 경로가 설치되지 않았다")

    for path in consumers:
        version = _version(json.loads(path.read_text(encoding="utf-8"))["version"])
        assert version >= QS_FLOOR, (
            f"설치된 트리에서 typed-rest-client 가 보는 qs 가 취약 범위다: {version} < "
            f"{'.'.join(map(str, QS_FLOOR))} — override 가 설치까지 도달하지 않았다"
        )
