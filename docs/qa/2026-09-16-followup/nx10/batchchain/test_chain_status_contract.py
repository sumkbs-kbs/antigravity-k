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
  · **S-7 게이트 자식은 무인 작업이 아니다**: 부모 계보를 따라 게이트가 돌린 시험을 걸러낸다.
  · **S-8 지금 도는 게이트**: 부분 리포트(“4/23”)는 **어느 게이트인지 말하지 못한다** — 로그 줄과
    리포트 id 를 대조해 이름을 붙이고, 대조가 안 되면(다른 attempt) **단정하지 않는다**.
    그리고 **부분 리포트를 끝난 배치로 세지 않는다**(그 오판이 다음 할 일을 한 칸 앞당겼다).

실행:
  .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/batchchain/test_chain_status_contract.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
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
    gate_ids: dict[str, list[str]] | None = None,
    log: str = "",
) -> Path:
    """가짜 nx10 트리를 만든다(`repo` 는 진짜 저장소 — `git log` 만 진짜를 쓴다).

    실제 `git log` 를 읽는 이유: S-2 는 “커밋이 근거”라는 계약이라, 커밋 판정만은 실제 저장소에서
    확인해야 의미가 있다(시험은 그 판정을 **합성 제목**으로 검증한다).
    """
    (root / "batchchain").mkdir(parents=True, exist_ok=True)
    for label, summary in gate_labels:
        doc: dict[str, Any] = {"summary": summary, "git": {}}
        ids = (gate_ids or {}).get(label)
        if ids is not None:
            # 실제 리포트는 **끝날 때까지 부분**이다(수집된 게이트만 들어 있다) — 그 모양을 그대로 만든다.
            doc["gates"] = [{"id": gate} for gate in ids]
        (root / f"gate-report-{label}.json").write_text(json.dumps(doc), encoding="utf-8")
    if log:
        (root / "promote-runner.log").write_text(log, encoding="utf-8")
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


def test_the_gate_in_flight_is_read_from_the_log_and_the_report(tmp_path: Path) -> None:
    """S-8 — 부분 리포트만으로는 “4/23”까지밖에 못 말한다. **어느 게이트인지**는 로그가 답한다.

    실측 동기: 이 창에서 “지금 무슨 게이트를 재고 있나”를 알려고 사람이 `ps` 를 두드려야 했다.
    """
    ids = [
        "python-ruff",
        "python-format",
        "python-mypy",
        "python-basedpyright",
        "python-tests",
        "python-benchmark",
    ]
    # 실제 로그는 진행하면서 자란다 — 다섯 번째 게이트가 **시작된 순간**의 모양으로 만든다.
    log = "=== promote-gates START 2026-09-18T06:52:53Z (6 gates) ===\n" + "".join(
        f"[{gate}] uv run --isolated pytest tests/\n" for gate in ids[:5]
    )
    _fixture(
        tmp_path,
        gate_labels=[("batch-sc6", {"passed": 4, "failed": 0, "total": 4})],
        gate_ids={"batch-sc6": ids[:4]},
        log=log,
    )
    sc6 = STATUS.batch_states(STATUS.repo_root(NX10), tmp_path)[0]
    assert sc6["gates_complete"] is False
    assert sc6["gates"]["gates"] == 4 and sc6["gates"]["ids"] == ids[:4]
    assert sc6["running_gate"]["id"] == "python-tests"

    # 경과는 **그 줄이 쓰인 시각**(로그 mtime) 기준이다 — 10분 전으로 못박고 확인한다.
    stamp = time.time() - 600
    os.utime(tmp_path / "promote-runner.log", (stamp, stamp))
    again = STATUS.gate_progress(tmp_path, ids[:4])
    assert 595 <= again["elapsed_seconds"] <= 605
    assert "python-tests" in STATUS.running_gate_text(again)
    # 로그의 줄을 다 채우면 “끝”이라 말한다(끝난 배치를 “도는 중”으로 잡지 않는다).
    assert STATUS.gate_progress(tmp_path, ids[:5])["state"] == "끝"
    # 리포트가 로그보다 **많은** id 를 갖는 것도 모순이다 — 그대로 단정하지 않는다.
    assert STATUS.gate_progress(tmp_path, ids)["state"] == "다른 attempt 의 로그"
    # 도는 게이트가 **마지막 줄이 아니면** 시작 시각을 모른다 — 그때는 경과를 지어내지 않는다.
    (tmp_path / "promote-runner.log").write_text(log + "[python-benchmark] x\n", encoding="utf-8")
    unknown = STATUS.gate_progress(tmp_path, ids[:4])
    assert unknown["id"] == "python-tests" and "elapsed_seconds" not in unknown
    assert "경과 미상" in STATUS.running_gate_text(unknown)


