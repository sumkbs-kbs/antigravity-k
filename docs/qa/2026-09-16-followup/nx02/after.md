---
title: NX-02 after (작업 트리, journal 원본 + materialized view)
created: 2026-09-16
tags: [nx-02, after, evidence]
---

# NX-02 after — 같은 시나리오의 관측값

측정 트리: 작업 트리(`src/…/conversation_store.py`, 미커밋). 드라이버와 시나리오는 `before.md` 와 동일하다.
원본 출력: [`after-run-output.json.txt`](after-run-output.json.txt) (exit 0).

| 관측 | after (작업 트리) |
|---|---|
| client 가 읽는 history (`get().messages`) | 5건 — **기존 GET 응답 형태 불변(호환)** |
| `turn-0` 이 남아 있는가 (view) | false (view 는 bounded) |
| 원본 이력 조회 API | `store.original_history()`, `GET /v1/conversations/{id}/history` |
| 복구 가능한 원문 수 | **40 / 40** |
| 저장 파일 | `v2/<sha>/<sha>.json`(view) + `v2/<sha>/<sha>.jsonl`(journal) |
| journal | `base`/`append`/`compact`/`fork`/`delete` 이벤트, seq 1..N |

```json
{
  "tree": "after-working-tree",
  "store_module": "/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py",
  "turns_written": 40,
  "view_message_count": 5,
  "view_has_turn_0": false,
  "view_is_bounded": true,
  "originals_api_present": true,
  "originals_message_count": 40,
  "originals_cover_every_turn": true,
  "original_history_recoverable": true,
  "journal_files": ["v2/148de9c5.../2ec3e47d....jsonl"],
  "compact_summary_present": true
}
```

추가 증거(원본 손상·테일·삭제·경쟁)는 `tests/test_nx02_history_journal.py` 14건과
[`regression.txt`](regression.txt), 마이그레이션 3-모드 출력은 [`migration-report.txt`](migration-report.txt) 에 있다.

## 구현 계약(관측으로 확인된 것만)

- **commit 지점:** journal line + fsync. view 쓰기가 실패해도(`_persist` 예외) 다음 읽기에서
  journal replay 로 view 가 복구되고 원문은 남는다(시험 4).
- **1 append = 1 revision:** append 가 soft max 를 넘겨 압축을 동반해도 journal 이벤트는 1건,
  revision 도 1만 증가한다(시험 1: 1001 append → revision 1001).
- **originals 정의:** 요약 메시지(provenance=`summary`)는 view/`summary` 에만 속하고 originals 에는
  들어가지 않는다. 요약을 원문으로 재창작하지 않고, 요약을 원문 턴으로 제시하지도 않는다.
- **손상/테일:** 중간 손상 줄은 `ConversationHistoryCorruptError`(409, `journal_line`/`journal_offset`)
  로 올라오고 skip 하지 않는다. 마지막 잘린 줄은 미커밋 tail 로 보고·격리(`*.tail-recovery-*.bin`)된다.
- **삭제:** 같은 잠금에서 journal `delete` + 표식 + 파일 제거. 삭제 후 `get`/`original_history`/
  `export` 는 아무것도 반환하지 않고, 삭제된 id 는 재사용되지 않는다(시험 6·7).
- **journal 실패 매핑:** 손상 409 `conversation_history_corrupt`, IO/상위 schema 503
  `conversation_history_unavailable` (성공으로 감추지 않음).
