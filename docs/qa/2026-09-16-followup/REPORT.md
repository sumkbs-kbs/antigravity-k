---
title: Ssak-Ai 상용 완성도 정밀 검토 및 FlyWire 접목 타당성
date: 2026-09-15
tags: [review, commercial-readiness, reliability, flywire, research]
reviewed_head: ffb0ebb312b76d86742d3e4065628a9704f8268e
verdict: NO-GO
scope: current integrated checkout; all authors; analysis only
---

# Ssak-Ai 상용 완성도 정밀 검토 및 FlyWire 접목 타당성

## 1. 종합 결론

**현재 Ssak-Ai는 기능 폭과 안전장치가 상당히 발전한 개발·평가용 후보이다. 일반 고객에게 안정성을 약속하는 정식 상용 제품으로는 아직 NO-GO다.** 핵심 이유는 서명이나 문서 승인만 남아서가 아니다. 장기 대화의 요구사항 보존, 삭제한 세션의 재등장, 현재 통합 후보의 검증 일치성에 실제 공백이 있다.

기존 개선은 상당수 반영됐다. CAS(저장 버전을 비교하여 오래된 쓰기를 거부), 프로세스 잠금, 실패 시 접근 거부, 도구 승인, 설정 시크릿 분리, 오류 복구 UI, 오프라인 assets, 운영 지표, 출하 증거 관리까지 있다. 개인 스크립트 단계는 넘어섰다. 그러나 기능 존재·테스트 통과·출하 승인·고객 지원 가능성은 서로 다른 지표다.

**FlyWire 접목은 연구 실험으로 가능하다. 추천하는 순서는 기존 저장·기억 결함 해결 → 검색/전략 선택의 작은 실험 → 실제 연결 구조를 쓰는 축소 모듈 비교 실험이다. 전체 초파리 뇌를 기본 LLM 대체품으로 탑재하는 것은 현 단계에서 권하지 않는다.**

## 2. 검토 범위와 증거 수준

- 기준 HEAD: ffb0ebb312b76d86742d3e4065628a9704f8268e. 사용자·다른 에이전트·이번 검토 이전 작성자를 구분하지 않았다.
- Git 추적 인벤토리: 총 3,078개 경로, Markdown 739개, backend Python 484개, dashboard TS/TSX 251개. Markdown에는 프로젝트 문서뿐 아니라 bundled skills, 데이터·지식 문서, 과거 증거가 포함된다. docs/ 내 Markdown은 112개다.
- 전체 저장소를 검토 대상으로 삼고 구조 탐색, 문서 인벤토리, 요구사항/릴리스 증거 대조 후 위험이 큰 코드 경로를 정밀 검사했다. **모든 3,078개 파일을 줄마다 정독하거나 모든 기능을 실행했다는 뜻은 아니다.**
- 실제 확인: 그래프/원문 코드, 계획 11–17·GA/패키징/배포 문서, 과거 gate/soak 산출물, 실행 중 재soak의 읽기 전용 상태, 임시 저장소 재현, 좁은 회귀 테스트, 브라우저 PIN 잠금 화면.
- 미확인: 현재 HEAD 전체 required gate 재실행, 전체 인증 후 UI/모바일 동선, 실제 유료 provider 전체, 새 고객 기기 설치·업그레이드 완주, Kubernetes 장애 주입, 모든 선택 extra/GPU 기능, 현재 재soak 최종 결과.
- UI는 http://127.0.0.1:8000 에서 실제 PIN 잠금 화면이 렌더링됨을 확인했다. 인증 이후 전체 페이지·반응형·접근성을 현재 빌드에서 검증했다고 판정하지 않는다.
- 소스·설정·실제 비밀번호·vault·진행 중 soak는 수정하지 않았다. 초기 Git 상태의 vault_data 및 인증 백업 경로도 그대로 남겼다. 이 보고서는 저장소 밖에 저장했다.

증거 표기: **재현**=이번 세션에서 실제 실행, **정적 확인**=원문 분기/배선 확인, **과거 기록**=이전 후보의 산출물, **미검증**=증거 부족. 이 구분 없이 PASS를 합산하지 않는다.

## 3. 상용 제품과 비교하는 기준

비교 대상은 현재 ADR의 **로컬 우선·단일 운영자·self-hosted 단일 조직 제품**이다. 멀티테넌트 SaaS·기업 SSO·결제·Windows를 현 SKU의 필수 결함으로 계산하지 않았다. 다만 그 시장까지 진출하려면 별도 범위 확장이 필요하다.

