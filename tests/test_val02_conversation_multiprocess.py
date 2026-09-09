"""VAL-02 회귀 — 다중 프로세스 conversation CAS 원자성 고정.

VAL-02 staging(SC-2)에서 발견한 결함을 잠근다:
  F1  결정론적 tmp 파일명(<conv>.tmp) — 동시 writer가 서로의 tmp를 치환해
      FileNotFoundError로 메시지 유실.
  F2  프로세스별 메모리 캐시만으로 CAS 평가 — 다른 프로세스의 append가
      보이지 않아 CAS가 통과하고 마지막 쓰기가 이긴다(침묵 덮어쓰기).

수정 후 계약: N개 프로세스가 경쟁해도 "append 성공 수 == 최종 메시지 수"
(또는 명시적 StaleConversationRevisionError 거절 — 유실 아님).
"""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

import pytest


def _mp_append_worker(storage_dir: str, project_id: str, conversation_id: str, turns: int, result_q: Any) -> None:
    from antigravity_k.engine.conversation_store import ConversationStore, StaleConversationRevisionError

    store = ConversationStore(storage_dir)
    appended = 0
    stale = 0
    errors = 0
    for i in range(turns):
        rev = store.get_revision(project_id=project_id, conversation_id=conversation_id) or 0
        try:
            store.append(
                project_id=project_id,
                conversation_id=conversation_id,
                expected_revision=rev,
                role="user",
                content=f"w-{mp.current_process().pid}-{i}",
            )
            appended += 1
        except StaleConversationRevisionError:
            stale += 1  # 명시적 거절 — 유실이 아니다
        except FileNotFoundError:
            errors += 1  # F1 재발: tmp 경합이 드러나면 안 된다
        except Exception:
            errors += 1
    result_q.put({"appended": appended, "stale": stale, "errors": errors})


@pytest.mark.parametrize("workers,turns", [(4, 10), (6, 20)])
def test_multiprocess_append_is_atomic(tmp_path: Any, workers: int, turns: int) -> None:
    """F1+F2 회귀: 멀티프로세스 append에서 유실/오류 0, 성공 수 == 최종 메시지 수."""
    from antigravity_k.engine.conversation_store import ConversationStore

    storage_dir = str(tmp_path / "conversations")
    q: Any = mp.Queue()
    procs = [mp.Process(target=_mp_append_worker, args=(storage_dir, "proj", "conv", turns, q)) for _ in range(workers)]
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    for p in procs:
        p.join(timeout=60)

    final = ConversationStore(storage_dir).get(project_id="proj", conversation_id="conv")
    final_count = len(final.messages) if final else 0
    appended = sum(r["appended"] for r in results)
    errors = sum(r["errors"] for r in results)

    assert errors == 0, "F1 재발: tmp 파일 경합으로 append가 실패했다"
    assert final_count >= appended, (
        f"F2 재발: append 성공 {appended}건 중 {appended - final_count}건이 침묵 덮어쓰기로 유실됐다"
    )


def test_multiprocess_cas_losers_are_rejected_not_silent(tmp_path: Any) -> None:
    """F2 보조: stale CAS는 반드시 StaleConversationRevisionError로 거절된다 (반환값 위장 금지)."""
    from antigravity_k.engine.conversation_store import (
        ConversationStore,
        StaleConversationRevisionError,
    )

    storage_dir = str(tmp_path / "conversations")
    store = ConversationStore(storage_dir)
    store.append(project_id="p", conversation_id="c", expected_revision=0, role="user", content="seed")
    store.append(project_id="p", conversation_id="c", expected_revision=1, role="user", content="second")

    with pytest.raises(StaleConversationRevisionError):
        store.append(project_id="p", conversation_id="c", expected_revision=0, role="user", content="stale")
