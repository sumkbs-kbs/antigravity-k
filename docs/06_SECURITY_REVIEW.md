# 06 Security Review

기준일: 2026-08-17

## 검토 범위

파일·쉘·Git·브라우저·웹 검색·provider key·memory/Vault·FastAPI route를 대상으로 정적 코드와 테스트를 확인했다. 이 문서는 보안 보증서가 아니라 현재 통제와 남은 검증을 구분한 review다.

## 통제 상태

| 영역 | 현재 통제 | 상태 | 잔여 위험 |
|---|---|---|---|
| tool permission | ToolRegistry allow/deny/prompt, guardrail, approval; approved execution re-check; shell/Git/web fetch/external-brain/system/filesystem/legacy mutation route gates; fail-closed sandbox | [~] | 40 HTTP/urllib/httpx call sites are inventory-visible and guarded; remaining connector permission review |
| protected paths | executor boundary와 audit | [x] | platform-specific path matrix |
| secrets | `.env`/scanner/config redaction 일부 | [~] | 로그/외부 connector 전체 흐름 |
| SSRF | public http URL, all DNS answers checked, PageScraper TCP address pinning, redirect re-check, shared urllib/httpx request hook, robots/crawl-delay policy | [x] | 배포별 legal attestation registry를 enforce 모드로 운영해야 함 |
| prompt injection | web text untrusted wrapper, control markup neutralization | [x] | model compliance/evasion set |
| external code | tool/sandbox/worktree mechanisms, timeout clamp, bounded stdout/stderr, CPU/memory/process limits, fail-closed backend, snapshot rollback on task failure/cancel | [~] | cross-platform enforcement and load matrix |
| authentication | PIN/JWT/API auth routes | [~] | default deployment hardening |
| audit | event bus/audit/tool history | [~] | correlation id completeness |
| dependency | CI pip-audit/bandit/SBOM jobs | [x] workflow exists | findings execution evidence |
| privacy | project/user/global memory stores, provider/durable compliance API, Vault raw-asset exclusion | [~] | raw asset deletion/change consent flow |

## 우선 수정

1. 모든 DNS address가 public인지 확인하고, PageScraper는 resolve 결과를 TCP 연결에 pin하며 redirect마다 재평가한다. raw urllib/HTTPX connector는 동일 egress policy로 inventory한다.
2. `robots.txt`와 crawl-delay를 crawler adapter policy로 적용한다. `LegalTermsPolicy`는 감사 모드와 enforce 모드를 제공하며, 배포는 도메인별 terms URL, 허용 purpose, attestation 만료를 정책 파일로 채운 뒤 enforce로 전환한다. 차단 우회·인증 우회·CAPTCHA 우회는 구현하지 않는다.
3. 웹 본문과 tool result를 모델에게 전달할 때 system/developer/tool markup과 명령어 문법을 데이터로 감싼다.
4. secret scanner와 audit logger의 실제 redaction test를 provider, HTTP, exception, cache, Vault 경로까지 확장한다.
5. provider와 durable store scope 삭제를 사용자 요청으로 실행하고, export/redaction/retention과 Vault raw-asset exclusion/redacted opt-in policy를 적용한다. 원문 asset 변경은 별도 consent flow로 제한한다.

이번 cycle에서 `ToolRegistry.execute_approved()`가 gate를 우회하지 않도록 재검증하고, browser action/autonomous QA/external-brain endpoint가 Playwright, QA engine, 외부 adapter 시작 전에 permission deny를 적용하도록 연결했다. system skill publish/install/remove, env/vault/restart/shields, filesystem mutations, Git file arguments도 side effect 전에 gate와 project-root 경계를 통과한다. 회귀 테스트는 `tests/test_tool_executor.py`, `tests/test_agent_tools_api.py`, `tests/test_api_server.py`, `tests/test_git_api_boundary.py`에 있다.

메모리 compliance slice는 `SessionManager`와 builtin/episodic/working/project/global provider, durable MemoryService/VectorStore/LLMWiki/GBrain/search-cache에 export/redact/retention 계약을 연결했다. `DELETE /api/memory`, `GET /api/memory/export`, `POST /api/memory/redact`, `POST /api/memory/retention`은 인증 middleware 아래에서 provider별 건수와 audit event를 반환한다. project decision/fact와 episodic/Cavemem 저장소는 각 workspace의 `.antigravity/memory/` 아래에 있고, 한 `MemoryManager`를 다른 project root에 재바인딩하면 fail-closed한다. 해석된 memory 경로가 심볼릭 링크로 workspace 밖을 가리키면 저장소 생성 전에 거부한다. Vault 원문 asset은 기본 export에서 제외되고 opt-in에서도 redacted content만 반환한다.

## Egress inventory evidence

`make audit-egress`는 네트워크 요청 없이 `src/antigravity_k`의 Python AST를 스캔하고 `data/audits/egress-inventory.json`을 생성한다. 2026-08-09 실행에서는 40개 `httpx`/`urllib` call site가 발견됐고 모두 `guarded_endpoint`로 기록됐다. `safe_urlopen`과 HTTPX request hook은 송신 직전에 local 허용 범위와 public DNS 해석을 검사하며, private/link-local 주소는 fail-closed로 거부한다. PageScraper는 같은 경계에서 robots.txt, crawl-delay와 `LegalTermsPolicy`를 확인한다. 감사 모드는 정책 누락을 관찰하고, enforce 모드는 attestation이 없는 도메인을 거부한다.

## 출시 차단 기준

- private/link-local address로 fetch 가능한 경로가 0개이며, egress inventory의 guarded endpoint가 유지됨
- 배포 대상 도메인의 legal terms record가 만료되지 않았고 crawler policy가 enforce 모드임
- 승인 없는 destructive side effect가 0개
- secret/PII가 로그와 cache에 남지 않음
- dependency audit/bandit 결과가 review되고, 예외는 문서화됨
- prompt injection fixture가 도구 실행으로 승격되지 않음
- sandbox output/memory/process quota가 실행 중 적용되고 task 실패·취소 시 snapshot rollback이 시도됨
