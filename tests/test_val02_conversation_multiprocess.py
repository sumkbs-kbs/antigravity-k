"""VAL-02 / NX-04 회귀 — CAS 검증과 압축 검증을 분리한다.

VAL-02 staging(SC-2)에서 발견한 결함을 잠근다:
  F1  결정론적 tmp 파일명(<conv>.tmp) — 동시 writer가 서로의 tmp를 치환해
      FileNotFoundError로 메시지 유실.
  F2  프로세스별 메모리 캐시만으로 CAS 평가 — 다른 프로세스의 append가
      보이지 않아 CAS가 통과하고 마지막 쓰기가 이긴다(침묵 덮어쓰기).

NX-04 진단: `final_count >= appended` 는 압축이 켜지면 **유효한 압축을 유실로
오인**하고, 경쟁으로 성공 수가 64 미만이면 결함 검증 자체가 비결정적이 된다.
따라서 한 assertion 안에서 두 계약을 섞지 않는다.

| 시험 | cap | 검증하는 계약 |
|---|---|---|
| `test_cap0_…success_set_is_exactly_the_stored_set` | 0 (압축 끔) | CAS만: 성공 ID = 저장 ID, 거절 ID 미반영, revision = 성공 수 |
| `test_cap0_…rejected_not_silent` | 0 | stale 패자는 명시적 409 (반환값 위장 금지) |
| `test_cap64_sequential_…` | 64 (제품 기본) | 결정적 123 append, 압축 ≥2회, revision/원본 손실 0, view ≤ 64 |
| `test_cap64_multiprocess_…` | 64 (제품 기본) | 경쟁에서도 성공 ≥123, **원본 유실 0** 과 **압축 발생** 을 별도 결과로 식별 |
| `test_seed_fixed_repetition_…` | 64 (제품 기본) | 고정 seed 10회 반복에서 같은 불변식 |

금지 사항(카드): assertion 삭제, 하한 0 완화, cap 무한 고정으로 제품 설정 회피,
무관한 과거 fail 수치를 성공에 합산 — 모두 하지 않는다. cap0 은 제품 기본값을
숨기기 위한 것이 아니라 CAS 만 분리 관측하기 위한 **명시적 두 번째 구성**이며,
제품 기본값(cap64)은 별도 시험이 각각 검증한다.

정본 계수 기준은 NX-02 의 원본 이력(journal)이다. view 는 bounded 이므로
성공 append 수와 같아질 수 없다(그 둘을 분리해 관측하는 것이 이 카드의 목적).
"""

from __future__ import annotations

import multiprocessing as mp
import os
import random
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import Any

import pytest

CAP_ENV = "AGK_CONVERSATION_SOFT_MAX_MESSAGES"
PRODUCT_CAP = 64  # ConversationStore._DEFAULT_SOFT_MAX_MESSAGES 와 동일하게 유지
REQUIRED_SUCCESSES = 123  # 카드: 최소123개 성공으로 두 번 압축이 반드시 발생
JOIN_TIMEOUT_S = 120  # 명시적 종료 한도(초과하면 테스트 실패)
BARRIER_TIMEOUT_S = 60
CONSTRAINT_TEXT = "승인 없이 도구를 실행하지 마"


# ── worker ──────────────────────────────────────────────────────────────


def _cas_worker(
    storage_dir: str,
    project_id: str,
    conversation_id: str,
    soft_max: int,
    prefix: str,
    turns: int,
    max_attempts: int,
    barrier: Barrier,
    out: Queue[dict[str, Any]],
) -> None:
    """Bounded-retry CAS writer: 성공 ID / 거절 ID / 오류를 분리해 보고한다.

    stale 패자는 **새 message id** 로 재시도하므로, 거절된 ID 가 나중에
    저장되지 않았음을 집합으로 검증할 수 있다.
    """
    os.environ[CAP_ENV] = str(soft_max)
    from antigravity_k.engine.conversation_store import ConversationStore, StaleConversationRevisionError

    store = ConversationStore(storage_dir)
    success_ids: list[str] = []
    rejected_ids: list[str] = []
    stale = 0
    errors = 0
    attempts = 0
    barrier.wait(timeout=BARRIER_TIMEOUT_S)
    while len(success_ids) < turns and attempts < max_attempts:
        attempts += 1
        message_id = f"{prefix}-{attempts}"
        revision = store.get_revision(project_id=project_id, conversation_id=conversation_id) or 0
        try:
            store.append(
                project_id=project_id,
                conversation_id=conversation_id,
                expected_revision=revision,
                role="user",
                content=f"{message_id} body",
                message_id=message_id,
            )
            success_ids.append(message_id)
        except StaleConversationRevisionError:
            stale += 1
            rejected_ids.append(message_id)  # 명시적 거절 — 유실이 아니다
        except FileNotFoundError:
            errors += 1  # F1 재발: tmp 경합이 드러나면 안 된다
            break
        except Exception:
            errors += 1
            break
    out.put(
        {
            "success_ids": success_ids,
            "rejected_ids": rejected_ids,
            "stale": stale,
            "errors": errors,
            "attempts": attempts,
        }
    )


