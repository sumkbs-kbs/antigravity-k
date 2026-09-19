---
title: F01 Workspace WebSocket 인증 수정 진행 기록
tags: [qa, security, websocket, remediation]
date: 2026-09-02
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_auth_bypass_fixed
---

# F01 진행 기록

사용자 요청에 따라 최우선 P1 인증 누락부터 수정한다. 담당: 현재 작업의 root 에이전트. 제품 코드·테스트는 root만 수정하고 독립 계획 검토는 읽기 전용으로 진행한다.

## 작업 상태

1. 완료: 인증 활성화 상태에서 두 실제 WS route의 무인증 upstream 도달을 실패 테스트 6건으로 재현.
2. 완료: 공통 인증 적용, 중복 accept 제거, 자격 증명 query 제거. 250 LOC 제한으로 전송 로직만 별도 모듈로 분리.
3. 완료: 최종 집중/실제 Uvicorn TCP·WS 검사 28건, 격리 Python 회귀 4,827건 통과. 변경 파일 타입/린트/포맷 및 wheel 빌드 통과. 독립 코드 검토 승인.
4. 완료: 결과/한계/재현 명령 저장. 테스트 서버는 context 종료로 정리했으며 임시 worktree 정리 기록은 아래 참고.

## 범위와 계약

- `/api/workspace/services/{hostname}/ws`와 `/ws/{path}`를 같은 인증 경계로 보호한다.
- 기존 `session_state.close_unauthorized_ws`는 accept 후 4401 close를 보내므로, 요구사항은 **서비스 조회·upstream 연결 전 인증 완료**다. handshake HTTP 403을 요구하는 새 정책으로 바꾸지 않는다.
- 기존 query `token`, `pin` 및 `bearer.*` subprotocol을 유지한다. 일반 Authorization 헤더는 기존 WS helper가 지원하지 않는다.
- 인증용 query는 upstream에 보내지 않고 업무용 query 중복/빈 값은 보존한다.
- 서비스별 ACL 및 Origin 정책 신설은 이번 최소 수정 범위가 아니다. 공통 인증 정책은 변경하지 않는다.
- 기존 전체 QA 58/100 및 출시 불승인은 이 한 건을 수정하더라도 자동 해제되지 않는다.

## 원인 및 구현

HTTP 인증 미들웨어는 WS scope에 실행되지 않는다. 두 WS route가 공유하는 `_proxy_websocket`에는 인증 호출 자체가 없어서 PIN 설정과 무관하게 등록된 loopback 서비스에 연결됐다.

- [workspace_services.py](../../../../src/antigravity_k/api/routes/workspace_services.py): `_proxy_websocket` 시작에서 기존 `close_unauthorized_ws`를 호출한다. 거절 시 즉시 return, 성공 시에만 registry를 조회한다. 기존 HTTP 404/409 예외는 WS에서만 1008로 변환한다. 공통 helper가 accept하므로 중복 accept는 제거했다.
- [workspace_websocket.py](../../../../src/antigravity_k/api/routes/workspace_websocket.py): transport만 분리했다. decoded query 키 `token`·`pin`을 모두 제거하고 나머지 중복/순서/빈 값/문자 값을 보존한다. 업무 query의 URL encoding 표기는 정규화될 수 있다. Header는 기존 workspace metadata allowlist만 전달한다.
- 실제 연결 시험에서 추가 발견한 동일 transport 종료 결함도 보완했다. 정상 upstream 종료 시 1000 close를 보낸다. AnyIO TaskGroup의 `ExceptionGroup`에 포함된 연결 오류를 `except*`로 처리하여 1011을 보낸다. 예상하지 못한 오류는 숨기지 않는다. 클라이언트가 이미 끊겼으면 재차 close하지 않는다.
- 네트워크 실패 로그는 고정 문구와 service 필드만 기록하며 token·PIN·전체 URL을 기록하지 않는다. 다만 inbound reverse proxy/access log 전반의 query redaction까지 구현한 것은 아니다.
- 변경 후 제품 파일 pure LOC: route 244, transport 65. 공통 auth·HTTP 동작·의존성·대시보드는 변경하지 않았다. route의 긴 `_HOP_BY_HOP` 상수는 기존 formatter에 맞춰 줄바꿈만 변경했다.

