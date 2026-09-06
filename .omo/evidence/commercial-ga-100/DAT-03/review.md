# DAT-03 독립 리뷰 — r1 APPROVE

- **Reviewer:** dat_03_verify (구현자 dat_03_registry와 상이한 세션 — Freebuff/Claude 세션, 2026-09-06)
- **검증 대상:** `codex/dat-03-registry-atomic` @ `f61e06f` (+ `06eaa49` 문서)
- **Verdict:** **APPROVE** — 발견 결함 0건. 수용기준 4건 전부 독립 재현으로 확인.

## 검증 방법

1. **코드 리뷰**: `project_registry.py` 전체(415 lines) + `filesystem.py` API 연동부 + 구현자 테스트 6건
2. **증거 재현**: 신규 스위트 `test_project_registry_atomic.py` (6건) + `test_project_registry_api.py` (2건) + registry 소비자 스위트 (path_contracts / ctx01 / durable_memory_purge, 19건) 재실행 → 전부 통과
3. **수용기준 독립 재현** (구현자 테스트와 별개로 직접 스크립트 작성):
   - AC#1 다중 프로세스: 서브프로세스 2개 × 100개 add → **201개 존재** (200 + default) — PASS
   - AC#2 typed failure: `builtins.open`에 ENOSPC(28) 주입 → `RegistrySaveError` 발생 (조용한 성공 없음) — PASS
   - AC#3 corruption recovery: primary 절단 → `.bak`에서 복구 + `.corrupt-<ts>` 격리 보존 — PASS
   - AC#4 API/재시작 일치: `add_project` 반환 레코드 == 새 인스턴스 로드 상태 (이름/경로/tasks/active) — PASS (테스트 `test_api_response_matches_post_restart_state` 재실행)
4. **회귀 분석**: base `f61e06f~1`(`8cec36c`) throwaway worktree에서 동일 파일셋 전체 스위트 실행 → 실패 목록 **byte-identical** (21 = 21). 참고: 이전 세션에서 기록된 base 22건 중 `test_web_search_quality` 1건은 메인 리포지토리 리브랜드 커밋(`5098643`) 이후 환경에서 재검증 결과 통과로 변해 있었음 (troubleshooting 과정의 부수 효과). DAT-03 자체 회귀는 **0건**.
5. **품질**: ruff + mypy (구현 2파일) 클린.

## 코드 리뷰 상세

- **flock reload-modify-save**: 모든 변경 연산(`add_project`/`switch_project`/`remove_project`/`get_active_project`의 편의 저장)이 `<storage>.lock`의 `LOCK_EX` 아래 디스크 최신 상태를 재적용한 뒤 저장한다. AC#1의 200/200이 이 구조의 직접 결과.
- **atomic save**: temp(`.{name}.tmp-{pid}`) 기록 + `fsync(file)` + `fsync(parent dir)` + `os.replace`. AC#3 시나리오에서 primary 절단이 재현되지 않는 이유이기도 하다 (테스트는 외부에서 강제 절단).
- **backup rotation**: 정상 저장마다 직전 primary를 `.bak`으로 원자적 회전 → 복구 시 "직전 정상 상태" 보장. 마지막 1회 저장분은 손실될 수 있으나 이는 last-good-backup의 표준 의미론이며 구현자가 테스트 주석에 명시.
- **typed failure**: `RegistrySaveError(cause=OSError)` 체인 유지, `filesystem.py` create route는 500 fail-closed 변환. switch/delete route는 catch 없이 FastAPI 500으로 동일하게 fail-closed (명시적 처리는 없으나 동작 등가 — 개선 여지, 비차단).
- **호환성**: `ProjectRecord` 위치 인자 `__init__` + `to_dict`/`from_dict` 유지 확인 — `path_security.py`, `project_binding.py`, `git_api.py`, `filesystem.py` 소비자 전부 무영향 (소비자 스위트 19건 통과로 교차 검증).

## 비차단 관찰 (후속 제안)

1. `switch_project`/`delete_project` 라우트도 `RegistrySaveError`를 명시적으로 catch해 일관된 에러 응답 형식을 내는 것 고려 (현재는 프레임워크 기본 500 — fail-closed 동작은 동일).
2. `_RegistryFileLock.__enter__`의 `break` 직후 unreachable `self._fd = fd` 라인은 데드 코드 (주석으로 의도 문서화되어 있으나 제거 가능).
3. lock 타임아웃(30s) 초과 시 `RegistryLockTimeout`이 API에서 500으로 변환되는데, 사용자 관점 503(retryable)이 더 적절할 수 있음.

## 결론

수용기준 4건 + 계획 요구사항(typed failure / corruption 격리 보존) 모두 독립 재현으로 확인. 구현은 계획이 제시한 두 대안(flock+atomic vs SQLite) 중 전자를 채택했고 요구 수준을 충족한다. **r1 APPROVE** — 병합 후 DONE 마킹은 코디네이터 승인 절차에 따른다.