def _join(process: mp.Process) -> int:
    process.join(timeout=JOIN_TIMEOUT_S)
    if process.is_alive():
        process.terminate()
        process.join(timeout=10)
        pytest.fail(f"worker 가 {JOIN_TIMEOUT_S}s 안에 종료하지 않았다: pid={process.pid}")
    assert process.exitcode == 0, f"worker 비정상 종료: {process.exitcode}"
    return process.exitcode


def _run_race(
    storage_dir: Path,
    *,
    soft_max: int,
    workers: int,
    turns: int,
    max_attempts: int,
) -> dict[str, Any]:
    """barrier 로 동시에 시작하는 CAS 경쟁을 실행하고 원본/view 를 함께 관측한다."""
    from antigravity_k.engine.conversation_store import ConversationStore

    os.environ[CAP_ENV] = str(soft_max)  # spawn 자식도 같은 제품 설정을 본다
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(workers)
    out: Queue[dict[str, Any]] = ctx.Queue()
    processes = [
        ctx.Process(
            target=_cas_worker,
            args=(str(storage_dir), "proj", "conv", soft_max, f"w{i}", turns, max_attempts, barrier, out),
        )
        for i in range(workers)
    ]
    for process in processes:
        process.start()
    results = [out.get(timeout=JOIN_TIMEOUT_S) for _ in processes]
    for process in processes:
        _join(process)

    reader = ConversationStore(storage_dir)
    record = reader.get(project_id="proj", conversation_id="conv")
    originals = reader.original_history(project_id="proj", conversation_id="conv")
    success_ids = [mid for result in results for mid in result["success_ids"]]
    rejected_ids = [mid for result in results for mid in result["rejected_ids"]]
    return {
        "soft_max": soft_max,
        "workers": workers,
        "requested_per_worker": turns,
        "success_ids": success_ids,
        "rejected_ids": rejected_ids,
        "stale_rejected": sum(result["stale"] for result in results),
        "unexpected_errors": sum(result["errors"] for result in results),
        "attempts": sum(result["attempts"] for result in results),
        "revision": record.revision if record is not None else -1,
        "stored_view_ids": [m.id for m in record.messages] if record is not None else [],
        "view_count": len(record.messages) if record is not None else -1,
        "compaction_generations": record.memory.generation if record is not None else -1,
        "originals": originals,
        "original_ids": [str(m.get("id")) for m in originals],
    }


# ── 1) cap0: CAS 계약만 본다 ────────────────────────────────────────────


def test_cap0_cas_success_set_is_exactly_the_stored_set(tmp_path: Path) -> None:
    """압축을 끄고 CAS 만 검증: 성공 ID = 저장 ID, 거절 ID 는 미반영, revision = 성공 수."""
    report = _run_race(tmp_path / "cap0", soft_max=0, workers=4, turns=8, max_attempts=80)

    assert report["unexpected_errors"] == 0, "F1 재발: tmp 파일 경합으로 append가 실패했다"
    assert report["stale_rejected"] > 0, "경쟁이 일어나지 않았다 — stale 거절 경로가 검증되지 않음"
    assert len(report["success_ids"]) == 4 * 8, "bounded retry 로 요청한 성공 수를 채워야 한다"

    # CAS 계약: 성공 집합 == 저장 집합, 거절 집합과 교집합 없음.
    assert sorted(report["stored_view_ids"]) == sorted(report["success_ids"])
    assert sorted(report["original_ids"]) == sorted(report["success_ids"])
    assert set(report["rejected_ids"]).isdisjoint(report["stored_view_ids"])
    assert set(report["rejected_ids"]).isdisjoint(report["original_ids"])
    assert report["revision"] == len(report["success_ids"])
    # cap0 이므로 압축은 일어나지 않는다(이 시험이 압축을 섞지 않는다는 증거).
    assert report["compaction_generations"] == 0
    assert report["view_count"] == len(report["success_ids"])


def test_cap0_stale_loser_gets_explicit_conflict_not_silent_success(tmp_path: Path) -> None:
    """F2 보조: stale CAS 는 StaleConversationRevisionError 로 거절된다(위장 금지)."""
    from antigravity_k.engine.conversation_store import (
        ConversationStore,
        StaleConversationRevisionError,
    )

    os.environ[CAP_ENV] = "0"
    store = ConversationStore(tmp_path / "cas")
    store.append(project_id="p", conversation_id="c", expected_revision=0, role="user", content="seed")
    store.append(project_id="p", conversation_id="c", expected_revision=1, role="user", content="second")

    with pytest.raises(StaleConversationRevisionError) as excinfo:
        store.append(project_id="p", conversation_id="c", expected_revision=0, role="user", content="stale")
    assert excinfo.value.context["current_revision"] == 2
    assert len(store.original_history(project_id="p", conversation_id="c")) == 2


