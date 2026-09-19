# NX-08 인계 — 영속화·복구의 잔여 의혹 재검증

상태: **REVIEW** (구현·시험 green, 독립 검토 미실시) — 2026-09-16
카드: `docs/18` §NX-08 / `docs/19` §NX-08. 선행: NX-02·NX-03(REVIEW). 후속: NX-09, NX-10.

## 1. 한 줄 요약

NX-03 이 넘긴 잔여 의혹 4건을 **실제로 죽이고·실패를 주입해서** 재측정했다. 5개 결함이
재현되었고(A1·A2·C1-crlf·C2-eof·D1) **모두 수정·재검증**했다. 남은 것은 외부 의존성
한계 1건(F2)과 조건을 만들 수 없어 미판정인 2건(F1·G1)이다.

## 2. 판정표 (before → after)

    before: {"CONFIRMED": 6, "NOT_REPRODUCED": 7, "INCONCLUSIVE": 2}   ← HEAD 추출본
    after:  {"CONFIRMED": 1, "NOT_REPRODUCED": 12, "INCONCLUSIVE": 2}  ← 작업 트리

| id | before | after | 결함 | 수정 |
|---|---|---|---|---|
| A1-fsync-failure | CONFIRMED | NOT_REPRODUCED | 이전 bytes 가 사라짐 | `write_text_atomically` |
| A2-crash-mid-write | CONFIRMED | NOT_REPRODUCED | 잘린 파일이 커밋 후보로 남음 | 같은 수정 |
| C1-crlf | CONFIRMED | NOT_REPRODUCED | CRLF frontmatter 가 본문으로 샘 | 구분자 `\r?` |
| C2-eof-no-newline | CONFIRMED | NOT_REPRODUCED | `ValueError` 로 읽기 실패 | `index` → `find` |
| D1-snapshot-restore | CONFIRMED | NOT_REPRODUCED | 복구가 `0600`→`0644` 완화 | 복구 후 mode 복원 |
| F2-foreign-host-stale-lock | CONFIRMED | **CONFIRMED** | 다른 호스트 lock 은 안 깨짐 | 외부 의존성 — 미해결(§5) |
| B1, C1-lf, C2-with-newline, C3×2, C4, E1 | NOT_REPRODUCED | NOT_REPRODUCED | — | 회귀 없음 |
| F1-nfs, G1-tombstone-gc | INCONCLUSIVE | INCONCLUSIVE | — | 조건 없음(§5) |

## 3. NX-03 잔여 의혹 4건의 결말

1. **tombstone 누적·GC 없음** → `G1 INCONCLUSIVE`. 심볼 검색으로 GC 경로 부재만 확인했다.
   정책(보존 기간·GC 트리거)은 제품 결정이라 **NX-03 후속/NX-08-F** 로 남긴다.
2. **NX-03 이전에 삭제된 세션의 stale writer 부활** → **재측정 대상 아님**. 표식이 없는
   과거 이력은 복구 불가이고, 지금 새로 만들 수도 없다(현재 코드는 삭제 시 표식을 남긴다).
   NX-03 이 이미 "구버전 삭제 이력은 복구 불가"로 기록했다.
3. **redact 경로의 무잠금 직접 덮어쓰기** → `E1 NOT_REPRODUCED`(lock enter/exit 1회 확인).
   다만 같은 경로가 **비원자적 `open("w")`** 를 쓰고 있어 A1/A2 결함을 그대로 물려받았다 —
   `write_text_atomically` 로 교체했고 `test_privacy_redact_*` 2건이 이를 지킨다.
4. **NFS 등 파일시스템별 flock/fsync 신뢰성** → `F1 INCONCLUSIVE` + `F2 CONFIRMED`.
   이 호스트에 NFS 가 없어 일반화하지 않는다. 대신 **다른 호스트가 남긴 lock** 은 로컬에서
   호스트명 위조로 코드 경로를 재현했고, filelock 3.29 가 깨지 않는다는 것을 확인했다.

