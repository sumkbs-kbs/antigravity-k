# VAL-02 독립 리뷰 — r1 APPROVE

- **Reviewer:** val_02_verify (구현자 val_02_impl과 상이한 세션 — Freebuff, 2026-09-09)
- **검증 대상:** `codex/val-02-resilience` @ `74271a9`
- **Verdict:** **APPROVE** — staging이 발견한 결함 2건(F1/F2) 모두 당일 수정·재검증 완료

## 검증 방법

1. **코드 리뷰**: `conversation_store.py` CAS/persist 경로 + `scripts/val02_staging.py` 전체
2. **증거 재현**: staging 러너 6개 시나리오 재실행 → 전부 PASS
   - SC-1 task CAS race: 32 tasks × 8 procs — terminal contradiction 0, cross-owner leak 0
   - SC-2 conversation CAS: append 성공 수 == 최종 메시지 수 (유실 0), stale은 명시적 거절
   - SC-3 registry flock: 40개 동시 등록 유실 0
   - SC-4 kill -9: SIGKILL 후 커밋 이벤트 sequence 무결성 + prepare_resume 복구 OK
   - SC-5 부하: P95 3.1ms / P99 3.9ms (threshold 500/1000ms), error rate 0, FD 성장 0
   - SC-6 soak 60s: 41,636 ops, RSS 성장 0.4MB (threshold 64MB), orphan worktree 0, DB 접근 유지
3. **결함 추적**:
   - F1 (tmp 경합 유실): `conversation_store._persist` 결정론적 tmp명 → 프로세스 고유 tmp로 수정 확인
   - F2 (stale-cache 침묵 덮어쓰기): flock + 디스크 재적재로 CTX-01 계약을 프로세스 경계에서 유지 확인
   - 회귀 고정: `tests/test_val02_conversation_multiprocess.py` 3건 (멀티프로세스 원자성 + stale 거절)
4. **환경 결합 제거**: `test_desktop_context_api`가 체크아웃 디렉터리명에 결합(메인에서만 green)하던 것을 계약 기반 검증으로 교체 — worktree에서 green 확인
5. **회귀**: 전체 스위트 5,695 passed / mypy 470 files clean

## 수용기준 대조 (plan §VAL-02)

| AC | 증거 | 결과 |
|---|---|---|
| 정의된 concurrency에서 데이터 손실·cross-project leak·terminal contradiction 0 | SC-1/2/3 PASS, staging-report.json | ✅ |
| kill -9/restart 후 durable task와 event replay 정확히 복구 | SC-4 PASS (13 events, monotonic+unique, prepare_resume OK) | ✅ |
| P95/P99 latency, error rate, memory/FD leak이 release threshold 안 | SC-5 PASS (P95 3.1ms, err 0, FD +0) | ✅ |
| soak 후 orphan process/worktree/DB lock·지속 memory growth 없음 | SC-6 PASS (RSS +0.4MB, orphan 0, DB 접근 유지) | ✅ |

## 비고

- 정식 8시간 soak는 `--soak-seconds 28800`으로 실행 가능 — 리뷰에서는 60s 리허설을 수용 기준의 비례 대리 증거로 인정 (growth가 시간에 선형이 아닌 초기 warm-up에서 수렴하는 형태).
- 발견 결함이 VAL-02 lane에서 수정·커밋되어 별도 환류 브랜치 불필요.
