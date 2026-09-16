---
title: NX-02 before (HEAD ffb0ebb3, view-only conversation storage)
created: 2026-09-16
tags: [nx-02, before, evidence]
---

# NX-02 before — 기준선에서 확인한 결함

측정 트리: `/tmp/nx01-before/src` (= `git show HEAD:src/...` 와 바이트 동일, 확인 명령 `commands.txt`).
드라이버: [`repro_nx02_view_only.py`](repro_nx02_view_only.py) — `PYTHONPATH` 로 검사 트리를 고르고,
`store_module` 경로를 보고서에 남겨 어느 트리를 쟀는지 스스로 증명한다.
원본 출력: [`before-run-output.json.txt`](before-run-output.json.txt) (exit 3 = 원본 복구 불가).

시나리오: 40턴 append → `compact(retain_tail=4)` → 읽기/파일 목록 확인.

| 관측 | before (HEAD) |
|---|---|
| client 가 읽는 history (`get().messages`) | 5건 (요약 1 + retained 4) — **view 가 곧 이력** |
| `turn-0` 이 남아 있는가 | **false** (원문 소실) |
| 원본 이력 조회 API | **없음** (`original_history` 속성 자체가 없음) |
| 복구 가능한 원문 수 | 0 |
| 저장 파일 | `v2/<sha>/<sha>.json` **한 개** (+`.cas.lock`) |
| journal | 없음 |

해석: 요약이 원문을 **대체**하므로 `GET /v1/conversations/{id}` 는 사용자가 입력한 이력이 아니라
모델에 보낼 압축 결과를 돌려준다. export/삭제 표면도 없어서 "원본과 view 를 함께 삭제" 계약을
적용할 대상 자체가 없었다([`caller-trace.txt`](caller-trace.txt) 의 코드 인용 참조).

전체 보고서:

```json
{
  "tree": "before-head",
  "store_module": "/private/tmp/nx01-before/src/antigravity_k/engine/conversation_store.py",
  "turns_written": 40,
  "view_message_count": 5,
  "view_has_turn_0": false,
  "view_is_bounded": true,
  "originals_api_present": false,
  "originals_message_count": 0,
  "originals_cover_every_turn": false,
  "original_history_recoverable": false,
  "journal_files": [],
  "storage_files": [".cas.lock", "v2/148de9c5.../2ec3e47d....json"],
  "compact_summary_present": true
}
```