## 4. 변경 파일

| 파일 | 변경 |
|---|---|
| `src/antigravity_k/engine/vault.py` | `write_text_atomically` 신설(+tmp 수거·권한 승계·dir fsync), `write_note` 적용, 구분자 `\r?`, 본문 `find`, 복구 후 mode 복원 |
| `src/antigravity_k/engine/vault_privacy.py` | `_apply_files` → `write_text_atomically` |
| `src/antigravity_k/engine/vault_privacy_git.py` | 복구 전 mode 기록 → 복구 후 복원 |
| `tests/test_nx08_vault_durability.py` | 신규 17건 |

`VaultCommitError` 를 새로 만들지 않았다 — `engine/vault_git.py` 에 이미 있는 타입을 그대로
쓴다(중복 정의 금지).

## 5. 남긴 것 (다음 에이전트가 이어받을 것)

* **F2 (CONFIRMED, 미해결)**: filelock 3.29 는 `hostname != socket.gethostname()` 이면 stale
  lock 을 깨지 않는다. 단일 호스트 배포에서는 발생하지 않는다. 공유 볼륨·다중 인스턴스로
  확장할 때 정책을 정해야 한다 — 후보: (a) lock 에 host/pid/시작시각을 남기고 나이 기반으로
  운영자가 판단, (b) 공유 FS 에서는 외부 lock(NFS-safe)로 교체, (c) 공유 FS 미지원을 지원표에
  명시. **현재 복구 절차는 `.git/.agk_vault.lock` 수동 제거**이며 드라이버가 이 절차의
  유효성(`outcome_after_manual_unlink=wrote`)을 관측했다.
* **F1 (INCONCLUSIVE)**: NFS/SMB 실마운트에서의 flock/fsync 는 이 환경에서 측정 불가.
* **G1 (INCONCLUSIVE)**: tombstone GC 정책 결정 필요(NX-03 후속).
* **미실시**: 커널 수준 전원 차단(드라이버는 `os.fsync` 치환으로 "정리 코드 없는 종료"를
  재현), Windows/NTFS 관측(제품 지원표 범위 밖).
* **독립 검토자 지정·판정** — 다른 카드와 동일하게 미배정(겸직) 상태다.

## 6. 다음 카드에 미치는 영향

* **NX-10 차단 여부**: 카드 규칙은 "확인된 데이터 손실은 수정·재검증 전 NX-10 을 막는다".
  A1/A2(데이터 손실)는 **수정·재검증 완료** — 차단 사유가 아니다. F2 는 단일 호스트
  배포에서 재현되지 않고, 다중 인스턴스 공유 볼륨을 쓰지 않는다면 잔여 위험으로 남는다
  (출시 판단 대상).
* **NX-09(사용자 동선)** 에 영향 없음 — vault 쓰기 경로의 **성공 결과는 바뀌지 않았고**
  (`test_vault*.py` 전부 green), 실패 시 이전 내용이 남는 쪽으로만 달라졌다.
* **NX-10(최종 후보)**: `vault.py` 는 후보 지문 대상 코드다 — 이 파일을 고친 뒤에는
  후보 SHA·지문을 다시 고정해야 한다(값은 `docs/20` 이 아니라 판정 카드 §5 가 소유).

## 7. 증거 지도

| 파일 | 내용 |
|---|---|
| `before-run-output.json` / `after-run-output.json` | 드라이버 stdout 전문(15개 probe 의 관측값) |
| `before.md` / `after.md` | 판정표와 수정 설명 |
| `regression.txt` | 계약 시험·좁은 회귀·전체 스위트 수치 |
| `commands.txt` | 그대로 복사해 재현하는 순서 |
| `repro_nx08_vault_persistence.py` | 드라이버(`--src` 로 잴 나무를 바꾼다) |
