---
title: Ssak-Ai GA-100 최종 독립 검토
reviewed_sha: 8794aaecabf5664a7ee560b104e0115d915aabb7
date: 2026-09-10
status: review-complete-request-changes
tags: [commercialization, final-review, security, evidence]
---

# Ssak-Ai GA-100 최종 검토

현재 SHA의 **상용화 100% / 출시 GO 승인은 보류해야 한다.** 구현량이나 테스트 개수 때문이 아니라, 실제 데이터 정합성·격리 결함과 필수 출시 증거의 누락이 확인됐다. 기존 작업 전체가 실패했다는 의미는 아니다. 아래 결함을 수정하고 동일한 최종 SHA에서 필수 게이트를 통과해야 한다.

검토 대상은 `8794aaecabf5664a7ee560b104e0115d915aabb7`이다. 기존 RC 승인 대상은 `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9`이며, 이후 17개 커밋·197개 파일의 변경에 실제 API·에이전트·대시보드 코드가 포함된다. 작성자와 수정자 구분 없이 현재 구현을 검토했다. 이번 검토에서는 제품 소스를 수정하거나 커밋하지 않았다.

## 우선순위별 발견 사항

| ID | 심각도 | 문제·발생 조건 | 근거 | 수정 완료 기준 |
|---|---|---|---|---|
| FR-01 | P1 | 인증된 `/api/agent/ask` 요청의 `test_code`를 호스트 Python/pytest에서 직접 실행하며 서버 환경변수까지 상속한다. 임시 cwd는 실행 격리가 아니다. | [agent_ask.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/routes/agent_ask.py:35), [unified_agent.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:209), 상세 `final-security.md` HIGH 1 | 모든 사용자·모델 코드 실행을 fail-closed sandbox로 통합하고 호스트 파일/환경/네트워크 접근 제한을 실행 테스트로 입증 |
| FR-02 | P1 | 셸 경로 검사에서 `$HOME`·`${HOME}` 확장이 통과한다. 실제 shell 실행 시 프로젝트 밖 경로로 확장될 수 있다. 정책 probe에서 allow 확인. | `src/antigravity_k/tools/tool_path.py:284`, `permission_gate.py:151`, `terminal_tools.py:118` | OS/sandbox 경계를 강제하거나 확장 없는 구조화 argv로 전환; 변수·리다이렉션·치환·symlink 공격 테스트 |
| FR-03 | P1 | AtomicTransactionEngine이 `../outside.py`를 허용해 프로젝트 밖 파일을 생성한다. 임시 폴더에서 실제 쓰기 재현. | `src/antigravity_k/engine/atomic_transaction_engine.py:50,80` | 읽기·쓰기·복구 전에 canonical root containment 검증; traversal/symlink 거부 및 기존 빈 파일 보존 |
| FR-04 | P1 | RSI 실패 복구가 `git checkout <snapshot> -- .`로 전체 트리를 되돌려 다른 에이전트·사용자의 변경까지 덮어쓸 수 있다. 정적 호출 경로 확인. | `src/antigravity_k/engine/rsi_sandbox.py:239,418` | 격리 worktree/transaction에서 mutation 소유 경로만 복원; 동시 변경·dirty 파일 보존 재현 |
| FR-05 | P1 | 여러 서버 worker가 같은 대화를 사용할 때 캐시가 갱신되지 않아 이전 history/revision을 읽고 오래된 expected_revision을 허용한다. 두 store 인스턴스로 재현. | `src/antigravity_k/engine/conversation_store.py:182,220,224,588`; `reproduce_conversation_store_stale_cache.output.txt` | 읽기·생성·CAS를 저장소 최신 상태 및 프로세스 간 lock과 일치시키고 cross-worker read/no-new-turn 회귀 테스트 추가 |
| FR-06 | P1 · 출시 검증 | RC 승인 SHA와 현재 코드가 다르며 클라우드 provider 실행이 없고, 요구된 8시간 soak 대신 60초 결과만 존재한다. | `final-goal.md` B1–B3 | 모든 수정이 포함된 한 SHA를 고정해 실제 cloud streaming/tool/cancel/error 및 28,800초 soak 수행 |
| FR-07 | P2 · 검증 코드 | Chroma 삭제 시나리오가 false 지표를 반환해도 성공 처리된다. 다른 문서가 검색되는 것을 삭제 실패로 보는 판정 방식도 부정확하다. 이것만으로 VectorStore 삭제 결함을 단정하지 않는다. | `scripts/val01_staging.py:40,195`; RC `rc01-val01.json:87–92` | 삭제 대상 source identity가 검색·저장소에서 제거됐음을 assert하고 실패 시 nonzero 결과를 기록 |
| FR-08 | P2 · 완료 기록 | DONE과 리뷰 대기 metadata가 공존하고, 실행용 체크리스트 mirror·지원표·승인 등록부·점수표가 현재 GA READY 주장과 다르다. | `final-context.md` B2–B5 | 실제 승인 결과를 확보한 뒤 공식/실행 문서 동기화; 미완료 승인·지원 범위를 사실대로 표시 |
| FR-10 | P2 · 설정/패키징 | 저장소 기본 설정의 agent 항목이 번들 기본 설정에 없어 동일성 테스트가 실패한다. Root가 별도 재현했으며 stale site-packages 문제가 아니다. | `config.yaml:557`, `src/antigravity_k/config.yaml:556`, `tests/test_model_registry.py:66`; `logs/bundled-config-root-recheck.txt` | 기본 설정을 동기화하고 새 wheel 설치 환경에서 동일성·기동 검증 |
| FR-09 | P2 · 배포 증거 | wheel/sdist hash만으로는 내려받아 재검증할 산출물·provenance·benchmark·SHA 연결이 충분하지 않다. | `final-goal.md` B5 | 재현 가능한 산출물 위치와 checksum, source SHA, 환경, 명령, exit code를 manifest로 연결 |