# ── 2) cap64: 제품 기본값에서 결정적 압축 검증 ──────────────────────────


def test_cap64_sequential_123_appends_compact_twice_without_loss(tmp_path: Path) -> None:
    """결정적 123 append: 두 번 압축이 반드시 발생하고 원본/ revision 은 손실 0."""
    from antigravity_k.engine.conversation_store import ConversationStore
    from antigravity_k.engine.summary_memory import is_store_generated_summary

    os.environ[CAP_ENV] = str(PRODUCT_CAP)
    store = ConversationStore(tmp_path / "cap64")
    expected_ids: list[str] = []
    for i in range(REQUIRED_SUCCESSES):
        message_id = f"seq-{i:03d}"
        store.append(
            project_id="proj",
            conversation_id="conv",
            expected_revision=i,
            role="user" if i % 2 == 0 else "assistant",
            content=f"turn-{i}",
            message_id=message_id,
        )
        expected_ids.append(message_id)

    record = store.get(project_id="proj", conversation_id="conv")
    assert record is not None
    originals = store.original_history(project_id="proj", conversation_id="conv")

    # 압축 계약(유실이 아님을 먼저 증명한다).
    assert record.memory.generation >= 2, f"123 append 는 두 번 압축해야 한다: {record.memory.generation}"
    assert len(record.memory.summarized_ranges) >= 2
    assert is_store_generated_summary(record.summary or "")
    assert len(record.messages) <= PRODUCT_CAP

    # 유실 계약(원본은 전부 남는다).
    assert record.revision == REQUIRED_SUCCESSES
    assert [str(m.get("id")) for m in originals] == expected_ids
    assert [str(m.get("content")) for m in originals] == [f"turn-{i}" for i in range(REQUIRED_SUCCESSES)]


def test_cap64_multiprocess_distinguishes_loss_from_compaction(tmp_path: Path) -> None:
    """경쟁 + 제품 cap64: 성공 ≥123, 원본 유실 0, 압축 발생을 별도 결과로 식별."""
    report = _run_race(
        tmp_path / "cap64-race",
        soft_max=PRODUCT_CAP,
        workers=6,
        turns=25,
        max_attempts=25 * 30,
    )

    assert report["unexpected_errors"] == 0, "F1 재발: tmp 파일 경합으로 append가 실패했다"
    successes = report["success_ids"]
    assert len(successes) >= REQUIRED_SUCCESSES, f"카드 하한 미달: {len(successes)}"

    # (a) CAS 유실은 0: 성공한 id 는 전부 원본에 남아 있고, 거절 id 는 남지 않는다.
    assert sorted(report["original_ids"]) == sorted(successes)
    assert set(report["rejected_ids"]).isdisjoint(report["original_ids"])
    assert report["revision"] == len(successes)

    # (b) 압축은 별도 결과다: view 는 bounded 이고 압축 세대가 관측된다.
    assert report["view_count"] <= PRODUCT_CAP
    assert report["compaction_generations"] >= 1
    assert report["view_count"] < len(successes), "압축이 실제로 view 를 줄였어야 한다"


# ── 3) 고정 seed 10회 반복 ──────────────────────────────────────────────


@pytest.mark.parametrize("seed", list(range(10)))
def test_seed_fixed_repetition_keeps_invariants(tmp_path: Path, seed: int) -> None:
    """고정 seed 10회 반복에서 cap64 불변식이 동일하게 유지된다."""
    from antigravity_k.engine.conversation_store import ConversationStore
    from antigravity_k.engine.summary_memory import is_store_generated_summary

    os.environ[CAP_ENV] = str(PRODUCT_CAP)
    rng = random.Random(seed)
    store = ConversationStore(tmp_path / f"seed-{seed}")
    expected_ids: list[str] = []
    for i in range(REQUIRED_SUCCESSES):
        message_id = f"s{seed}-{i:03d}"
        store.append(
            project_id="proj",
            conversation_id="conv",
            expected_revision=i,
            # 첫 턴은 user 여야 한다: NX-01 계약상 제약은 user 메시지만 만들 수 있다.
            role="user" if i == 0 else rng.choice(["user", "assistant", "tool"]),  # type: ignore[arg-type]
            content=CONSTRAINT_TEXT if i == 0 else f"turn-{i}-{rng.randrange(10**6)}",
            message_id=message_id,
        )
        expected_ids.append(message_id)

    record = store.get(project_id="proj", conversation_id="conv")
    assert record is not None
    originals = store.original_history(project_id="proj", conversation_id="conv")

    assert record.revision == REQUIRED_SUCCESSES
    assert [str(m.get("id")) for m in originals] == expected_ids
    assert len(record.messages) <= PRODUCT_CAP
    assert record.memory.generation >= 2
    assert is_store_generated_summary(record.summary or "")
    # SC-6 의미 보존: 압축을 두 번 넘겨도 초기 제약이 남아 있어야 한다.
    assert any(c.text == CONSTRAINT_TEXT for c in record.memory.active_constraints())
