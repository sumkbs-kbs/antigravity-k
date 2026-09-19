---
title: Ssak-Ai 전체 QA 및 수정 인수인계
tags: [qa, handoff, index]
date: 2026-09-02
reviewed_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
---

# 전체 QA 및 수정 인수인계

최초 전체 QA 판정: **배포 승인 불가 / 58점**. 후속으로 F01 Workspace WebSocket 인증 누락, F02/F07 Vault Git 트랜잭션, F03 릴리스 버전 원천, F04 Mutation historical snapshot 정합성, F05 배포물 기반 SBOM/notices, F06 의존성 권고 triage, F08 Wiki Markdown 안전화, F09/F10 E2E 인증 fixture와 hard gate, F11 설치 matrix, F12 모바일/한국어 UI, F13 VS Code 확장, F14 release-baseline 검증기, F15 정적/행동 보안 게이트의 수정·검증을 완료했다. F01은 집중/실제 wire 28건과 회귀를 통과했고, F02/F07는 Vault/API/멀티프로세스 테스트와 전체 비벤치마크 회귀 4,836건을 통과했으며, F03은 실제 wheel/sdist 빌드와 태그 불일치 거절을, F04는 dashboard 598 test와 실제 브라우저 3 viewport/상태 검사를, F05는 실제 wheel/sdist 문서 포함과 변조 거절을 확인했다. F06은 base runtime/dashboard production 권고를 0건으로 만들고 Python 4,855·dashboard 598 test와 실제 배포물 검증을 통과했으며, optional RAG ChromaDB 4건만 명시적 residual로 남겼다. F08은 regex HTML/`dangerouslySetInnerHTML` 경로를 제거하고 dashboard 603 test, production browser E2E, CSP 유지를 확인했다. F09/F10은 인증 fixture를 실제 상태 계약으로 복구하고 전체 Playwright 59 expected, 실패 전파 exit 1까지 검증했다. F11은 base+dev 전체 4775 passed와 rag focused 38 passed로 선택 의존성 경계를 검증했다. F12는 `/plugins` clipping과 `/data-extraction` 지표 붕괴를 재현·수정하고 8 route × 3 viewport fresh capture와 전체 Playwright 59 expected로 회귀를 확인했다. F13은 clean install에서 lint/compile/test를 복구하고 실제 Extension Host 4 시나리오로 offline/timeout/재연결/flood/deactivate를 검증했다. F14는 AGPL/GPL SPDX 리터럴 및 변형 스캔 전수 거절, CLI/HTTP/Server/WebUI 엔트리포인트 계약 검증 및 격리 벤치마크 23건을 통과했다. F15는 실제 sandbox-exec 프로세스 실행 및 cleanup, 샌드박스 부재 시 fail-closed, OS 권한/네트워크 격리, auto-pilot 위험 명령 차단 입증 및 전체 430개 소스 파일 mypy 0 errors를 달성했다. 이 수정들만으로 전체 출시 판정을 변경하지 않는다.

## 읽는 순서

1. [상세 QA 보고서](REPORT.md): 검토 범위, F01–F15 결함/위험, 실제 검사 결과, 평가, 한계.
2. [수정 인수인계 계획](REMEDIATION_PLAN.md): 에이전트 파일 소유권, 이슈별 재현·수정 방향·완료 조건, 재검증 명령, 결과 기록 양식.
3. [증거 인덱스](EVIDENCE_INDEX.md): 실제 로그·캡처·독립 검토 보고서와 해석상 주의사항.
4. [F01 수정 진행 기록](remediation/F01-workspace-websocket-auth.md): 수정 범위, RED→GREEN, 네트워크 E2E, 재검증·롤백, 남은 위험.
5. [F02/F07 수정 진행 기록](remediation/F02-F07-vault-git-transaction.md): 노트 전용 Git 커밋, 사용자 index 보존, 실패 상태 계약, 남은 위험.
6. [F03 수정 진행 기록](remediation/F03-release-metadata-version.md): 빌드된 wheel/sdist metadata 기반 버전 추출, 소스/태그 일치 검증, CI 조기 게이트.
7. [F04 수정 진행 기록](remediation/F04-mutation-snapshot.md): historical snapshot schema/원천/신선도 계약, malformed 데이터 fail-closed, 실제 브라우저 QA.
8. [F05 수정 진행 기록](remediation/F05-release-sbom-notices.md): lockfile runtime closure 기반 SBOM/notices 생성, 배포물 포함/변조 검증, supply-chain manifest.
9. [F06 수정 진행 기록](remediation/F06-dependency-triage.md): 권고별 runtime/optional/dev 분류, pnpm 11 override 계약, 잔존 ChromaDB 위험 관리.
10. [F08 수정 진행 기록](remediation/F08-wiki-markdown-sanitization.md): Wiki Markdown 이중 안전 경계, 실제 production browser E2E, CSP 유지, stale bundle 함정.
11. [F09/F10 수정 진행 기록](remediation/F09-F10-e2e-auth-hard-gate.md): E2E 인증 상태 분리, 실제 UI login/fallback, 전체 Playwright hard gate와 실패 전파.
12. [F11 수정 진행 기록](remediation/F11-install-matrix.md): base+dev와 rag 설치 경계, keyword-only fallback, CI base/rag matrix.
13. [F12 수정 진행 기록](remediation/F12-mobile-cjk-layout.md): 모바일 control clipping, 한국어 word wrapping, 지표 layout 회귀와 실제 브라우저 증거.
14. [F13 수정 진행 기록](remediation/F13-vscode-extension.md): VS Code 확장 clean install, lint/test runner, 실제 Extension Host E2E와 dependency 갱신.
15. [F14 수정 진행 기록](remediation/F14-release-baseline.md): 라이선스 스캐너 사각지대 해소, CLI/API/Server/WebUI 엔트리포인트 계약 검증.
16. [F15 수정 진행 기록](remediation/F15-static-and-behavioral-gates.md): 행동 기반 샌드박스/권한 검증, auto-pilot 위험 차단, mypy 전체 430개 소스 무결성.
17. [최종 전체 통합 및 회귀 검증 기록](remediation/FINAL-INTEGRATION-VERIFICATION.md): 청크 분할 충돌 해소, 전체 단위 테스트 4,890건, 라이브 백엔드 스모크 9건, Playwright E2E 59건 전수 통과.
18. [UI 시각적 검토 최종 승인 보고서](remediation/VISUAL-REVIEW-AUDIT.md): 8개 라우트 × 3개 뷰포트 24개 실화면 정밀 검토, 바운딩 박스 오버플로 0건, 시각적 게이트 최종 PASS.
19. [macOS .dmg 배포 가이드](../../packaging/MACOS_DMG_GUIDE.md): Ssak-Ai.app 번들 및 5.5MB 압축 DMG 생성(`make dmg`), 드래그 앤 드롭 설치 및 GUI 런처 지원.
20. [에이전틱 AI를 위한 런타임 에러 진단 저널 가이드](../../architecture/AGENT_ERROR_JOURNAL.md): 런타임 에러 스택/스니펫/요청정보 수집, JSONL/Markdown 동시 기록, AI Fix Prompt 자동 생성 및 CLI/API 조회 지원.