P1은 출시 전 해소할 높은 영향의 결함/필수 게이트 실패, P2는 검증 신뢰도와 출시 기록 정합성 문제다. 코드 크기나 구현 상수에 결합된 테스트 등 유지보수 지적은 `final-quality.md`에 별도로 남겼으며 그 자체를 상용화 불가의 핵심 근거로 삼지 않았다.

## 프로젝트 폴더와 컨텍스트 압축

- QA 실행자는 브라우저 프로젝트 전환 후 active context/localStorage 일치와 HTTP 200을 관찰했다고 보고했다. 화면 캡처는 보존됐으나 원본 HTTP action log가 누락돼 재현 증거는 부분적이다. 선택 폴더의 실제 파일 내용이 새 요청의 provider prompt까지 전달되는 전체 경로는 이번 리뷰에서 입증하지 못했다. 경로 격리는 FR-02/03 때문에 승인할 수 없다.
- QA 실행자는 브라우저에서 압축 API를 직접 호출해 메시지 8→4, revision 8→9, 추정 토큰 480→276, stale revision 409를 관찰했다고 보고했다. 이는 압축 UI 버튼·자동 압축 트리거·provider 종단간 성공을 뜻하지 않는다. 원본 응답 로그 누락으로 수치는 실행자 보고 수준의 증거이며 스크린샷만으로 확증하지 않는다.
- 대화 저장·최종 prompt 예산·압축 관측성 관련 34개 테스트는 통과했다. 다만 FR-05의 worker 간 오래된 대화 사용 문제는 남아 있어, 서버가 최신 대화를 기준으로 압축/요청한다는 전체 계약은 미완료다.
- 압축 알고리즘 자체가 전부 실패한다거나 모든 프로젝트 파일을 읽지 못한다고 단정하지 않는다. 테스트 통과 범위, 실제 브라우저 관찰, 실 provider 종단간 미검증을 구분한다.

## 독립 검토 결과

| 검토 영역 | 판정 | 현재 SHA 증거 |
|---|---|---|
| 목표·수용 기준 | FAIL | [final-goal.md](final-goal.md) |
| 실행 QA / 런타임 감사 | FAIL · 브라우저 원본 로그 일부 누락 | [final-qa.md](final-qa.md) |
| 코드 품질·대화 정합성 | FAIL | [final-quality.md](final-quality.md) |
| 보안 | FAIL | [final-security.md](final-security.md) |
| 문서·승인·증거 정합성 | FAIL | [final-context.md](final-context.md) |

