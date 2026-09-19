"""실제 실행 재판정 계약 — 새 SC-6 기준이 **실제 자료**에서도 옳게 판정하는가.

왜 계약이 필요한가(문서가 스스로 남긴 위험):
    새 기준의 검증은 합성 픽스처 8건뿐이었고 문서는 그것을 “남는 위험: 통과 경로는 합성 픽스처로만
    증명”이라고 적어 두었다. 이 시험은 그 문장을 **실제로 기록된 실행**으로 닫는다 — 재구현이 아니라
    **적용된 함수**(`scripts/val02_staging.py`)를 불러서 판정한다.

계약(이 시험이 지키는 문장 — 근거는 `sc6fix/replay-real-runs.json` 이 아니라 **기록된 리포트 원본**):
  · **R-1 진짜 누수는 잡는다**: 1,683 MB 누수 실행은 모든 시각 모델에서 `fail` 이고, 반복당 creep 이
    상한의 **100배 규모**다.
  · **R-2 건강한 실행은 통과한다**: 4차 실행은 모든 시점 모델에서 `pass` 이고, **창 밖 증가 < 총 증가**
    (워밍업이 실제로 제외된다 — 재설계의 목적이 이것이다).
  · **R-3 판정 불가는 판정 불가로**: 60초 리허설은 `not_applicable` 이다(옛 기준이라면 +21.2 MB 를
    64 MB 와 비교해 통과로 읽었다 — 그 읽기가 바로 오해였다).
  · **R-4 시각 모델에 흔들리지 않는다**: 세 실행 모두 이빨(±20%)에서 판정이 유지된다. 흔들리는 자료에서는
    그 사실을 `mixed` 로 말한다(모델을 골라 통과시키지 않는다).

이빨(음성 대조군):
  · 평평한 합성 시리즈 → `pass`.
  · 창 **뒤**에 계단이 있는 합성 시리즈 → 시각 모델에 따라 판정이 갈린다(`mixed`). 창을 어디에 두느냐가
    판정을 바꾸는 자료라면 그렇게 말하는 것이 계약이다.

실행:
  PYTHONPATH=src .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/sc6fix/test_replay_real_runs_contract.py -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NX10 = HERE.parent

NAMES = {"누수": "soak-28800-fail001.json", "4차": "soak-28800.json", "리허설": "soak-60.json"}


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPLAY = _load(HERE / "replay_real_runs.py", "nx10_replay_real_runs")
STAGING = REPLAY.load_staging(REPLAY.repo_root(HERE))


def _result(which: str) -> dict[str, Any]:
    report = NX10 / NAMES[which]
    assert report.is_file(), f"기록이 없다: {report}"
    result = REPLAY.replay(report, STAGING)
    assert "error" not in result, result
    return result


def _synthetic(tmp_path: Path, samples: list[float], duration_s: float = 28800.0) -> Path:
    report = tmp_path / "synthetic.json"
    report.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario": "SC-6-soak",
                        "rss_samples_mb": samples,
                        "actual_duration_s": duration_s,
                        "completed_ops": REPLAY.SAMPLE_EVERY_OPS * len(samples),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return report


def test_the_real_leak_fails_on_every_time_model() -> None:
    """R-1 — 실제 누수(1,683 MB)는 어느 시각 모델에서도 fail 이고 creep 이 상한의 100배 규모다."""
    result = _result("누수")
    assert result["verdict"] == "fail", result
    assert result["robust_to_time_model"] is True
    creeps = [arm["creep_kb_per_op"] for arm in result["arms"].values()]
    assert min(creeps) > 10 * STAGING.RSS_CREEP_MAX_KB_PER_OP, creeps
    assert all(arm["excluded_mb"] > result["old_criterion_limit_mb"] for arm in result["arms"].values())


def test_the_healthy_eight_hour_run_passes_and_excludes_the_warmup() -> None:
    """R-2 — 4차 실행은 pass 이고 **창 밖 증가가 총 증가보다 작다**(워밍업 제외가 실제로 일어난다)."""
    result = _result("4차")
    assert result["verdict"] == "pass", result
    assert result["robust_to_time_model"] is True
    for arm in result["arms"].values():
        assert arm["excluded_mb"] < result["total_growth_mb"], arm
        assert arm["creep_kb_per_op"] < STAGING.RSS_CREEP_MAX_KB_PER_OP / 10, arm


def test_the_sixty_second_rehearsal_is_not_judged() -> None:
    """R-3 — 60초 리허설은 판정 불가다(옛 기준은 +21.2 MB 를 64 MB 와 비교했다)."""
    result = _result("리허설")
    assert result["verdict"] == "not_applicable", result
    assert result["robust_to_time_model"] is True
    assert all(arm["index"] == -1 for arm in result["arms"].values())


def test_a_flat_series_passes(tmp_path: Path) -> None:
    """음성 대조군 ① — 평평한 시리즈는 통과한다(기준이 늘 빨간 것이 아니다)."""
    result = REPLAY.replay(_synthetic(tmp_path, [100.0] * 200), STAGING)
    assert result["verdict"] == "pass", result


def test_a_step_after_the_window_makes_the_time_model_matter(tmp_path: Path) -> None:
    """음성 대조군 ② — 창 **뒤**의 계단은 시각 모델에 따라 판정을 갈리게 한다 → `mixed` 로 말한다.

    이빨의 요점: 상태판·프로브가 “어느 모델에서도 같은 답”이라고 말할 때 그것이 **우연이 아님**을 보인다.
    """
    # 계단이 **창 경계(표본 8~12)** 안에서 오르므로, 창을 어디에 두느냐에 따라 “창 밖 증가”가 40 MB 가
    # 되기도 0 MB 가 되기도 한다 — 그 상태가 곧 “모델에 따라 뒤집힌다” 이다.
    samples = [100.0] * 8 + [110.0, 120.0, 130.0, 140.0] + [140.0] * 188
    result = REPLAY.replay(_synthetic(tmp_path, samples), STAGING)
    assert result["robust_to_time_model"] is False, result
    assert result["verdict"] == "mixed", result


def test_a_report_without_samples_is_refused_not_guessed(tmp_path: Path) -> None:
    """모르는 것을 아는 척하지 않는다 — 표본이 없으면 판정하지 않고 그렇게 말한다."""
    report = tmp_path / "empty.json"
    report.write_text(json.dumps({"scenarios": [{"scenario": "SC-6-soak", "actual_duration_s": 28800.0}]}), "utf-8")
    result = REPLAY.replay(report, STAGING)
    assert "error" in result and "표본" in result["error"], result


def test_the_recorded_json_matches_a_fresh_replay() -> None:
    """기록된 재판정 JSON 은 다시 돌린 결과와 같아야 한다(문서에 적힌 수치는 기록에서 나온다)."""
    recorded = HERE / "replay-real-runs.json"
    assert recorded.is_file(), "replay-real-runs.json 이 없다 — 먼저 프로브를 돌려 기록해야 한다"
    saved = {item["report"]: item for item in json.loads(recorded.read_text(encoding="utf-8"))}
    for which, filename in NAMES.items():
        fresh = _result(which)
        assert saved[filename]["verdict"] == fresh["verdict"], (which, saved[filename]["verdict"], fresh["verdict"])
        for share, arm in fresh["arms"].items():
            assert saved[filename]["arms"][share]["creep_kb_per_op"] == arm["creep_kb_per_op"], (which, share)