## 재현 및 진행 증거

기준 HEAD는 위 full SHA이며 **미커밋 수정본**을 검증했다. HEAD가 같아도 작업 파일이 다를 수 있으므로 아래 지문을 함께 비교한다. 사용자 기존 `data/benchmark_results.json` 변경은 보존했고 이 수정에는 포함하지 않는다.

### 수정 전 RED

```bash
uv run --no-sync pytest tests/test_workspace_websocket.py -q -k 'unauthorized_workspace_ws' --tb=short
```

당시 6건(경로 2개 × 무토큰/오류/만료) 모두 `Failed: DID NOT RAISE <class 'starlette.websockets.WebSocketDisconnect'>`, **6 failed, 12 deselected in 1.59s**, exit 1. 기대한 4401 대신 실제 echo upstream의 경로 응답을 받았다. 이후 wrong-PIN/오류 subprotocol 사례를 추가하여 현재 같은 selector는 10건이다. RED 개수를 현재 테스트 개수로 바꿔 기록하지 않는다.

### 수정 후 집중 검사 및 실제 wire

```bash
uv run --no-sync pytest tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py -q -s --tb=short
```

중간 결과는 **27 passed in 11.40s**였으며, 이후 send-side disconnect 회귀 1건을 추가했다. **최종 28 passed in 11.37s**, exit 0. 실제 출력:

```text
WIRE: HTTP no-auth=401, login=200, register=201, WS no-auth=4401 x2, authenticated text/binary=PASS x2
```

실제 app/router/middleware를 Uvicorn으로 loopback 임의 포트에서 실행하고 HTTP 로그인으로 발급받은 JWT를 사용했다. HTTP 서비스 등록→두 WS 경로→text/binary 왕복을 수행했다. 전체 앱 lifespan은 `off`로 설정하여 RAG/IDE/예약 작업을 시작하지 않았으며, 이는 전체 부팅이나 전체 브라우저 E2E 검증이 아닌 **인증·프록시 기능의 실제 네트워크 E2E**다. 인증 함수·암호 검증·WS connect/send/receive는 mock하지 않았다. 테스트용 config, registry, 메모리 JWT secret/PIN hash만 fixture에서 격리/복원했다.

| 검사 | 기대/관찰 |
|---|---|
| 두 경로 무토큰·오류 JWT·만료 JWT·오류 PIN·오류 bearer subprotocol | 4401, upstream 연결 없음 |
| 유효 JWT query/PIN query/bearer subprotocol | 두 경로 text/binary 왕복 |
| 중복 token 및 인코딩된 `p%69n` | upstream에서 모두 제거 |
| 업무 query | 중복 room, empty, 공백/plus 의미 보존 |
| 알 수 없는/stopped service, 무인증 | 서비스 존재 여부와 무관하게 4401 |
| 알 수 없는/stopped service, 유효 인증 | 1008, ASGI 예외 없음 |
| 개발 loopback + PIN 없음 | 기존 no-auth 허용 정책 유지 |
| production 또는 non-loopback 설정 + PIN 없음 | 4401 |
| 클라이언트 종료 | upstream handler 종료 Event 확인 |
| 송신 중 client disconnect | application_state만 먼저 DISCONNECTED가 되어도 이중 close 없이 종료 |
| upstream 정상/오류 종료 | 1000 / 1011 close frame 수신 |
| 연결 불가능한 upstream | 기존 connect timeout 이내 처리 후 1011 |

중간 wire 시험은 인증 왕복 1건 통과, 종료 3건 실패였다. 그중 정상/오류 종료 2건은 제품 결함으로 보완했다. 나머지는 테스트 수신 제한 5초가 기존 upstream 접속 제한 10초보다 짧아서 발생했다. 제품 timeout을 단축하지 않고 검사 허용 시간만 15초로 정정했다.

