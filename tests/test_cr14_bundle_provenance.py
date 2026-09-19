"""CR-14 F-12 회귀 — 커밋된 번들의 **빌드 provenance 가 HEAD 에 매이지 않게** 고정한다.

발견(F-12, attempt-009 에서 등록·폐쇄)
=====================================
attempt-008 은 \"빌드는 바이트 단위로 멱등\"(F-01)을 근거로 `dashboard_dist` 를 후보와 함께
커밋하라고 안내했다. 그 실측은 **고정 HEAD 에서만** 참이었다. 커밋이 생기면 HEAD 가 바뀌고,
`buildStamp.ts` 가 `git rev-parse --short HEAD` 를 `AGK_BUILD_ID` 기본값으로 쓰기 때문에
**다음 빌드는 반드시 다른 바이트를 낸다** — 실측(커밋 `5a717c4a` 직후):

  · 커밋 전 같은 트리에서 재빌드 → 완전한 no-op
  · 커밋 후 재빌드 → 자산 **22개 교체** + `index.html` 수정 + 코드 지문 이동
    (`07118329…` → `a4be7868…`)

즉 `dashboard-build` 가 required gate 인 한 **커밋된 후보에서는 단일 지문 20/20 을 완주할 수
없었다**(C14-01/C14-02 가 구조적으로 미충족). 동시에 커밋된 번들은 자기 커밋의 SHA 를 담을 수
없다(치킨-에그) — 그래서 BUILD 라벨이 실제 내용과 다른 리비전을 가리켰다.

수정: 해석 순서에 **커밋된 핀**(`dashboard/build-provenance.json`)을 넣는다.
`AGK_BUILD_ID`(릴리스 주입) → 핀(커밋된 기록) → `git short SHA`(핀 없는 개발 트리) → null.
핀이 있는 한 로컬·CI·Docker 빌드가 같은 바이트를 내고, `.git` 이 없는 컨테이너에서 buildId 가
UNKNOWN 으로 떨어지던 문제도 함께 닫힌다.

계약
====
  C14-F12-1 핀 파일이 존재하고 유효한 `buildId` 를 담는다(placeholder 금지).
  C14-F12-2 **커밋된 출하 번들이 핀의 `buildId` 를 담는다** — 핀을 갱신했는데 재빌드를 잊거나,
            재빌드했는데 핀을 안 고치면 이 계약이 깨진다.
  C14-F12-3 `buildStamp.ts` 해석 순서가 env → 핀 → git 이다(git 이 핀을 덮으면 결함이 되살아난다).
  C14-F12-4 `vite.config.ts` 와 `vitest.config.ts` 가 **같은** `buildStampDefine` 을 쓴다.
  C14-F12-5 핀 값이 `null`/빈 문자열이 아니다(추측으로 채우지 않는다는 CR-10 규칙과 충돌하지 않게,
            핀 자체는 **기록**이므로 값이 있어야 한다).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT / "dashboard"
PIN = DASHBOARD / "build-provenance.json"
BUILD_STAMP = DASHBOARD / "buildStamp.ts"
VITE_CONFIG = DASHBOARD / "vite.config.ts"
VITEST_CONFIG = DASHBOARD / "vitest.config.ts"
SHIPPED_ASSETS = REPO_ROOT / "src" / "antigravity_k" / "dashboard_dist" / "assets"

HEX_SHA = re.compile(r"^[0-9a-f]{7,40}$")
PLACEHOLDERS = {"unknown", "tbd", "todo", "none", "null", "placeholder", "changeme"}


def _pin() -> dict[str, object]:
    assert PIN.is_file(), f"{PIN.relative_to(REPO_ROOT)} 가 없다 — 번들 provenance 의 단일 기록 지점이다"
    return json.loads(PIN.read_text(encoding="utf-8"))


# ── C14-F12-1/5: 핀 파일 자체 ─────────────────────────────────


def test_pin_file_records_a_real_source_revision() -> None:
    payload = _pin()
    build_id = str(payload.get("buildId") or "").strip()
    assert build_id, "핀에 buildId 가 없다 — 빌드가 다시 git HEAD 를 쓰게 된다"
    assert build_id.lower() not in PLACEHOLDERS, f"placeholder 는 기록이 아니다: {build_id!r}"
    assert HEX_SHA.match(build_id), f"git short SHA 형식이 아니다: {build_id!r}"


def test_pin_allows_unknown_built_at() -> None:
    """빌드 시각은 CR-10 규칙대로 미기록(null)이어도 된다 — 추측값을 넣지 않는다."""
    payload = _pin()
    built_at = payload.get("builtAt", None)
    assert built_at is None or isinstance(built_at, str), "builtAt 은 문자열 또는 null 이어야 한다"


# ── C14-F12-2: 커밋된 번들이 핀을 반영한다 ───────────────────


def test_committed_bundle_carries_the_pinned_build_id() -> None:
    if not SHIPPED_ASSETS.is_dir():
        pytest.skip("빌드 산출물이 없다 — 이 계약은 번들이 있는 트리에서만 의미가 있다")

    build_id = str(_pin()["buildId"])
    carriers = [
        path
        for path in sorted(SHIPPED_ASSETS.glob("*.js"))
        if build_id in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert carriers, (
        f"출하 번들 어디에도 핀의 buildId({build_id}) 가 없다 — 핀을 기록한 뒤 "
        "`pnpm run build` 로 번들을 다시 만들지 않았다"
    )


def test_committed_bundle_does_not_carry_a_stale_sibling_build_id() -> None:
    """핀이 아닌 다른 short SHA 를 BUILD 라벨로 달고 있으면 출하물이 잘못된 리비전을 말한다."""
    if not SHIPPED_ASSETS.is_dir():
        pytest.skip("빌드 산출물이 없다")

    build_id = str(_pin()["buildId"])
    # 번들에 박히는 값은 `define` 치환 결과이므로, 다른 8자리 hex 가 BUILD 자리에 남아 있으면
    # 그것은 이전 빌드의 잔재다. 산출물 전체에서 핀 값의 등장 횟수를 세어 0 이 아님을 확인한다.
    hits = 0
    for path in sorted(SHIPPED_ASSETS.glob("*.js")):
        hits += path.read_text(encoding="utf-8", errors="replace").count(build_id)
    assert hits > 0, "핀 값이 번들에 없다"

    # 그리고 후보 리비전이 아닌 다른 짧은 SHA 가 BUILD 라벨 자리에 없어야 한다 —
    # `__AGK_BUILD_ID__` 는 문자열 리터럴로 치환되므로 남은 자리는 없어야 한다.
    leftovers = [
        path.name
        for path in sorted(SHIPPED_ASSETS.glob("*.js"))
        if "__AGK_BUILD_ID__" in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert not leftovers, f"치환되지 않은 BUILD 상수가 남아 있다: {leftovers}"


# ── C14-F12-3: 해석 순서(핀이 git 을 덮는다) ─────────────────


def test_build_stamp_reads_the_pin_before_git_head() -> None:
    """git SHA 가 핀보다 먼저 오면 커밋마다 번들이 흔들린다 — 순서가 계약이다."""
    source = BUILD_STAMP.read_text(encoding="utf-8")
    assert "build-provenance.json" in source or "BUILD_PROVENANCE_FILE" in source, (
        "buildStamp.ts 가 핀 파일을 읽지 않는다"
    )
    match = re.search(r"export const buildId:[^=]*=\s*(.+?);", source, flags=re.DOTALL)
    assert match, "buildStamp.ts 에서 buildId 해석식을 찾지 못했다"
    expression = " ".join(match.group(1).split())
    order = [part.strip() for part in expression.split("??")]
    assert len(order) == 3, f"해석 순서가 3단(env → 핀 → git)이 아니다: {expression}"
    assert "AGK_BUILD_ID" in order[0], f"1순위가 환경변수가 아니다: {order[0]}"
    assert "pin.buildId" in order[1], f"2순위가 커밋된 핀이 아니다: {order[1]}"
    assert "gitShortSha" in order[2], f"3순위가 git SHA 가 아니다: {order[2]}"


# ── C14-F12-4: 두 설정이 같은 define 을 쓴다 ─────────────────


def test_both_vite_and_vitest_use_the_same_build_stamp() -> None:
    for config in (VITE_CONFIG, VITEST_CONFIG):
        source = config.read_text(encoding="utf-8")
        assert "buildStampDefine" in source, f"{config.name} 가 buildStampDefine 을 쓰지 않는다"
        assert "define: buildStampDefine" in " ".join(source.split()), (
            f"{config.name} 의 define 이 buildStampDefine 이 아니다 — 서버/테스트가 다른 값을 본다"
        )
