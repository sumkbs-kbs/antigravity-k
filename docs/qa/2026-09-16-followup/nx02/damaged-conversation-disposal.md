# NX-02 후속 — 손상된 대화의 **격리·폐기** 운영 절차 (결정 브리프)

작성: 2026-09-16. 후보 지문 `157311cf…`(동결 트리). 근거: `repro_corrupt_disposal.py` ·
`corrupt-disposal-output.txt`(이 디렉터리, 실제 실행 출력).

## 1. 왜 이 문서가 필요한가

`docs/09_OPERATION_GUIDE.md` 는 "손상 대화 폐기 경로 없음"을 **기대하지 말 것** 목록에 넣고,
소유자를 미정으로 남겨 두었다. 그런데 이건 "없으면 불편한 기능"이 아니라 **저장소가 손상됐을 때
운영자가 대화 하나를 정리할 방법이 없다**는 뜻이다. 실제로 어떤 일이 나는지 실행으로 확인했다.

## 2. 실측 (추측 아님)

| 상황 | 읽기 (`get`) | 관측 (`history_state`) | **제품의 delete** |
|---|---|---|---|
| view JSON 손상 | `ConversationIntegrityError` (json_decode) | `ConversationIntegrityError` | **`ConversationIntegrityError` — 거절** |
| journal 중간 줄 손상 | `ConversationHistoryCorruptError`(줄·오프셋 동반) | 가능 | **`ConversationHistoryCorruptError` — 거절** |

즉 `delete_conversation` 은 `_authoritative_record()` 로 **journal 을 먼저 읽어** 삭제 이벤트를
커밋하므로, 이력이 손상돼 있으면 **삭제 자체가 성립하지 않는다**. 이건 버그가 아니라
"원본을 조용히 버리지 않는다"(ADR-DAT-02)의 안전 측 동작이다. 문제는 **비상구가 없다**는 것:
손상된 대화는 읽지도 지우지도 못하고, 그 파일은 디스크에 계속 남아 `store_usage()` 에 계속 잡힌다.

## 3. 선택지

| # | 안 | 내용 | 비용 | 위험 |
|---|---|---|---|---|
| **A** | 제품에 명시 폐기 경로 | 예: `DELETE /conversations/{id}?force=1`(권한·감사 로그 필수) | 코드·계약·시험 + ADR 수정 | "조용한 삭제 금지"의 예외를 제품에 영구히 만든다. 감사 없이 쓰이면 데이터 손실 경로가 된다 |
| **B** | **운영자 파일 격리 절차**(권고) | 서비스 정지 → 손상 파일 2개를 **저장소 밖**으로 이동 → 삭제 표식 기록 → 재기동 | 코딩 0 (기존 라이브러리 1줄 사용) | 손대는 사람이 경로를 알아야 한다(§4 로 해결) |
| **C** | 복구 우선 | 손상 구간을 버리고 이력 재구성 | 코딩 필요 | **부분 복구는 "원본 보존" 계약을 깨뜨릴 수 있다** — 버린 구간을 복구로 위장하게 됨. 지금 자동 처리되는 것은 *truncated tail*(잘린 꼬리)뿐이다 |

**권고: B 를 지금 문서화하고, A 는 오너 판정 사항으로 남긴다.** C 의 유일하게 안전한 부분
(잘린 꼬리 정리)는 이미 `rewrite_without_truncated_tail()` 로 자동이다.

## 4. 절차 (B) — 그대로 실행 가능

```bash
# 0) 서비스 정지(쓰는 프로세스가 없어야 한다). 저장소 기본 위치:
#    ~/.antigravity/conversations   (env AGK_CONVERSATION_STORE_DIR 로 바뀔 수 있다)

# 1) 손상된 대화의 파일 3개 경로를 **id 로부터** 계산한다(경로를 추측하지 않는다)
STORAGE=~/.antigravity/conversations
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from pathlib import Path
from antigravity_k.engine.conversation_journal import deletion_marker_path
from antigravity_k.engine.conversation_store import conversation_storage_relative_path
rel = Path(conversation_storage_relative_path('$PROJECT_ID', '$CONVERSATION_ID'))
print('$STORAGE'/rel); print(('$STORAGE'/rel).with_suffix('.jsonl')); print('$STORAGE'/deletion_marker_path(rel))
"
#   → v2/<sha256(project)>/<sha256(conversation)>.json / .jsonl / .deleted.json

# 2) 격리 디렉터리는 **저장소 루트 밖**에 만든다(⚠ §5 — 안에 두면 전체가 죽는다)
Q=~/.antigravity/quarantine/$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$Q"
mv <view.json> <journal.jsonl> "$Q"/        # 바이트를 보존한다(사후 분석용)

# 3) 삭제 표식을 남긴다 → 제품 의미론상 '삭제됨'이 되고 **id 재사용이 금지된다**
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from pathlib import Path
from antigravity_k.engine.conversation_journal import write_deletion_marker
from antigravity_k.engine.conversation_store import conversation_storage_relative_path
rel = Path(conversation_storage_relative_path('$PROJECT_ID','$CONVERSATION_ID'))
write_deletion_marker(Path('$STORAGE')/rel, project_id='$PROJECT_ID', conversation_id='$CONVERSATION_ID', seq=0, revision=0)
"
# 4) 서비스 기동 → 확인
#    history_state: exists=False · deleted=True · content_erased=True
#    append(expected_revision=0) → ConversationNotFoundError("…id is not reused")
# 5) 격리본은 정해 둔 보존 기간만큼 남기고, 폐기는 별도 승인으로(파괴는 사람이 결정한다)
```