독립 검토는 최초에 송신 중 disconnect 경계를 거절했다. 새 회귀 테스트가 `RuntimeError: Cannot call "send" once a close message has been sent.`로 실패(1 failed, 23 deselected)하는 것을 확인했다. 두 종료 분기 모두 `client_state`와 `application_state`가 CONNECTED인지 검사하도록 수정한 뒤 같은 테스트가 1 passed, 23 deselected로 전환됐다. 이 한 건은 의도적으로 ASGI send 경계에 OSError를 주입하며, 실제 Starlette 상태 전이와 실제 echo upstream을 사용한다. 해당 보완 이후 독립 검토는 APPROVE다.

### 최종 전체 회귀·정적 검사·빌드

| 검사 | 결과 |
|---|---|
| 격리 `pytest tests/ -q --tb=short -m 'not slow and not benchmark'` | **4827 passed, 6 skipped, 19 deselected in 115.35s**, exit 0 |
| 집중/실제 wire | **28 passed in 11.37s**, exit 0; 위 전체 회귀에도 포함되므로 합산하지 않는다 |
| 변경 4파일 `ruff check` | All checks passed, exit 0 |
| 변경 4파일 `ruff format --check` | 4 files already formatted, exit 0 |
| 변경 4파일 fresh `basedpyright` CLI | 0 errors, 0 warnings, 0 notes, exit 0 |
| `git diff --check` | exit 0 |
| 격리 `uv build --wheel --out-dir /tmp/agk-f01.I58IIe/dist-final` | `antigravity_k-0.1.0-py3-none-any.whl` 빌드 성공, exit 0; 새 transport 모듈 포함 확인 |
| 독립 F01 소스/테스트 경계 검토 | APPROVE; 실행 시험을 대신하는 승인이 아님 |

회귀의 정확한 실행은 격리 worktree에서 원본 `.venv/bin/python -m pytest tests/ -q --tb=short -m 'not slow and not benchmark'`였다. 비교용 중간 회귀는 4826 passed였고, 최종은 send-side 테스트를 포함한 4827 passed다. slow/benchmark 19건과 skip 6건을 통과로 세지 않는다. 대시보드 브라우저 전체 E2E와 선택적 MLX/finetune 조합은 이번 수정에서 다시 실행하지 않았다.

진단 도구 한계: 장기 실행 중인 편집기 LSP는 새 파일을 workspace symbol로 찾으면서도 import 위치에 `reportMissingImports`를 잔류 표시했다. 서버 재시작 도구는 제공되지 않아 사용자 설정/공유 프로세스를 변경하지 않았다. **fresh CLI basedpyright 0/0, 실제 import/전체 회귀/wheel 포함 확인**을 새 프로세스의 검증 근거로 사용한다. 편집기 LSP 표시까지 깨끗하다고 주장하지 않는다.

### 검증한 파일 지문 (SHA-256)

```text
77b7f6abd8b8281295a56e08e55968eeb33450ffad5a51eb2a19c645db8b00a1  src/antigravity_k/api/routes/workspace_services.py
9b05c02487f4e19dd8acd1606d49e8bfc0a578db8801857996843fc7cb989578  src/antigravity_k/api/routes/workspace_websocket.py
2a5c3e1d38fbb95d2c0cf88adf2377db24a82548358cf92351fbf87a728bc629  tests/test_workspace_websocket.py
ce12ae8bc93fb86a481e4e5b580c65665caa2bf5198ebc27cfba164a7ce4a72f  tests/test_workspace_websocket_live.py
```

독립 검토도 동일 HEAD와 위 4개 지문에 묶여 있다. 이 파일들이 변경되면 기존 PASS/APPROVE를 자동 재사용하지 않는다.

## 실행 환경

macOS arm64, Python 3.13.12. 기존 `.venv`를 `--no-sync`로 사용하여 lock/설치 구성을 변경하지 않았다. FastAPI 0.136.3, Starlette 1.1.0, websockets 16.0, AnyIO 4.13.0, Uvicorn 0.48.0, pytest 8.4.2, ChromaDB 1.5.9가 설치된 환경이다. 이전 base+dev-only QA와 설치 조건이 다르므로 과거의 ChromaDB 미설치 실패를 해결했다는 증거로 삼지 않는다.

