"""chain_status.py 계약 — 상태판은 **파일과 종료 코드**로만 말하고, 아무것도 쓰지 않는다.

왜 계약이 필요한가(2026-09-18 실측):
    죽은 무인 체인을 다음 사람이 손으로 복원하는 일이 이 창에서 **한 번 실패했다**. 상태판이
    문장을 읽거나 낡은 기록을 현재로 오해하면, 그 실패를 자동화해 반복하게 된다. 그래서 여기서
    고정하는 것은 “무엇을 말하는가”가 아니라 **“무엇을 근거로 삼는가”** 다.

계약(이 시험이 지키는 문장):
  · **S-1 읽기 전용**: 상태판은 어떤 파일도 만들지 않는다(도는 체인의 측정에 끼어들지 않는다).
  · **S-2 커밋이 근거**: 배치의 “적용”은 커밋 제목으로 판정한다(로그 문장·mtime 이 아니다).
  · **S-3 리포트가 근거**: “게이트 완료”는 리포트 JSON 의 요약으로만 판정한다.
  · **S-4 낡은 중단은 현재가 아니다**: 마지막 `# 배치 체인 — 시작` **뒤**의 `## 중단` 만 현재로 본다.
  · **S-5 soak 귀속**: 시작/종료 지문이 같을 때만 “귀속 성립”이라 말한다.
  · **S-6 다음 할 일**: 진행 상태에서 **계산**되고, 판단할 수 없으면 그렇게 말한다.

실행:
  .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/batchchain/test_chain_status_contract.py -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NX10 = HERE.parent


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("nx10_chain_status", HERE / "chain_status.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STATUS = _load()


def _fixture(
    root: Path,
    *,
    gate_labels: list[tuple[str, dict[str, Any]]],
    record: str = "",
    soak_exit: str = "",
    verdict: dict[str, Any] | None = None,
) -> Path:
    """가짜 nx10 트리를 만든다(`repo` 는 진짜 저장소 — `git log` 만 진짜를 쓴다).

    실제 `git log` 를 읽는 이유: S-2 는 “커밋이 근거”라는 계약이라, 커밋 판정만은 실제 저장소에서
    확인해야 의미가 있다(시험은 그 판정을 **합성 제목**으로 검증한다).
    """
    (root / "batchchain").mkdir(parents=True, exist_ok=True)
    for label, summary in gate_labels:
        (root / f"gate-report-{label}.json").write_text(json.dumps({"summary": summary, "git": {}}), encoding="utf-8")
    if record:
        (root / "batchchain" / "batchchain-record.md").write_text(record, encoding="utf-8")
    if soak_exit:
        (root / "soak-exit.txt").write_text(soak_exit, encoding="utf-8")
    if verdict is not None:
        (root / "soak-recovery-latest.json").write_text(json.dumps(verdict), encoding="utf-8")
    return root


def test_the_panel_writes_nothing(tmp_path: Path) -> None:
    """S-1 — 읽기 전용. 새 파일이 하나도 생기지 않아야 한다(도는 체인에 끼어들지 않는다)."""
    _fixture(tmp_path, gate_labels=[("batch-sc6", {"passed": 3, "failed": 0, "total": 3})])
    before = sorted(p.name for p in tmp_path.rglob("*"))
    # 픽스처는 저장소 밖이라 `git log` 근거만 **실제 저장소**를 준다(계약 S-2 가 진짜 커밋을 본다).
    state = STATUS.collect(tmp_path, STATUS.repo_root(NX10))
    after = sorted(p.name for p in tmp_path.rglob("*"))
    assert before == after, "상태판이 파일을 만들었다"
    assert state["batches"][0]["batch"] == "SC6"  # 읽었다는 최소 증거


def test_applied_is_decided_by_the_commit_not_by_a_log_sentence(tmp_path: Path) -> None:
    """S-2 — 커밋이 근거. 합성 제목은 커밋 이력에 없으므로 “적용 안 됨”이다."""
    _fixture(tmp_path, gate_labels=[])
    states = STATUS.batch_states(STATUS.repo_root(NX10), tmp_path)
    real = STATUS.recent_commits(STATUS.repo_root(NX10))
    # 이 창의 실제 배치 커밋은 이력에 있다(SC6 는 실제로 적용됐다).
    sc6 = next(state for state in states if state["batch"] == "SC6")
    assert any("judge SC-6 by the creep" in line for line in real)
    assert sc6["applied"] is (sc6["commit"] is not None)
    # 합성 제목은 이력에 없다 → 어느 배치도 그것으로 “적용됨”이 되지 않는다.
    assert all("합성 제목" not in (state["commit"] or "") for state in states)


def test_a_gate_summary_is_read_from_the_report(tmp_path: Path) -> None:
    """S-3 — 게이트 완료는 리포트 요약으로 판정한다(리포트가 없으면 없다고 말한다)."""
    _fixture(tmp_path, gate_labels=[("batch-flush", {"passed": 22, "failed": 1, "total": 23})])
    assert STATUS.gate_summary(tmp_path, "batch-flush")["summary"]["passed"] == 22
    assert STATUS.gate_summary(tmp_path, "batch-perf") is None


def test_a_stale_stop_is_not_the_current_state(tmp_path: Path) -> None:
    """S-4 — 낡은 중단은 현재가 아니다. 이 창에서 실제로 난 실수의 일반형이다."""
    record = (
        "\n# 배치 체인 — 시작 2026-09-17T11:27:30Z\n\n"
        "## 중단 (2026-09-17T12:19:48Z)\n\n- 단계: 2\n- 사유: 옛 사유(게이트 리포트 없음)\n"
        "\n# 배치 체인 — 시작 2026-09-17T21:52:47Z\n"
    )
    _fixture(tmp_path, gate_labels=[], record=record)
    stop = STATUS.chain_stop(tmp_path)
    assert stop is None, "새 시작 뒤에는 중단 기록이 없다 — 낡은 중단을 현재로 읽었다"


def test_a_stop_after_the_last_start_is_reported_with_its_step(tmp_path: Path) -> None:
    """S-4(양성) — 마지막 시작 뒤의 중단은 단계·사유와 함께 보고한다."""
    record = (
        "\n# 배치 체인 — 시작 2026-09-17T11:27:30Z\n"
        "\n# 배치 체인 — 시작 2026-09-17T21:52:47Z\n\n"
        "## 중단 (2026-09-17T22:40:00Z)\n\n- 단계: 5\n- 사유: FLUSH 적용 실패(사전 이미지 불일치)\n"
    )
    _fixture(tmp_path, gate_labels=[], record=record)
    stop = STATUS.chain_stop(tmp_path)
    assert stop == {"at": "2026-09-17T22:40:00Z", "step": "5", "reason": "FLUSH 적용 실패(사전 이미지 불일치)"}


def test_attribution_needs_the_two_fingerprints_to_match(tmp_path: Path) -> None:
    """S-5 — 시작/종료 지문이 같을 때만 “귀속 성립”이다(다르면 갈렸다고 말한다)."""
    marker = "# NX-10 SC-1~6 soak 러너 기록\n"
    same = marker + "start_time: a\nend_time: b\nexit: 0\nstart_fingerprint: aa\nend_fingerprint: aa\n"
    _fixture(tmp_path, gate_labels=[], soak_exit=same)
    assert STATUS.last_soak_block(tmp_path)["attributed"] is True

    other = tmp_path / "other"
    _fixture(other, gate_labels=[], soak_exit=marker + "start_fingerprint: aa\nend_fingerprint: bb\n")
    assert STATUS.last_soak_block(other)["attributed"] is False


def test_the_last_soak_block_is_the_last_one(tmp_path: Path) -> None:
    """여러 회차가 쌓인 파일에서 **마지막** 블록을 읽는다(첫 회차를 집으면 상태가 과거가 된다)."""
    marker = "# NX-10 SC-1~6 soak 러너 기록\n"
    text = marker + "start_time: old\nend_fingerprint: old\n" + marker + "start_time: new\nend_fingerprint: new\n"
    _fixture(tmp_path, gate_labels=[], soak_exit=text)
    assert STATUS.last_soak_block(tmp_path)["start_time"] == "new"


def test_next_action_is_computed_and_says_so_when_it_cannot(tmp_path: Path) -> None:
    """S-6 — 다음 할 일은 진행 상태에서 계산한다. 모르면 모른다고 말한다(없는 근거를 집지 않는다)."""
    states = [
        {"batch": "SC6", "commit": "abc", "applied": True, "gates": {"summary": {}}},
        {"batch": "PERF", "commit": None, "applied": False, "gates": None},
        {"batch": "FLUSH", "commit": None, "applied": False, "gates": None},
        {"batch": "FLUSH2", "commit": None, "applied": False, "gates": None},
    ]
    assert "PERF" in STATUS.next_action(states, None, [{"label": "배치 체인"}])

    half = [
        {"batch": "SC6", "commit": "abc", "applied": True, "gates": None},
        {"batch": "PERF", "commit": None, "applied": False, "gates": None},
    ]
    assert "게이트" in STATUS.next_action(half, None, [{"label": "배치 체인"}])

    all_done = [dict(state, gates={"summary": {}}) for state in states]
    all_done[1]["applied"] = all_done[2]["applied"] = all_done[3]["applied"] = True
    assert "soak" in STATUS.next_action(all_done, None, [])

    stopped = STATUS.next_action(states, {"step": "5", "at": "t", "reason": "r"}, [])
    assert "멈췄다" in stopped