실측 결과(§2 의 3번 케이스): 격리 이동 + 표식 뒤 `history_state` 는
`{'exists': False, 'deleted': True, 'content_erased': True, …}`,
`get()` 은 `None`, id 재생성 시도는 `ConversationNotFoundError` — **원본 2개 파일은 격리
디렉터리에 그대로 남는다**(바이트 보존).

### 실데이터 사본 리허설 (2026-09-16, `rehearse_real_store_quarantine.py`)

합성 프로브만으로는 "실제 저장소에서도 그런가"를 말할 수 없으므로, 사용자 저장소
(`~/.antigravity/conversations`, 레거시 레이아웃 3개 대화)를 **복사본에서만** 만져 리허설했다:

1. 원본 전수 sha256 → `cp` 사본이 동일함을 확인 → 종료 시 원본 해시 재확인 **불변**(4개 파일)
2. 사본에서 CR-01 migration: `--dry-run` → `--apply --backup-dir`(`journal_backfilled: 3`) → `--verify-only`(`verified`, 실패 0)
3. 사본에서 대화 1건 손상 → 읽기 거절(`ConversationIntegrityError`) → **본 절차 적용** →
   대상 `deleted=True` · `get()=None` · id 재사용 금지(`ConversationNotFoundError`) · **형제 대화 정상** · 격리본 보존
4. 음성 대조군 A/B(위 표)로 함정의 조건을 확정

부수 관측(마이그레이션 도구가 이미 문서화한 동작): 백필 직후 3개 view 는 모두
`journal_seq=0` / journal tail `seq=1` 이고, **첫 읽기에서 view 가 journal 로부터 재생성**된다
(로그: `Conversation view rebuilt from journal … view_seq=0 journal_seq=1`). 도구의
`_advanced_view_match` 가 이 상태를 정당하다고 명시하고 `--verify-only` 도 통과한다 — 데이터 손실은
없고, 비용은 대화당 첫 읽기 1회의 replay 다.

## 5. ⚠ 함정 — 격리 위치는 **저장소 루트 밖**이어야 한다 (조건을 정확히)

`ConversationStore` 는 저장소 루트에 v2 아닌 `*.json` 이 보이면 **미완료 마이그레이션으로 간주해
fail-closed** 한다(`legacy_storage_paths()` → `storage_layout_state()`).

**처음에는 이 함정을 무조건적이라고 적었는데, 실데이터 사본 리허설에서 재현되지 않아 조건을 나눠
다시 생성:** `storage_layout_state()` 는 레거시 파일이 있어도 **마이그레이션 완료 표식
(`migration_v2.json`)이 있으면 `v2` 를 돌려준다**. 따라서:

| 상태 | 루트 안에 격리 디렉터리를 두면 | 근거 |
|---|---|---|
| **표식 없음**(마이그레이션 전) | `legacy_requires_migration` → **무관한 정상 대화까지** `ConversationStorageMigrationRequiredError` | 실측 A(실데이터 사본) · 합성 프로브 케이스 4 |
| **표식 있음**(마이그레이션 후) | 레이아웃은 `v2` 유지 — 읽기도 `--verify-only` 도 통과 | 실측 B(실데이터 사본) |

그래서 규칙은 여전히 같지만 이유가 정확해졌다: 마이그레이션 **전** 저장소에서는 치명적이고(가장 위험한
시점), 후에는 "조용한 오염"에 그친다 — 잉여 파일이 저장소 스캔에 잡혀 `store_usage()` 의 사용량에
들어간다. 격리 위치는 **항상** 저장소 루트 밖(`~/.antigravity/quarantine/<timestamp>/`)으로 둔다.
운영 문서에도 이 조건을 명시해 적었다(`docs/09`).

## 6. 남긴 결정 (소유자 지정 필요)

1. **소유자**: 손상 대화의 격리·폐기 절차 소유자(현재 미정) — 문서화는 했지만 **연습·승인은 사람**.
2. **A 안 채택 여부**: 제품에 명시 폐기 경로를 둘 것인가. 둔다면 권한·감사 로그·"삭제는 복구
   불가" 통지가 계약에 함께 들어가야 한다.
3. **격리본 보존 기간**: 파괴 시점·보존 기간(증거 보존과 개인정보 최소화의 충돌).
4. **리허설**: 이 절차를 실제 저장소 복사본에서 한 번 돌려보는 것(현재 상태: 문서 + 프로브 실행까지).
