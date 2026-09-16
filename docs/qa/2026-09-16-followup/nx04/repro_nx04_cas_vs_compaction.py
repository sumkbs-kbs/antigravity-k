#!/usr/bin/env python
"""NX-04 driver: 같은 부하를 옛 판정식과 새 판정식으로 각각 채점한다.

카드 문제: `final_count >= appended`(view 메시지 수 >= 성공 수)는 압축이 켜지면
**유효한 저장을 유실로 오인**한다. 이 드라이버는 같은 결정적 부하(cap64, 순차
append)에 두 판정식을 적용해 그 false positive 를 실측으로 보여주고, 새 판정식이
CAS 유실과 정상 압축을 분리해 보고하는지 확인한다.

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx04/repro_nx04_cas_vs_compaction.py

동시 writer(진짜 CAS 경쟁) 증거는 `tests/test_val02_conversation_multiprocess.py`
가 담당한다(이 드라이버는 순차 결정적 부하만 다룬다).
"""

from __future__ import annotations

import json
import os
import random
import statistics
import tempfile
import time
from pathlib import Path

CAP_ENV = "AGK_CONVERSATION_SOFT_MAX_MESSAGES"
PRODUCT_CAP = 64
SEQUENTIAL_APPENDS = 120  # cap64 에서 압축이 두 번 일어나는 양(65, 123 근처)
SEEDED_REPETITIONS = 10
CONSTRAINT_TEXT = "승인 없이 도구를 실행하지 마"


def _run_sequential(storage: Path, *, soft_max: int, appends: int, seed: int) -> dict:
    """순차 append 결과를 옛/새 판정식이 함께 먹을 수 있는 원시 관측으로 만든다."""
    from antigravity_k.engine.conversation_store import ConversationStore

    os.environ[CAP_ENV] = str(soft_max)
    rng = random.Random(seed)
    store = ConversationStore(storage_dir=storage)
    expected_ids: list[str] = []
    started = time.perf_counter()
    for i in range(appends):
        message_id = f"seq-{i:04d}"
        store.append(
            project_id="p",
            conversation_id="c",
            expected_revision=i,
            role="user" if i == 0 else rng.choice(["user", "assistant", "tool"]),
            content=CONSTRAINT_TEXT if i == 0 else f"turn-{i}-{rng.randrange(10**6)}",
            message_id=message_id,
        )
        expected_ids.append(message_id)
    elapsed = time.perf_counter() - started

    record = store.get(project_id="p", conversation_id="c")
    originals = store.original_history(project_id="p", conversation_id="c")
    assert record is not None
    return {
        "soft_max": soft_max,
        "appends_requested": appends,
        "successes": len(expected_ids),
        "view_messages": len(record.messages),
        "originals": len(originals),
        "original_ids_in_order": [str(m.get("id")) for m in originals] == expected_ids,
        "revision": record.revision,
        "compaction_generations": record.memory.generation,
        "constraint_preserved": any(c.text == CONSTRAINT_TEXT for c in record.memory.active_constraints()),
        "elapsed_s": round(elapsed, 3),
        "appends_per_s": round(appends / elapsed, 1) if elapsed else None,
    }


def _old_judge(observation: dict) -> dict:
    """VAL-02 원래 판정: view 메시지 수 >= 성공 append 수."""
    lost = max(0, observation["successes"] - observation["view_messages"])
    return {
        "judge": "old(view_count >= successes)",
        "claimed_lost_messages": lost,
        "verdict": "PASS" if lost <= 0 and observation["view_messages"] >= observation["successes"] else "FAIL",
    }


def _new_judge(observation: dict) -> dict:
    """NX-04 판정 분리: (a) CAS 유실 0 = 원본 기준, (b) 압축은 별도 관측."""
    cas = {
        "originals_lost": max(0, observation["successes"] - observation["originals"]),
        "revision_matches_successes": observation["revision"] == observation["successes"],
        "originals_in_order": observation["original_ids_in_order"],
    }
    compaction_enabled = observation["soft_max"] > 0
    compaction = {
        "compaction_enabled": compaction_enabled,
        "view_bounded": (not compaction_enabled) or observation["view_messages"] <= observation["soft_max"],
        "generations": observation["compaction_generations"],
        "compaction_observed": (not compaction_enabled)
        or (observation["view_messages"] < observation["successes"] and observation["compaction_generations"] >= 1),
        # cap0 은 "압축을 끈 두 번째 구성" 이므로 압축이 일어나지 않아야 한다.
        "no_compaction_as_configured": compaction_enabled
        or (observation["compaction_generations"] == 0 and observation["view_messages"] == observation["successes"]),
    }
    ok = (
        cas["originals_lost"] == 0
        and cas["revision_matches_successes"]
        and cas["originals_in_order"]
        and compaction["view_bounded"]
        and compaction["compaction_observed"]
        and compaction["no_compaction_as_configured"]
    )
    return {
        "judge": "new(cas+compaction split)",
        "cas": cas,
        "compaction": compaction,
        "verdict": "PASS" if ok else "FAIL",
    }


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="nx04-driver-"))
    # (1) 같은 부하를 두 판정식으로 채점 — 옛 판정식의 false positive 실측
    observation = _run_sequential(root / "judge", soft_max=PRODUCT_CAP, appends=SEQUENTIAL_APPENDS, seed=0)
    old = _old_judge(observation)
    new = _new_judge(observation)

    # (2) cap0 — 압축을 끄고 CAS 계약만 보는 두 번째 구성
    cap0 = _run_sequential(root / "cap0", soft_max=0, appends=20, seed=0)
    cap0_judgement = _new_judge({**cap0, "soft_max": 0})

    # (3) 고정 seed 10회 반복 — 같은 불변식 유지 여부와 성능 수치(반복별 보고)
    repetitions = []
    for seed in range(SEEDED_REPETITIONS):
        obs = _run_sequential(root / f"seed-{seed}", soft_max=PRODUCT_CAP, appends=123, seed=seed)
        judgement = _new_judge(obs)
        repetitions.append({**obs, "verdict": judgement["verdict"], "seed": seed})

    elapsed = [r["elapsed_s"] for r in repetitions]
    report = {
        "schema": "nx04-cas-vs-compaction/1",
        "tree": str(Path(__file__).resolve()),
        "cap_env": CAP_ENV,
        "product_cap": PRODUCT_CAP,
        "judge_comparison": {
            "observation": observation,
            "old": old,
            "new": new,
            "note": (
                "같은 저장 결과를 옛 판정식은 유실로 오인하고(claimed_lost_messages>0), 새 판정식은 "
                "CAS 유실 0 + 압축 관측으로 분리 보고한다."
            ),
        },
        "cap0_configuration": {"observation": cap0, "judgement": cap0_judgement},
        "seeded_repetitions": {
            "count": len(repetitions),
            "all_verdicts_pass": all(r["verdict"] == "PASS" for r in repetitions),
            "elapsed_s": elapsed,
            "elapsed_median_s": round(statistics.median(elapsed), 3) if elapsed else None,
            "elapsed_max_s": max(elapsed) if elapsed else None,
            "appends_per_s_median": round(statistics.median([r["appends_per_s"] for r in repetitions]), 1)
            if repetitions
            else None,
            "runs": repetitions,
        },
        "verdict": "PASS"
        if (
            new["verdict"] == "PASS"
            and cap0_judgement["verdict"] == "PASS"
            and all(r["verdict"] == "PASS" for r in repetitions)
        )
        else "FAIL",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