## 우선 처리

- F01: Workspace WebSocket 인증 누락 수정·검증 완료. 서비스별 ACL/Origin 강화는 별도.
- F02/F07: Vault의 무관한 staged 변경 커밋과 실패 후 파일/Git 상태 수정·검증 완료.
- F03: 릴리스 버전 추출과 빌드 산출물/태그 일치 수정·검증 완료.
- F05: 실제 배포물의 SBOM/notices 수정·검증 완료. hoisted npm transitive closure 누락도 후속 수정·재검증 완료.
- F04: Mutation 수치를 historical snapshot으로 명확히 표시하고 실시간 CI 위장 제거. 실시간 ingestion은 별도 과제.
- F06: 의존성 권고 triage 완료. optional RAG ChromaDB fixed release 추적 필요.
- F08: Wiki HTML sanitization/CSP 안전성 수정·검증 완료. F09/F10 전체 Playwright 재실행에 포함되어 통과했다.
- F09/F10: 인증 fixture 복구와 전체 E2E hard gate 수정·검증 완료. 실제 GitHub Actions runner 실행은 아직 증거로 남지 않았다.
- F11: base+dev 설치에서 keyword-only fallback 계약을 복구하고 CI base/rag matrix를 추가했다.
- F12: 390px에서 플러그인 toggle/카드 완전 노출과 지표 label 가독성을 복구했다. 한국어 word wrapping 계약과 8 route × 3 viewport fresh capture, 전체 Playwright 59 expected, 및 독립 시각적 감사 통과로 수정·검증 완료.
- F13: 확장 manifest/활성화 계약과 ESLint/test runner 복구, 실제 Extension Host 4 시나리오 및 마켓플레이스 패키징(VSIX 5.46KB) 통과로 수정·검증 완료.
- F14: AGPL/GPL 리터럴 및 헤더/풀네임/대소문자 변형 전수 거절, 엔트리포인트 AST 계약 검증, 저장소 미변조 격리 벤치마크 23건 통과로 수정·검증 완료.
- F15: 실제 sandbox-exec argv 실행/cleanup, fail-closed, OS 쓰기/네트워크 격리, auto-pilot 위험 명령 차단 행동 검증, 전체 430 소스 파일 mypy 0 errors로 수정·검증 완료.

다른 에이전트에게는 `REMEDIATION_PLAN.md`의 마지막 시작 문장과 배정할 Fxx를 전달하면 된다. 현재 HEAD가 기준 SHA와 다르면 먼저 재현 여부를 다시 확인한다.

## 다음 우선순위

1. F09/F10/F11/F13 원격 CI: 권한이 확보되면 실제 GitHub Actions workflow/matrix(Linux/macOS/Windows) 원격 실행 로그를 evidence로 추가한다.
2. F12 독립 visual reviewer 게이트: 24개 실화면 캡처 및 DOM 분석 기반 **승인(APPROVED / PASS) 완료** ([보고서](remediation/VISUAL-REVIEW-AUDIT.md)).
3. F13 Marketplace 패키징은 검증 완료(VSIX 5.46KB, 0 warnings)되었으며, 외부 마켓플레이스 게시 권한 확보 시 퍼블리시 단계를 진행한다.

## 보존/변경

원래 사용자 변경 `data/benchmark_results.json`은 보존했다. 최초 QA는 읽기 전용이었고, 후속 F01 작업에서 제품 2파일과 테스트 2파일 및 관련 문서를 변경했다. 공통 인증 설정·의존성·대시보드는 변경하지 않았으며 커밋/배포하지 않았다. 상세 raw evidence는 `.omo/evidence/full-qa-2026-09-02/`에 로컬 보존되어 있으므로 다른 컴퓨터의 clone에는 자동으로 따라가지 않을 수 있다. 문서에 보존한 재현 절차와 테스트 파일로 새 격리 환경에서 재검증할 수 있다.
