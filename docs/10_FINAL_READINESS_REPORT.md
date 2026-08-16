# 10 Final Readiness Report

## 결론

현재 Antigravity-K는 **로컬 중심 에이전트 기능 검증/베타 준비 단계**다. qwen3.6 local-first, tool permission, CoV, QualityGate 수정 재생성, RAG provenance, durable task state, web result quality contract, chat/task/slash/CLI/MAX/multiplexer의 AgentRuntime 연결, memory compliance contract는 실제 코드와 테스트로 확인됐다. 최신 simple 2-case × 2 repeats와 frontier 5-case × 2 repeats 모두 `excellent` 안정성을 확인했고 전체 basedpyright hard gate도 `0 errors`로 통과했지만, live 검색 recall/근거 정확도와 운영 rehearsal이 남아 있어 첨부 요구사항의 “상용서비스 수준” 최종 조건은 아직 충족되지 않았다.

## 요구조건별 판정

| 조건 | 판정 | 근거/부족한 증거 |
|---|---|---|
| 표준 설치·빌드·실행 | [~] | wheel/sdist build와 서버 smoke는 통과했지만 uv/lock과 clean machine 재현 추가 필요 |
| 핵심 검색 자동화 | [~] | adapter/quality contract와 graded 2-case/확장 6-case fixture가 통과했고 precision은 개선됐지만 provider 장애와 live recall/case coverage가 부족 |
| 치명적 보안 취약점 없음 | [~] | permission/URL guard와 41개 guarded egress inventory, robots/crawl-delay, legal terms audit/enforce policy가 존재하지만 배포별 attestation/policy file과 DNS/secret/dep audit rehearsal 필요 |
| 검증 가능한 출처 | [x] | source id/citation/provenance 구조 |
| 답변-근거 연결 | [~] | COV_VERIFY가 검색 context의 untrusted evidence를 복원해 unsupported/unknown/conflict citation과 검증기 예외를 fail-closed로 처리한다. controlled 및 cache-allowed 실제 DuckDuckGo evidence grounding은 통과했지만 forced-refresh provider 안정성·최신성·다국어 sample은 부족 |
| 중복/스팸 제거 | [~] | canonical dedupe/domain diversity, spam classifier 미완료 |
| 최신성 반영 | [~] | category TTL, publish/update freshness 미완료 |
| 외부 API 부분 장애 격리 | [x] | multi-provider fallback과 empty result contract |
| 검색 품질 목표 충족 | [~] | configured self-hosted authority-rescue plus Qwen source-hint run은 `error_count=0`, 6-case P@3 0.389/Recall@3 0.667/MRR 0.917/nDCG@3 0.741로 개선됐지만 provider availability와 load P95 1805.8ms는 여전히 미달 |
| 운영 로그/알림/롤백 | [~] | audit/checkpoint/Vault와 task 실패·취소 snapshot rollback, provider cooldown/load benchmark, stale-cache marker는 구현됐고 alert/restore rehearsal 부족 |
| 최신 문서 | [x] | 01~10 문서와 project diagnostic report 추가 |
| 위험 투명성 | [x] | 본 보고서와 security review에 미해결 항목 기록 |

## 출시 차단 항목

1. 배포별 이용약관/법적 attestation policy file을 채우고 `enforce` 모드로 전환한 증거와 dependency/secret audit 실행 증거
2. live provider 검색 recall 개선과 확장 human-labeled golden set의 healthy-provider 실행. 현재 configured self-hosted baseline은 availability만 통과하고 6-case relevance와 P95 tail은 미달
3. 실제 provider evidence를 넣은 live Qwen claim-level benchmark의 forced-refresh availability, 반복 분산, 최신성, 다국어 conflict presentation
4. shell tool, Git, PageScraper-backed web fetch, external-brain API와 `/api/agent/tools/shell/run`은 canonical permission 경계로 통합됨. shell은 project cwd/timeout/output quota와 fail-closed SandboxRunner를 사용하고 task rollback도 연결됐으며 41개 HTTP egress call site가 공통 runtime policy로 guarded됨
5. memory scope/delete/redaction 계약: provider/durable export-redact-retention과 Vault raw-asset exclusion/redacted opt-in은 완료됐고, 원문 asset 삭제/변경 consent flow가 남음
6. 전체 basedpyright hard gate는 `src` `0 errors`로 통과했다. 다만 healthy-provider P95/P99 baseline, 장시간 장애 복구 rehearsal, 저장소 전체 Ruff 712 legacy/style findings 정리가 남아 있다.
7. Qwen simple/frontier 대표 suite의 범위를 넓히고, long-horizon 및 live grounding에서도 반복 실행 분산과 `excellent` 비율을 안정적으로 유지하는 증거

## 다음 승인 조건

위 차단 항목마다 재현 가능한 테스트, 실행 로그, rollback 절차가 추가되고, 전체 suite와 API/browser E2E가 clean하게 통과한 뒤에만 베타 서비스 범위를 확대한다. 현재 전체 suite와 API E2E는 통과했지만 live relevance, healthy load baseline, 배포별 legal attestation, live claim sample이 남아 있으므로 개인 로컬/개발 환경의 제한된 사용으로 유지한다.