상용 코딩 도구의 비교 축은 작업 실행, 사용자 승인, 변경 복원, 세션 지속성, 설치/업데이트, 장애 설명, 공급자·지원 범위의 일관성이다. Cursor는 에이전트 작업과 checkpoint 복원을, Claude Code는 권한 제어와 checkpoint를 명시적으로 제공한다. 이는 비교 축의 근거이며 양 제품이 결함이 없다는 의미는 아니다. [Cursor 공식 설명](https://cursor.com/docs/agent/overview), [Claude Code 동작 설명](https://code.claude.com/docs/en/how-claude-code-works)

아래 등급은 측정된 완성률이 아니다. **B=기능과 일부 검증이 있으나 통합 출하 근거 부족, C=고객 신뢰에 영향을 주는 공백 확인, D=출하 조건 미충족, 범위 밖=현 SKU 요구가 아님**이다. 근거 없는 90점/95% 수치를 만들지 않았다.

## 4. 항목별 완성도

| 항목 | 현재 수준 | 갖춘 부분 | 상용 대비 남은 차이 / 필요한 완료 증거 |
|---|---|---|---|
| 제품 목적·아키텍처 | B | local-first, 단일 운영자 경계, 실행 context와 모델 레지스트리 | 웹 operator와 새 desktop 패키지의 지원 계약 통합 |
| 모델 연결·선택 | B | Ollama/MLX/LM Studio 및 cloud profiles, fallback·load balance·cascading | provider별 실제 성공·오류·스트림 취소·재시작 검증을 현재 후보로 고정 |
| 코딩 에이전트 실행 | B | ReAct/도구 실행/계획·검증·적응, direct task 상태·재개 | 긴 실제 저장소 작업에서 종료·요구 충족·복구를 함께 평가 |
| Adaptive/집단지성 | B | 분류·다양성 probe·반복 수정·다중 모델 경로 | 추가 호출 비용 대비 품질 향상 검증; 단순 테스트 성공과 전체 요구 충족 구분 |
| 작업 상태·동시성 | B | task transition CAS, 다중 프로세스 시험 이력 | 취소/재개/프로젝트 변경과 장애 복구를 동일 출하물에서 재확인 |
| 대화 저장 원자성 | B | revision CAS, 프로세스 잠금, 저장 ID·migration 개선 | 압축 정책 변경에 맞춘 회귀 계약 정리; 거대 단일 메시지/많은 대화 부하 |
| 장기 기억·문맥 보존 | C | 자동 압축·요약·retained IDs, 다중 memory providers | 두 번째 자동 압축에서 초기 요구사항 유실 재현. 메시지 제한만으로 보존성 보장 불가 |
| 세션 삭제·개인정보 생애주기 | C | 삭제 API/메모리 scope, 저장 충돌 방지 | 삭제 후 기존 writer가 세션을 되살림. 삭제 세대/tombstone 필요 |
| Vault·지식 저장 | B, 잔여 검증 | Git-first, YAML metadata, 변경 이력 | 모든 writer의 원자 저장·오류·crash 복구에 대한 추가 fault injection 필요 |
| 인증 | B/C | hash, bearer, fail-closed, 로그인 제한, WS ticket | PIN 변경이 이전 token을 폐기하지 않음. 원격·로컬 PIN 정책 분리 필요 |
| 도구 권한·샌드박스 | B | 승인·path/symlink/읽기 경계, macOS 검증 이력 | 실제 배포 모드별 동일 경계 검증; Linux/Docker를 macOS PASS로 대체 불가 |
| 비밀정보 취급 | B | 서버측 저장 계약·브라우저 영속 제거·redaction 개선 | export/log/backup/desktop 진단까지 현재 후보 end-to-end 재검증 |
| RAG·검색·실패 기억 | B | 벡터·키워드/코드 인텔리전스, 실패 회상, memory conflict resolution | 정답 corpus의 Recall@k·근거 정확성·한국어 질의·중복 제거 측정 |
| 대시보드 동작·회복 | B, 현재 전체 미검증 | route 오류 경계, 404, 작업/승인 UI, 상태 unknown 처리 | 현재 인증 후 모든 핵심 동선의 브라우저 검증과 설치물 일치 확인 |
| 접근성·다국어·모바일 | B, 현재 전체 미검증 | 디자인 토큰·keyboard 계약·CJK/접근성 과거 작업 | 화면 전체의 키보드·screen reader·375px 및 실제 휴대폰 연결 검증 |
| 관측·운영 | B/C | metrics, readiness endpoint, build provenance, runbooks | K8s readiness가 readiness endpoint와 연결 안 됨; 고객 지원 진단 동선 완주 |
| 장기 안정성 | C/판정 대기 | 8h 시험·RSS/FD/orphan 측정과 수정 | 이전 8h FAIL. 새 8h 완료 전 PASS 불가; 요구 보존 시험도 추가 |
| 테스트·품질 gate | B | 과거 후보 23/23 required PASS, 회귀·증거 지문 | 현재 HEAD는 이후 변경 포함. 새 통합 후보 기준 전체 gate 필요 |
| 설치·패키징 | B | Python 포함 DMG smoke와 desktop shell 구현 이력 | Electron→DMG 통합, 일반 고객 기기 설치 완주, signing·실제 feed 잔여 |
| 업그레이드·rollback | C | 정책·체크리스트 존재 | 이전 artifact 없음은 시험 성공이 아님. N/A 범위와 현 버전 backup/restore 구분 |
| self-hosted 배포 | C/실험적 | Docker/K8s·volume·resource·network manifests | namespace 설치 순서 오류, readiness 배선, 깨끗한 host 검증 |
| 문서·지원 정보 | C | 풍부한 ADR/runbook/증거/체크리스트 | 과거 상태와 최신 상태 혼재, 포트·후보·gate 수·지원 행의 동기화 |
| 공식 지원·출하 승인 | D | NO-GO를 명시하고 승인 경계 관리 | 지원 matrix의 Supported 행 없음. 현재 후보의 기술·운영·소유자 판정 필요 |
| Enterprise SaaS | 범위 밖 | 일부 기초 deployment 구성 | RBAC/SSO/tenant isolation/billing/SLA는 별도 제품 범위 |

대표 근거: [GA 지원 범위](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/ga/GA_SUPPORT_MATRIX.md:11), [제품 ADR](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/adr/0003-ga-product-scope.md:11), [모델 라우터](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/model_router.py:482), [Adaptive 실행](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:352), [memory 회상](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/memory_provider.py:364).

## 5. 우선순위가 높은 실제 발견

### F1. P1 — 반복 자동 압축 후 초기 요구사항 유실 [재현]

기본 상한 64개를 넘으면 오래된 메시지를 요약 1개와 최근 6개로 교체한다. 자동 경로는 LLM 요약 함수를 전달하지 않는다. fallback은 user/tool 메시지의 앞 100자, 처음 5개만 채택한다. 이전 요약은 system 역할이어서 다음 압축에서 제외된다.

| 임시 저장소에 append한 수 | revision | 저장 메시지 수 | 첫 요구사항 marker |
|---:|---:|---:|---|
| 64 | 64 | 64 | 존재 |
| 65 | 65 | 7 | 존재 |
| 122 | 122 | 64 | 존재 |
| 123 | 123 | 7 | 사라짐 |

실제 marker는 합성 문자열 EARLY_REQUIREMENT_KEEP_OFFLINE이었다. 고객 데이터는 사용하지 않았다. **장기 작업 중 ‘처음 요청한 제약을 잊는’ 문제로 연결될 수 있다.** CAS revision의 정확함과 내용 보존의 정확함은 별개다.

개선 방향: 원본 이력은 디스크에서 보존하고 모델 입력용 압축 view를 분리한다. 이전 요약을 다음 요약에 누적하고 명시적 사용자 제약·결정·미완료 목표는 별도 구조화 저장소에 보존한다. 65/123회 경계, 요약 실패, 시스템 지시, 긴 메시지, 재시작 후 보존을 검증한다. 새 신경망이나 더 큰 모델로 대체할 문제는 아니다.

근거: [자동 압축](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:485), [append trigger](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:600), [fallback 요약](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/context_summary.py:37).

### F2. P1 — 삭제한 세션이 기존 writer의 save로 재등장 [독립 재현]

A가 세션을 저장 → B가 같은 세션을 로드 → A가 clear_memory(all) → B가 save. 임시 SessionManager 두 인스턴스에서 삭제 1건 이후 합성 메시지가 다시 저장됐다.

삭제는 파일을 제거하지만 삭제 표식을 남기지 않는다. 저장은 디스크 파일이 있을 때만 revision 충돌을 검사하고, 없으면 새 revision 1로 쓴다. 결과적으로 B의 오래된 상태를 신규 세션으로 취급한다. 개인정보 삭제·사용자 신뢰·장기 실행 에이전트 종료 처리에 영향이 있다.

개선 방향: 삭제 세대/tombstone 또는 기존 writer의 missing-file stale 거부, 삭제와 저장의 잠금 규칙 통일. 지운 자료가 다시 나타나지 않는지를 두 writer 및 프로세스 재시작으로 확인한다.

근거: [clear_memory](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/session_manager.py:438), [저장 revision 판정](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/session_manager.py:717).

### F3. P1 — 23/23 PASS의 대상과 현재 코드가 다름 [산출물/원문 확인]

현재 판정 카드의 후보는 b6003205365606407cadfd6cbb1c813110beef0f. attempt-040 원본은 db0554712267ae06f070f0537cd186d41425ba35와 코드 지문 02349a8d06945e438bdc60799ed770a87d6bb67d33d27f09b52008d242536ed6으로 23/23 PASS를 기록한다. 문서만 추가한 커밋은 동일 코드 지문이면 연결할 수 있다.

그러나 현재 HEAD에는 desktop, SettingsPage, 인증, ConversationStore, soak harness 등 실행 코드 변경이 포함된다. **이전 증거는 유효한 과거 성과이며 현재 코드의 전면 검증 증거로 확장할 수 없다.**

개선 방향: 출하 범위/SHA/artifact를 하나로 선언하고 required gate와 설치물 사용자 동선을 같은 대상으로 재실행한다.

근거: [후보 카드](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md:2280), [지문 규칙](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/scripts/ga_gate.py:182).

### F4. P1 — 장기 안정성은 아직 열려 있음 [과거 FAIL + 현재 진행]

이전 full soak는 28,800.051초, SC-1~5 PASS, SC-6 FAIL이다. RSS 증가 1,654.9MB가 기준 64MB를 넘었다. 오류·FD 증가·orphan worktree는 0이었다. 이후 제품에 기본 64-message 자동 압축을 넣었고 RSS 기준은 유지했다.

수정 후 120초 probe는 SC-6에서 RSS +17.3MB, append 60,083회, 잔존 메시지 53개로 PASS. 그러나 이 짧은 일부 시나리오 결과는 8시간 전체 PASS를 대체하지 않는다.

추가 요청을 이어 처리한 약 20:43 KST 관측: 재시험 PID 72711, 경과 약 5시간36분, 순간 RSS 114,192KiB, 최종 JSON 미생성. 이는 진행 중 한 시점의 값이며 peak/증가량/최종 판정이 아니다. 진행 중 프로세스를 조작하지 않았다.

근거: [EX-05 실행 기록](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/ga/CR14_EX_EXECUTION_LEDGER.md:75), [수정 및 단기 probe](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/ga/notes/EX05_SC6_RSS_INVESTIGATION_2026-09-15.md:63).

### F5. P2 — 동시 append 시험의 메시지 수 계약이 자동 압축과 충돌 [정적 + 단일 writer 재현]

기존 시험은 최종 메시지 수가 성공한 append 수 이상이어야 한다고 검사한다. 이제 정상 압축이 성공 append를 요약하므로 이 검사는 그대로 성립하지 않는다. 별도 단일 writer 재현에서 120번 성공 append 후 revision120, 메시지62개였다.

초기 QA 에이전트는 58 PASS/1 FAIL(6×20 case)을 보고했으나 사용량 중단으로 해당 원본 로그를 인계하지 못했다. 따라서 그 숫자는 참고로만 남기고 최종 실행 집계에는 포함하지 않는다. 이후 보존된 원본 로그의 두 파일 재실행은 **21 PASS / 3.77초**였다. 동시 CAS 성공 개수에 따라 압축 경계를 넘는지가 달라져 양 결과가 양립할 수 있다. 이를 곧바로 CAS 유실로 단정하면 안 된다.

개선 방향: 압축을 끈 CAS accounting 시험과 압축을 켠 revision·summary·retained-tail 시험을 분리한다. 실패 메시지도 압축과 silent overwrite를 구별해야 한다.

근거: [회귀 assertion](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_val02_conversation_multiprocess.py:48), [보존된 실행 로그](tests.log).

### F6. P2 — PIN 변경과 세션 폐기 정책의 차이 [독립 격리 재현]

PIN 변경은 hash를 갱신하고 기존 bearer의 서명 키·credential generation은 바꾸지 않는다. 임시 hash/signing 파일로 직접 handler와 TokenService를 호출한 결과, 변경 성공 후 이전 token은 여전히 유효했다. 전체 네트워크 로그인 재현은 아니다.

이것이 의도한 세션 정책일 수 있으므로 무조건 취약점이라고 단정하지 않는다. 다만 사용자에게 ‘PIN을 바꿨으니 탈취된 세션도 끊겼다’고 보장할 수 없다. 즉시 전체 로그아웃/credential generation 폐기 기능을 별도로 정의해야 한다. 시험 TokenService 기본 TTL은 43,200초였고 실제 배포 TTL은 설정에 따라 다르다.

또한 변경 API의 4자리 최소값은 환경 구분 없이 적용된다. 로컬 편의를 위한 의도적 선택으로 기록돼 있지만, 원격 공개 배포의 강한 credential 정책과는 분리해 설명해야 한다.

근거: [PIN 변경 완료](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/auth_routes.py:353), [JWT 검증](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/auth.py:230), [길이 정책](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/auth_routes.py:216).

### F7. P2 — K8s readiness·초기 설치 순서 불일치 [정적 확인]

- readinessProbe는 /health를 본다. 이 endpoint는 status ok를 반환한다. 실제 task DB/registry/storage 등을 확인하는 /api/ready는 따로 있고 not_ready에서503을 반환한다. 배포 probe를 이 endpoint에 연결해야 의존성 장애를 readiness에 반영한다.
- 설치 문서는 namespace 생성 전에 그 namespace에 secret을 만든다. 새 클러스터에서는 전제가 충족되지 않는다. namespace manifest → secret → 나머지 manifest 순서로 안내해야 한다.

클러스터에 실제 배포하거나 장애를 주입하지 않았으며 위 판정은 YAML·route·문서의 배선 확인이다.

근거: [probe](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/deploy/k8s/deployment.yaml:73), [ready 구현](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/server.py:587), [배포 순서](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/deploy/README.md:57).

### F8. P2 — 현재 현황을 읽기 어려운 문서 구조 [문서 대조]

README의 ‘기술 축 모두 닫힘/남은 것은 사람 영역’, ‘책임자 미배정’과 이후 owner 기록·soak 실패가 일치하지 않는다. gate coverage 문서는22개, 최신 candidate는23개다. README 기본 포트8400과 실제 기본8000 안내가 섞여 있다. 새 DMG가 존재하는데 support matrix의 native 설명에는 아직 과거 ‘패키지 근거 없음’이 남아 있다.

지원 승인이 없는 것은 그대로 유지하되, ‘구현 없음’과 ‘구현됐지만 미지원’을 구분해야 한다. 최신 현황표 하나에 후보/코드지문/시험/지원/승인을 모으고 과거 이력을 별도 구역으로 내려야 다음 에이전트의 중복·오판을 줄일 수 있다.

근거: [README 현황](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/README.md:37), [support matrix](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/ga/GA_SUPPORT_MATRIX.md:17), [패키징 미완 목록](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/packaging/notes/SESSION_CHECKPOINT_2026-09-15.md:65).

## 6. 실제 검증 결과와 독립 검토 기록

모든 아래 레인은 동일 HEAD ffb0ebb312b76d86742d3e4065628a9704f8268e를 기준으로 한다. 초기 5개 레인 일부가 계정 사용량 제한으로 종료되어, 목표 보고서를 보존하고 나머지 주요 주장을 작은 독립 검토로 재검증했다. 원래 예정했던 5개 전면 독립 검토가 모두 완료된 것으로 표시하지 않는다.

| 검토 영역 | 판정 | 근거와 한계 |
|---|---|---|
| 목표·제약·개선 반영 | FAIL(상용 완료 명제) | 목표 보고서; 구현 다수 존재하나 현재 후보·8h·설치물 증거 부족 |
| 코드 품질 | FAIL(재현된 범위) | 세션 삭제 부활, 반복 압축 초기 요구 유실 |
| 보안 | 정책 공백 확인 / 전체 INCONCLUSIVE | PIN 변경 후 token 유효; 일반 보안 인증 전면 수행 아님 |
| QA | 좁은 회귀 PASS / 전체 INCONCLUSIVE | 21 tests PASS, 저장 재현, PIN 화면; 전체 E2E·8h 종료 미확인 |
| 문서·배포 context | FAIL(정확성) | readiness/namespace/현재 후보 문서 불일치 |
| debugging runtime audit | 결함 확인 / 전체 INCONCLUSIVE | 임시 데이터 원인 재현; 제품 수정이나 모든 경로 검증 없음 |

목표 레인 원문(`goals.md` — **저장소에 없다**: 세션 산출물이며 링크 위생 점검에서 dangling 으로 확인됨, 2026-09-16), [독립 재검토 원문](independent-review.md), [회귀 실행 로그](tests.log), [이번 런타임 관측](runtime-evidence.txt). 과거 backend/security 보고서를 현재 증거로 재사용하지 않았다.

## 7. 상용화를 위한 실행 순서

1. **데이터/요구 보존부터**: F1 반복 압축과 F2 삭제 부활 수정. 성공 조건은 장기 기억 보존과 삭제 후 재저장 거부의 재현 회귀다.
2. **검증 계약 정리**: F5 CAS 시험 분리. 메모리와 정보 보존을 동시에 평가한다.
3. **진행 중 soak 결과 보존**: 기존 FAIL을 덮어쓰지 않고 새 결과를 별도로 판정한다. 새 PASS도 그 실행 대상에만 적용한다.
4. **인증/배포/문서**: F6 세션 폐기 의도 명시, F7 배선과 순서, F8 현재 현황 정리.
5. **출하물 통합**: 실제 고객용 한 artifact로 설치→PIN→모델 연결→작업→승인/취소→재시작→이력/backup 복원까지 완주.
6. **후보 고정·지원 판정**: 같은 코드 지문의 required gates, OS/provider support 행, update/signing/owner 조건을 함께 마감.

현재 제품의 우선순위는 기능 추가보다 **기억·삭제·복구·후보 증거의 일관성**이다. 이것이 외부 신경 구조를 붙였을 때 효과를 판단할 정상 기준선도 만든다.

# 8. FlyWire Codex 조사

## 8.1 확인한 사이트와 데이터의 의미

사용자가 제공한 주소는 [FlyWire Codex FAFB](https://codex.flywire.ai/?dataset=fafb)다. 여기서 Codex는 Connectome Data Explorer라는 연구 데이터 탐색기이다. FAFB는 성체 암컷 초파리 뇌이며 현재 표시 snapshot은 v783이다. 연구 논문은 139,255개 뉴런과 그 사이 약54.5백만 화학 시냅스를 보고한다. [원 논문](https://www.nature.com/articles/s41586-024-07558-y)

사이트의 connection 수는 시냅스 개수와 같지 않다. 여러 시냅스가 한 뉴런 쌍의 연결로 집계되고, 화면에는 threshold가 적용된다. 현재 첫 화면 FAFB는3,732,460 connections이며 기본 최소5 synapses 필터가 있다. 이를54.5백만 시냅스 또는 무필터 graph edge 수와 혼동하면 데이터 import 검증부터 틀어진다. [Codex 첫 화면](https://codex.flywire.ai/?dataset=fafb), [FAQ](https://codex.flywire.ai/faq)

**이 자료는 학습 완료된 코딩 모델 weight나 초파리의 완전한 실행 가능한 정신 복제본이 아니다.** 입력·출력 인코딩, 뉴런 dynamics, 시간상수, plasticity/학습 규칙, downstream 학습 과제를 추가로 정해야 실행 모델이 된다. 생리 모델 연구도 neurotransmitter 예측·gap junction·neuromodulation 등 명시적인 가정과 한계를 갖는다. [생리 모델 및 한계](https://www.nature.com/articles/s41586-024-07763-9)

## 8.2 이번에 접근한 범위

첫 화면·FAQ·About·관련 논문·공식 데이터 archive를 확인했다. 로그인 없는 API/download 접근은 sign-in 화면으로 돌아왔다. Google 계정으로 약관에 동의하거나 계정을 새로 만들지는 않았다. 따라서 로그인 후 3D neuron 상세 탐색 또는 전체 데이터 다운로드를 수행했다는 주장은 하지 않는다.

FAQ는 대량 접근에 live page scraping 대신 static download를 권한다. 현재 직접 읽은 FAQ에는 Codex API token을 다운로드 요청에 포함하는 안내가 있다. 검색 캐시의 예전 token 없는 예시보다 현재 페이지의 계약을 따라야 한다. neuron root ID·snapshot·annotation 버전·필터를 함께 고정한다. [다운로드/접근 FAQ](https://codex.flywire.ai/faq)

공식 [Zenodo v783 archive](https://zenodo.org/records/10676866)는 proofread_connections 약852MB, 전체 synapse 파일 약9.5GB를 제공한다. 후자는 proofreading된 뇌 내부54.5백만 시냅스만 담는 표가 아니므로 같은 것으로 로드하면 안 된다. 이번에는 메타데이터만 확인했으며 큰 파일은 내려받지 않았다.

Zenodo REST metadata에서 해당 archive license id가 cc-by-4.0임을 직접 확인했다. 다만 이것을 모든 FlyWire annotation·웹사이트 자산·시뮬레이터 코드의 동일 라이선스로 확대하면 안 된다. 실제 상용 포함 대상 파일별 출처/버전/라이선스/수정 내역을 기록하고 기존 THIRD_PARTY_NOTICES 및 SBOM 절차에 연결한다. 이는 해당 데이터 레코드의 메타데이터 확인이며 제품 전체의 법률 승인 판정이 아니다.

## 8.3 관련 연구가 실제로 입증한 것

- 2024 생리 시뮬레이션: 연결 정보와 뉴런 모델로 특정 감각→운동 회로 반응을 예측했다. 언어·코딩 추론 향상 실험은 아니다. [Nature](https://www.nature.com/articles/s41586-024-07763-9)
- 2026 FlyGM 연구: connectome graph와 학습 가능한 모듈을 결합하여 가상 초파리 이동을 강화학습한다. 논문은 MLP보다 계산·메모리 비용이 높고 locomotion 밖 확장이 후속 과제라고 명시한다. 이번에 확인한 출처는 arXiv v3 preprint다. [FlyGM](https://arxiv.org/html/2602.17997v3)
- 후각 회로 기반 similarity search 연구: 차원을 확장한 뒤 일부 강한 활성만 남기는 방식이 검색 알고리즘으로 연구됐다. 이 원리를 쓰는 작은 검색 모듈은 전체 FAFB를 복제하지 않아도 만들 수 있다. [연구기관의 원 연구 설명](https://www.salk.edu/news-release/fruit-fly-brains-inform-search-engines-future/)

따라서 ‘뇌 구조를 가져오면 기존 LLM보다 지능이 좋아진다’는 결론은 불가하다. **작은 정책·검색 모델에 유용한 구조적 제약을 제공할 가능성**은 실험할 가치가 있다.

# 9. Ssak-Ai에 접목할 수 있는 구체적인 방식

아래는 제안이며 구현/성능 확인 결과가 아니다. 같은 이름의 새 계층을 중복 생성하지 않고 기존 접점을 확장하는 전제다.

| 방법 | 목적 | 기존 접점 | FAFB 원데이터 필요 | 추천 |
|---|---|---|---|---|
| 희소 기억 검색(FlyHash 유사) | 유사 실패·작업 기억 후보를 저비용으로 추림 | FailureMemory.find_similar, MemoryManager.prefetch_all | 불필요; 회로 원리 기반 | 가장 먼저 작은 offline 실험 |
| 작업 전략 선택기 | 탐색/직접 답변/수정/재검증/모델 escalation 선택 | UnifiedAgent.run, ModelRouter.route, CognitiveLoop | 선택; motif 또는 축소 graph | 우선 비교 실험 |
| novelty/반복 실패 탐지 | 같은 실패 반복시 전략 전환 신호 | FailureMemory, CognitiveLoop | 불필요 | 유용하나 기존 heuristic/bandit부터 비교 |
| 연결망 일부를 고정한 작은 recurrent/GNN 모듈 | 최근 실패/비용/불확실성의 시간 흐름 처리 | router 앞의 advisory scoring | 필요 | 연구 옵션, 기본 OFF |
| brain graph 탐색·설명 UI | 데이터·경로·활성 시각화 | plugin panel/command palette | 필요 | 교육·연구 기능 가치; 코딩 품질 상승과 별개 |
| 전체 connectome SNN/FlyGM 실행 | 뇌 dynamics·embodied control 연구 | 별도 실험 worker/process | 필요 | 현재 상용 경로와 분리 |
| 기존 Qwen/MLX 가중치에 직접 이식 | LLM 자체 교체/증강 | 단순 대응 지점 없음 | 필요하더라도 불충분 | 현 단계 비추천 |

### A. 가장 실용적인 첫 실험: 기억 후보 검색

현재 FailureMemory는 의미 검색 후 부족하면 키워드를 사용하며, MemoryManager는 여러 provider 결과를 모아 충돌을 해결한다. 여기에 임베딩→희소 확장→top-k 활성 fingerprint를 만들어 후보만 좁히는 검색 경로를 시험한다. 최종 순위와 명시적 사실의 우선권은 기존 authoritative memory 규칙이 결정한다.

이점 가설: 큰 실패 이력에서 검색 latency/RSS 또는 중복 후보가 줄 수 있다. 한계: 임베딩 품질이 낮으면 희소 hashing이 의미를 만들어주지 않는다. 작은 데이터에서는 기존 벡터 검색이 더 빠를 수 있다. **유실된 초기 요구사항을 복원하는 해결책으로 사용하면 안 된다.**

접점: [FailureMemory](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/failure_memory.py:106), [MemoryManager](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/memory_provider.py:364).

### B. 코딩 품질에 직접 연결되는 실험: 전략 선택

입력 특징 후보: task 유형, 남은 예산, 최근 테스트/도구 결과, 같은 오류 반복 횟수, provider availability, latency, 검색 근거 신뢰도. 출력은 제한된 행동 집합의 점수다. 예: 추가 탐색, 기억 검색, 직접 수정, 테스트 실행, 더 강한 모델 선택, 중단/사용자 문의.

중요한 제약: ModelRouter.route는 현재 combo_name을 받는다. 여기에 신경망을 단순 삽입해도 task context가 들어오지 않는다. 상위 호출자에서 명시적 feature를 전달하는 작은 계약이 먼저 필요하다. 명시적으로 사용자가 선택한 모델·provider 제약을 advisory score가 덮어쓰지 않아야 한다.

초기에는 선택기 출력을 기록만 하고 기존 행동을 유지하는 shadow 모드로 평가한다. 향상될 때만 허용된 후보 사이의 순위를 바꾼다. 승인·샌드박스·네트워크 정책은 별도 결정적 코드가 계속 집행한다.

접점: [ModelRouter 후보 필터](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/model_router.py:535), [UnifiedAgent](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:352), [CognitiveLoop](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/cognitive_loop.py:95).

### C. 실제 FAFB를 사용하는 연구 경로

1. snapshot783의 연결/주석을 다운로드해 checksum·root ID·threshold·집계 규칙을 manifest에 기록한다.
2. 연구 질문에 맞는 subset 또는 cell-type/region 집계 graph를 고정한다. 단순히 뇌 부위를 ‘계획 담당/검토 담당’으로 이름 붙이는 것으로 기능 대응이 입증되지는 않는다.
3. 방향과 양의 synapse count를 보존하고 sparse adjacency로 변환한다. 전달물질 label만으로 모든 흥분/억제 부호를 확정하지 않는다. 수용체·회로·모델 가정에 따라 다른 부분이 있으므로 부호를 가정/ablation 대상으로 관리한다.
4. task feature를 입력으로, 제한된 전략 점수를 출력으로 학습한다. 연결 topology만 고정하고 입력/출력 projection 및 일부 parameter를 학습하는 방식부터 시작한다.
5. graph의 degree를 보존하고 배선만 섞은 대조군, 무작위 graph, 작은 MLP, contextual bandit, 기존 heuristic과 동일 조건에서 비교한다.
6. 효과가 없으면 기능 flag를 끄고 기존 routing을 그대로 사용한다. 외부 사이트 연결 실패가 본 프로그램 시작 실패로 이어지지 않도록 runtime은 로컬 artifact만 읽는다.

### 권장 구성

사용자 요청 → 기존 실행 context·권한 확인 → 기존 기억 조회 → 선택기 후보 점수 → 기존 router/인지 순환 → 기존 도구 승인·sandbox → 작업 결과 기록 → offline 평가/학습.

여기서 신경 구조가 맡는 역할은 ‘어떤 허용된 선택을 먼저 할지’이다. 파일 접근권·삭제권·외부 전송권을 판단하는 최종 권한자가 아니다. 외부 데이터 학습에 사용자 코드·대화가 자동 업로드되지 않도록 로컬 처리 경계를 유지한다.

## 10. 계산 비용과 구현 난도

N=139,255인 dense float32 N×N 행렬은 77,567,820,100 bytes, 약77.6GB(72.2GiB)다. 이는 단지 weight 행렬만의 산술값이며 activation/optimizer/LLM 메모리는 추가다. 따라서 기본 Mac 앱에 dense 전뇌 행렬을 올리는 방식은 부적절하다.

Sparse 표현은 크게 줄일 수 있지만 edge 수, index 크기, latent width, 반복 step, 학습 batch에 따라 비용이 달라진다. 전체 graph를 Python NetworkX 객체로 뜨거운 경로에 넣으면 객체 오버헤드가 크다. prototype에서는 작은 subset과 CSR/COO 등 배열 기반 표현을 쓰고, 실제 Mac 환경에서 메모리·지연을 측정해야 한다. 기존 LLM과 같은 메모리를 경쟁하므로 새 구조가 공짜로 효율을 높인다고 가정하면 안 된다.

작업량 추정(1명 숙련 엔지니어, 공개 데이터 접근 가능, 기존 평가 harness 재사용 가정):

| 단계 | 예상 작업량 | 완료 산출물 |
|---|---|---|
| 기준선·데이터 계약·실험 설계 | 2–4 person-days | 데이터 manifest, 고정 task split, metric/대조군 |
| 희소 검색 또는 전략 선택 최소 실험 | 5–10 person-days | baseline 대비 offline 결과·RSS/latency |
| 축소 FAFB graph 학습 실험 | 10–20 person-days 추가 | topology ablation·반복 seed 결과 |
| 제품 통합·회귀·shadow telemetry | 5–10 person-days 추가 | feature flag, fallback, exportable 실험 증거 |
| 전체 뇌 dynamics/학습 | 여러 주 이상, 불확실성 큼 | 연구 프로젝트; 일반 제품 개발 견적과 분리 |

이는 확정 일정이나 GPU 비용 견적이 아니다. 코드 품질 개선 및 인증/배포 마감은 별도다.

## 11. 성능 향상을 입증하는 실험 설계

**비교군**: 현재 기준선 / 단순 규칙 또는 contextual bandit / 작은 MLP / 희소 회로 원리 모델 / 실제 FAFB subset / degree-preserving rewired graph. 전체 모델 호출 예산, base LLM, task split, seed를 동일하게 맞춘다.

**데이터**: 동일 저장소 작업의 변형이 train/test 양쪽으로 들어가지 않도록 repository 또는 task-family 단위로 분리. 초기100개 안팎 task는 pilot로 쓰고, 본 판정 표본수는 관측 분산과 검출하려는 개선 폭에 맞춰 늘린다. 성공 로그만 학습하지 않고 실패/중단 사례도 포함한다.

**지표**:

- 작업 성공: 숨겨진 테스트와 요구사항을 모두 충족하는 비율.
- 장기 기억: 65/123회 이상 이후 초기 제약·중간 결정 유지율.
- 효율: 성공 작업당 토큰·시간·provider 비용, P50/P95 지연.
- 복구: 반복 오류율, 유효하지 않은 재시도 횟수, 취소 응답·재시작 복원.
- 검색: Recall@10, 정확한 근거 비율, 중복률, peak RSS.
- 안전: 금지 동작·권한 우회 여부, 허용 후보 밖 출력 처리.
- 운영: 동시/반복 workload의 RSS·FD·worker 종료, artifact 재현성.

**출시 판단 제안**: pilot 전에 성공 기준을 고정한다. 예를 들어 품질을 떨어뜨리지 않고 성공 작업당 비용10% 절감, 또는 동일 비용에서 성공률 개선의 신뢰구간이0을 넘는 조건을 택할 수 있다. 이 수치는 관측 결과가 아니라 제안이다. 어떤 평균 향상도 권한 우회·삭제 부활·초기 요구사항 유실을 상쇄하는 것으로 처리하지 않는다.

FAFB가 MLP/bandit 또는 섞은 graph보다 낫지 않다면 ‘생물학적 구조의 효과’는 입증되지 않은 것이다. 그때는 더 단순한 모델을 채택하는 것이 상용 제품에는 낫다.

## 12. 최종 권고

**상용화:** 새 기능을 더 붙이기 전에 F1/F2의 데이터·기억 계약, 현재 후보의 통합 검증, 실제 설치·복구 동선을 먼저 닫는다. 진행 중 soak는 그대로 완주시키고 해당 결과만 별도 평가한다.

**FlyWire:** 검토 가치가 있다. 첫 도입은 작은 희소 기억 검색 또는 제한된 전략 선택기로 시작한다. 실제 connectome topology의 추가 가치가 대조군 대비 확인될 때만 제품 옵션으로 승격한다. 전체 초파리 뇌 탑재·LLM 교체·지능 급상승은 현재 자료로 약속할 수 없다.

**이번 작업의 결과는 분석 보고서이며 개선 코드나 FlyWire 통합 코드는 작성하지 않았다.**

독립 보고서 일관성 확인: PASS. 21건 실행 원본, 범위·불확실성 구분, FlyWire 제안의 한계, 행렬 메모리 산술을 확인했다. 부록의 미확보58/1 로그 표현은 본문과 일치하도록 정정했다. 이는 제품 전체 승인과 별개다.