대시보드 typecheck·build 통과, 70개 파일/750개 테스트 통과, lint 0 errors/30 warnings가 QA 실행자 로그 요약에 기록됐다. 백엔드 집중 테스트는 196 passed/1 failed이며, 별도 model-registry 재검사는 30 passed/1 deselected다. 실패한 번들 설정 테스트는 root가 다시 실행해 1 failed를 확인하고 원문을 보존했다. 코드 품질 lane의 34개, 보안 lane의 15개 테스트가 통과했다. 중복 가능성이 있어 이를 고유 테스트 총수로 합산하지 않는다. 대화 캐시 결함의 재현 명령은 `uv run python docs/qa/2026-09-10/reproduce_conversation_store_stale_cache.py`이며 결과는 같은 폴더에 보존했다.

## 후속 작업 체크리스트

- [ ] FR-01: host 직접 실행 제거 및 sandbox 격리 공격 시나리오 검증
- [ ] FR-02: shell 확장 우회 차단 및 프로젝트 경계 강제
- [ ] FR-03: transaction root containment, symlink, 빈 파일 rollback 검증
- [ ] FR-04: mutation 단위 rollback과 동시 사용자 변경 보존 검증
- [ ] FR-05: cross-worker 최신 대화 읽기 및 revision CAS 검증
- [ ] FR-07: Chroma 삭제 검증기의 false-green 제거
- [ ] FR-10: root/bundled 기본 설정 일치 및 신규 패키지 설치 확인
- [ ] FR-08: 미완료 독립 리뷰·지원/개인정보/라이선스 승인 상태를 해소하고 모든 문서 동기화
- [ ] FR-06/09: 최종 SHA 고정 후 clean 환경 전체 gate, 실제 local/cloud provider, 8시간 soak, 복구·배포 산출물 검증
- [ ] 선택 폴더 내 고유 sentinel 파일이 실제 새 요청의 provider prompt에 반영되는 시나리오 및 자동/수동 압축 UI 종단간 검증; 원본 요청/응답·스크린샷 보존
- [ ] 위 SHA에 대해 코드·보안·수동 QA·출시 판정을 다시 수행하고 모두 승인된 경우에만 GA GO 표시

## 범위와 한계

실제 cloud 호출·8시간 soak·전 플랫폼/전 provider 검증은 이번 최종 리뷰에서 새로 수행하지 않았다. 누락은 성공으로 대체하지 않았다. 저장된 과거 Ollama/Chroma/MLX 측정은 구현 진전의 근거로 인정하되 현재 SHA 전체 출시 승인으로 확장하지 않는다. 기존 점수표의 53은 과거 기준값이며 이번 현재 점수로 재사용하지 않고, 새 숫자도 임의 산정하지 않는다.

시작 시 `vault_data` submodule에 기존 변경이 있었으며 건드리지 않았다. 그 변경 자체를 제품 결함으로 취급하지 않는다. 리뷰 산출물이 후보 커밋 뒤에 저장되는 것은 정상일 수 있으며, 문제는 기록 시점이 아니라 산출물의 source SHA·재현성·필수 검증 연결 부족이다.

종합 판정은 **REVIEW FAILED / REQUEST CHANGES**다. 다섯 검토 영역의 결과를 수집했으며 QA의 원본 브라우저 로그 보완은 완료되지 않았다. 새 리뷰가 생성됐다는 사실은 기존 검증 누락을 닫거나 FAIL을 승인으로 바꾸지 않는다.


## 후속 실행 문서

2026-09-10 사용자 요청으로 이 결과에 대응하는 [상세 개선 개발계획서](../../14_FINAL_REVIEW_REMEDIATION_PLAN.md)와 [실행 체크리스트](../../15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md)를 작성했다. 다음 구현자는 RP-00부터 시작한다. 문서 작성만으로 본 보고서의 결함이나 미검증 항목이 해소된 것은 아니다.