전체 회귀/빌드는 `/tmp/agk-f01.I58IIe/repo`의 detached HEAD에 이 작업의 제품/테스트 4개 파일만 복사해 실행했다. 해당 임시 경로는 검증 후 정리하므로 재사용하지 않는다.

## 보존 증거 및 정리

- [최종 집중/wire 로그](../../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/focused-wire-final.log)
- [최종 전체 회귀 로그](../../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/regression-final.log)
- [최종 정적 검사 로그](../../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/static-final.log)
- [최종 wheel 빌드 로그](../../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/build-final.log)
- [독립 경계 검토](../../../../.omo/evidence/f01-boundary-gate-review.md)

원문 로그는 ignored 로컬 자료다. 이 문서에는 핵심 결과·명령·지문을 직접 보존하여 raw artifact가 없는 다른 에이전트도 재실행할 수 있도록 했다. 테스트는 ephemeral 메모리 자격 증명만 사용하며 실제 계정 비밀값을 기록하지 않았다. 임시 debug journal은 내용을 이 문서에 옮긴 뒤 제거하고 그 전용 exclude 항목도 복구한다. 임시 worktree는 제거하고 남은 task 전용 임시 폴더는 휴지통으로 이동한다. 원본 사용자 변경·설정·기존 QA 자료는 그대로 둔다.

## 다음 에이전트의 검증 명령

루트에서 실행할 집중 검사와 static gate:

```bash
uv run --no-sync pytest tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py -q -s --tb=short
uv run --no-sync ruff check src/antigravity_k/api/routes/workspace_services.py src/antigravity_k/api/routes/workspace_websocket.py tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py
uv run --no-sync ruff format --check src/antigravity_k/api/routes/workspace_services.py src/antigravity_k/api/routes/workspace_websocket.py tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py
uv run --no-sync basedpyright src/antigravity_k/api/routes/workspace_services.py src/antigravity_k/api/routes/workspace_websocket.py tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py
git diff --check
```

전체 회귀와 `uv build --wheel --out-dir <새 임시 출력 경로>`는 새 격리 checkout에서 수행한다. 테스트는 3.12+ Python 및 manifest의 dev 의존성이 필요하며, 전체 suite의 optional extras 조건을 별도로 기록한다. upstream과 API 모두 임의 포트를 사용하고 context 종료 시 server shutdown/join을 수행한다.

## 한계 / 다음 우선순위

- F01의 **기존 공통 인증 누락**이 수정 대상이다. 공유 PIN 기반 앱 전체 접근 권한 모델은 그대로다. Origin allowlist와 서비스별/프로젝트별 ACL은 설계·검증이 필요한 별도 강화 항목으로 남긴다. 해당 항목을 통과했다고 간주하지 않는다.
- TLS termination, 외부 reverse proxy, 실제 운영 upstream, WebSocket 업무 subprotocol negotiation은 이번에 검증하지 않았다. 기존 relay도 업무 subprotocol 전달은 지원하지 않았다.
- query 자격 증명은 앱 inbound access log에 남을 수 있다. 지원 클라이언트에서는 기존 bearer subprotocol 사용을 고려하고, 운영 proxy 로그 정책은 별도 점검한다.
- 다른 P1/P2는 미수정이다. 다음 최우선은 F02/F07 Vault 파일/Git 트랜잭션이며 인수인계 계획에 안전한 재현 절차가 있다.
- 커밋·배포하지 않았다. 향후 커밋에는 제품 2파일+테스트 2파일+관련 문서만 포함하고 사용자 benchmark 변경은 포함하지 않는다.

## 롤백

제품 두 파일과 테스트 두 파일은 한 논리적 변경이다. 후속 작업이 겹치지 않은 경우에만 이 수정의 diff를 검토해 해당 hunk만 역적용한다. 향후 별도 원자적 commit으로 저장됐다면 정확한 commit만 revert한다. `git reset --hard`, 전체 index 초기화, 사용자 파일 복원은 금지한다. 롤백하면 인증 우회가 재발하므로 Workspace 프록시의 외부 노출을 중단한 상태에서 처리해야 한다.