def test_a_log_from_another_attempt_is_not_used_to_name_a_gate(tmp_path: Path) -> None:
    """S-8(음성) — 리포트의 id 들이 로그 순서의 **앞머리**가 아니면 단정하지 않는다.

    로그는 attempt 마다 쌓인다. 옛 로그와 새 리포트를 섞으면 “지금 [python-tests]”가 거짓이 된다.
    """
    log = "=== promote-gates START … ===\n[python-ruff] x\n[python-format] x\n"
    _fixture(tmp_path, gate_labels=[("batch-sc6", {})], gate_ids={"batch-sc6": ["python-format"]}, log=log)
    assert STATUS.gate_progress(tmp_path, ["python-format"])["state"] == "다른 attempt 의 로그"
    # 로그가 없으면 모른다(없는 근거를 집지 않는다).
    assert STATUS.gate_progress(tmp_path / "nolog", []) is None


def test_a_partial_report_is_not_a_finished_batch(tmp_path: Path) -> None:
    """S-3(정밀) — 4/23 인 리포트를 “게이트 있다”로 세면 배치가 끝난 걸로 보인다.

    이 창에서 실제로 난 오판이다: SC6 을 재고 있는 중인데 다음 할 일이 **PERF** 로 건너갔다.
    """
    running = {"state": "진행 중", "id": "python-tests", "command": "pytest", "elapsed_seconds": 755.9}
    states = [
        _synth("SC6", True, 4, running),
        _synth("PERF", False, None),
        _synth("FLUSH", False, None),
        _synth("FLUSH2", False, None),
    ]
    action = STATUS.next_action(states, None, [{"label": "배치 체인"}])
    assert "SC6" in action and "python-tests" in action, action
    assert "PERF " not in action, "부분 리포트를 끝난 배치로 세었다"

    # 로그가 다른 attempt 면 이름을 붙이지 않고 그렇게 말한다.
    mismatch = STATUS.next_action([_synth("SC6", True, 4, {"state": "다른 attempt 의 로그"}), *states[1:]], None, [])
    assert "단정하지 않는다" in mismatch, mismatch


def test_a_gate_child_is_not_reported_as_an_unattended_job() -> None:
    """S-7 — 게이트가 돌리는 시험의 자식은 **무인 작업이 아니다**.

    첫 실행에서 실측한 거짓말: 게이트 `python-tests` → `soak_control.sh --selftest` → **진짜
    `soak_control.sh harvest` 자식**. 부모를 안 보면 상태판이 그것을 “회수 대기”로 보고한다.
    """
    tree = {
        52743: (50573, "bash scripts/soak_control.sh harvest"),
        50573: (47410, "bash scripts/soak_control.sh selftest"),
        47410: (1, ".venv/bin/python -m pytest tests/"),
    }
    assert STATUS.is_gate_child(52743, tree.get) is True

    detached = {
        900: (899, "bash scripts/soak_control.sh harvest --detach"),
        899: (1, "SCREEN -dmS nx10harvest caffeinate -i bash -c …"),
    }
    assert STATUS.is_gate_child(900, detached.get) is False
    # 부모를 모르면 단정하지 않는다(없는 근거를 집지 않는 원칙).
    assert STATUS.is_gate_child(1, lambda _pid: None) is False


def _synth(batch: str, applied: bool, collected: int | None, running: dict[str, Any] | None = None) -> dict[str, Any]:
    """합성 배치 상태 — `batch_states` 가 만드는 모양 그대로(수집 수·완료 여부·도는 게이트)."""
    return {
        "batch": batch,
        "commit": "abc" if applied else None,
        "applied": applied,
        "gates": {"summary": {}, "gates": collected} if collected is not None else None,
        "gates_complete": collected is not None and collected >= STATUS.EXPECTED_GATES,
        "running_gate": running,
    }


def test_next_action_is_computed_and_says_so_when_it_cannot(tmp_path: Path) -> None:
    """S-6 — 다음 할 일은 진행 상태에서 계산한다. 모르면 모른다고 말한다(없는 근거를 집지 않는다)."""
    states = [
        _synth("SC6", True, STATUS.EXPECTED_GATES),
        _synth("PERF", False, None),
        _synth("FLUSH", False, None),
        _synth("FLUSH2", False, None),
    ]
    assert "PERF" in STATUS.next_action(states, None, [{"label": "배치 체인"}])

    half = [_synth("SC6", True, None), _synth("PERF", False, None)]
    assert "게이트" in STATUS.next_action(half, None, [{"label": "배치 체인"}])

    all_done = [_synth(batch, True, STATUS.EXPECTED_GATES) for batch in ("SC6", "PERF", "FLUSH", "FLUSH2")]
    assert "soak" in STATUS.next_action(all_done, None, [])

    stopped = STATUS.next_action(states, {"step": "5", "at": "t", "reason": "r"}, [])
    assert "멈췄다" in stopped
