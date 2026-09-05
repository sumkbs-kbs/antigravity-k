# Grok Bot 0.18 Reconstructed · Paseo 벤치마크 검토

검토일: 2026-09-01

## 기준 소스

- Grok Bot 0.18 reconstructed: commit [`a9f633e09d49a85829b8236331b9e21f7e612634`](https://github.com/b-nnett/grok-bot-0.18-reconstructed/tree/a9f633e09d49a85829b8236331b9e21f7e612634)
- Paseo: commit [`ecec33265e68a71c68f49ef7c330cf43aa1d37c8`](https://github.com/getpaseo/paseo/tree/ecec33265e68a71c68f49ef7c330cf43aa1d37c8)

검토는 README만 비교하지 않고 런타임, 공급자 어댑터, 샌드박스, 이벤트 전송, 서비스 프록시, 보안 문서와 관련 테스트를 함께 확인했다. 외부 구현을 복사하지 않고 기능 계약과 운영 원칙만 독립적으로 반영한다.

## 구현 근거

Grok Bot의 다중 공급자 경계는 [`createCoordinatorInferenceRouter`](https://github.com/b-nnett/grok-bot-0.18-reconstructed/blob/a9f633e09d49a85829b8236331b9e21f7e612634/source/node-agent-coordinator/inference-router.ts), 공급자별 사용량 기록은 [`provider-session.ts`](https://github.com/b-nnett/grok-bot-0.18-reconstructed/blob/a9f633e09d49a85829b8236331b9e21f7e612634/source/host/extensions/inference/provider-session.ts), 로컬 실행 격리는 [`local-docker-host-connector.ts`](https://github.com/b-nnett/grok-bot-0.18-reconstructed/blob/a9f633e09d49a85829b8236331b9e21f7e612634/source/electron-main/box/local-docker-host-connector.ts), 통합 상태 투영은 [`desktop-health-forwarder.ts`](https://github.com/b-nnett/grok-bot-0.18-reconstructed/blob/a9f633e09d49a85829b8236331b9e21f7e612634/source/host/extensions/telemetry/desktop-health-forwarder.ts)에서 확인했다.

Paseo의 재연결 타임라인은 [`viewed-timeline-sync.ts`](https://github.com/getpaseo/paseo/blob/ecec33265e68a71c68f49ef7c330cf43aa1d37c8/packages/app/src/timeline/viewed-timeline-sync.ts), 작업공간 라우팅과 포트 수명주기는 [`service-proxy.ts`](https://github.com/getpaseo/paseo/blob/ecec33265e68a71c68f49ef7c330cf43aa1d37c8/packages/server/src/server/service-proxy.ts)와 [`workspace-service-port-registry.ts`](https://github.com/getpaseo/paseo/blob/ecec33265e68a71c68f49ef7c330cf43aa1d37c8/packages/server/src/server/workspace-service-port-registry.ts), 원격 연결의 암호 경계는 [`crypto.ts`](https://github.com/getpaseo/paseo/blob/ecec33265e68a71c68f49ef7c330cf43aa1d37c8/packages/relay/src/crypto.ts)와 [`daemon-keypair.ts`](https://github.com/getpaseo/paseo/blob/ecec33265e68a71c68f49ef7c330cf43aa1d37c8/packages/server/src/server/daemon-keypair.ts)에서 확인했다.

## 기능 비교와 판단

| 영역 | 외부 저장소에서 확인한 강점 | Ssak-Ai 현재 상태 | 판단 |
| --- | --- | --- | --- |
| 다중 공급자 라우팅 | Grok Bot은 Cursor, Claude Code, Codex, OpenRouter를 한 추론 라우터에서 선택하고 공급자별 도구 실행을 보존한다. | 모델 레지스트리, 공급자 capability, fallback, 로컬 모델 탐색과 사용량 기록이 이미 있다. | 중복 구현하지 않고 공급자 계약 테스트를 강화한다. |
| 로컬 샌드박스 | Grok Bot은 loopback 바인딩, 읽기 전용 content-addressed mount, 연결 전 검증을 결합한다. | Docker/macOS 샌드박스, fail-closed 격리 테스트, 보호 경로와 네트워크 정책이 이미 있다. | artifact hash manifest와 실행 증거 연결을 후속 반영한다. |
| 증거 기반 재구성 | Grok Bot은 원본·변환 renderer hash와 artifact provenance를 검증한다. | RAG provenance와 감사 로그는 있으나 UI/build artifact까지 이어지는 단일 증거 체인은 부족하다. | 빌드 provenance manifest를 P1 후보로 둔다. |
| 작업 수명주기 | Paseo는 생성, 실행, 중지, 재개, 보관과 공급자 독립 수명주기를 제공한다. | 제출, 상태, 취소, 재개, fork, 보관, 일정 실행이 이미 있다. | 중복 구현하지 않는다. |
| 타임라인 동기화 | Paseo는 live stream의 즉시성과 cursor 기반 authoritative fetch를 결합하고 gap을 검출한다. | 순번 이벤트, REST replay, SSE `Last-Event-ID`, WebSocket은 있으나 REST 응답이 다음 페이지 존재 여부를 알려주지 않았다. | `has_more`와 client replica(dedup, gap replay, snapshot boundary, local cache compaction)를 반영했다. |
| 작업공간 서비스 프록시 | Paseo는 서비스·브랜치·프로젝트 기반 DNS-safe hostname과 포트 라우팅을 제공한다. | IDE 프록시 외에 작업공간별 서비스 레지스트리와 HTTP/WebSocket 전달 계층을 추가했다. | health/start-stop 프로세스 연결과 forwarded-header 정책을 계속 확장한다. |
| 원격 연결 보안 | Paseo는 QR pairing과 종단 간 암호화 relay를 제공한다. | X25519/HKDF/ChaCha20-Poly1305 기반 pairing·relay, 회전·폐기·replay 방지까지 구현했다. | 배포 시 TLS와 다중 인스턴스 외부 저장소를 운영 설정으로 확정한다. |
| 실행 중 steering | Paseo는 활성 turn에 native steer RPC를 보낸다. | `queued_replay` 모드로 활성 provider turn 경계에 지시를 재주입하고, 요청·적용을 authoritative task event sequence에 기록한다. | provider별 native RPC가 없어도 동일한 API/event 계약으로 안전하게 확장한다. |

## 이번 반영: 누락 없는 이벤트 catch-up

`GET /api/tasks/{task_id}/events`는 요청한 `limit`보다 한 건 더 조회한다. 응답에는 요청 개수만 노출하고 추가 이벤트가 있으면 `has_more: true`를 반환한다.

클라이언트 계약은 다음과 같다.

1. `events`를 순서대로 적용한다.
2. 다음 요청의 `after_sequence`에는 현재 응답의 `last_sequence`를 사용한다.
3. `has_more`가 참인 동안 즉시 다음 페이지를 가져온다.
4. REST catch-up 이후 SSE 또는 WebSocket live stream으로 전환한다.

빈 페이지에서는 `last_sequence`가 요청한 `after_sequence`를 유지하며 `has_more`는 거짓이다. 이 계약은 기존 클라이언트의 `events`와 `last_sequence` 의미를 변경하지 않고 gap-free catch-up 가능 여부만 명시한다.

대시보드는 응답을 Zod로 파싱하고 `has_more`가 참이면 `last_sequence`를 다음 `after_sequence`로 사용해 즉시 다음 페이지를 요청한다. 모든 authoritative REST 페이지를 합친 뒤에만 SSE live stream을 시작한다. 서버가 `has_more: true`를 반환하면서 커서를 전진시키지 않으면 무한 재요청 대신 typed transport error로 중단한다.

## 이번 반영: 작업공간 서비스 레지스트리와 결정적 프록시

`WorkspaceServiceRegistry`는 서비스·브랜치·프로젝트 조합을 `<service>--<branch>--<project>.localhost`로 정규화하고, 63자 DNS label 제한을 넘으면 SHA-256 접미사를 붙여 결정성을 유지한다. 같은 호스트명에 다른 포트나 대상이 등록되면 충돌(409)로 거부한다. 프록시 대상은 SSRF 방지를 위해 `localhost` 또는 loopback IP만 허용한다.

`/api/workspace/services`에서 등록·목록·상태 변경·삭제를 제공하며, 등록 응답에는 HTTP와 WebSocket 진입점이 함께 포함된다. `/proxy/{path}`는 hop-by-hop 헤더와 원본 `Host`를 제거하고 `X-Forwarded-*` 및 작업공간 메타데이터를 주입해 스트리밍 HTTP 응답을 전달한다. `/ws/{path}`는 동일한 헤더 정책으로 양방향 WebSocket 프레임을 전달한다. `starting`, `ready`, `stopped`, `failed` 상태 중 `ready`만 프록시를 허용해 수명주기와 라우팅을 분리하지 않는다.

등록 요청에 `command`를 지정하면 런타임 어댑터가 로컬 subprocess를 직접 관리한다. `POST /{hostname}/start`는 PID를 추적하며 `ready`로 전이하고, `POST /{hostname}/stop`은 terminate 후 필요할 때 kill로 정리한다. `GET /{hostname}/health`는 프로세스 생존 여부를 authoritative registry 상태와 함께 반환하고, 관리 프로세스가 예기치 않게 종료되면 `failed`로 전이한다.

## 이번 반영: active-turn steering 계약

`POST /api/tasks/{task_id}/steer`는 실행 중인 태스크에 지시를 FIFO로 접수한다. 응답의 `mode`는 현재 provider 독립 구현인 `queued_replay`이며, 런너는 provider 스트림 청크 경계에서 큐를 drain해 다음 호출의 메시지에 `[Active-turn steering]` 지시를 추가한다. 요청과 적용은 각각 `task.steering.requested`, `task.steering.applied` 이벤트로 기록되어 REST/SSE/WebSocket replay에서 순서를 잃지 않는다.

provider capability snapshot에도 `active_turn_steering: queued_replay`를 노출해 향후 native steer RPC를 지원하는 공급자는 같은 API 계약 아래에서 구현을 교체할 수 있다. 태스크 소유자 검사는 기존 task API와 동일하게 적용하며, 비활성·종료 태스크는 404로 거부한다.

## 이번 반영: artifact provenance와 task 감사 이벤트 연결

기존 SHA-256 manifest 생성기(`artifact_provenance.py`)에 결정적 manifest digest와 `record_manifest_event` 어댑터를 추가했다. 인증된 `POST /api/tasks/{task_id}/provenance`는 서버 작업공간의 상대 경로만 받아 build, UI bundle, sandbox mount 또는 workspace 산출물을 해시하고, digest·파일 수·sequence를 응답한다. 동시에 전체 manifest가 `artifact.provenance.recorded` task event payload에 저장되어 REST/SSE/WebSocket replay에서 감사 증거와 산출물 hash를 함께 재현할 수 있다.

로컬 `make build-provenance`와 `make dashboard-build-provenance`는 각각 Python 배포물과 Vite bundle을 만든 직후 manifest를 생성·검증한다. CI의 package build, dashboard build, GitHub Pages 배포 및 release workflow도 동일한 gate를 실행하고 manifest를 업로드하므로, 업로드·배포 직전 산출물 변조는 non-zero exit로 차단된다.

CI 변수 `AGK_PROVENANCE_API_URL`, `AGK_PROVENANCE_TASK_ID`와 secret
`AGK_PROVENANCE_PIN`을 설정하면 `scripts/publish_artifact_provenance.sh`가
검증된 manifest를 `POST /api/tasks/{task_id}/provenance/manifest`로 전송한다.
서버는 manifest digest와 전체 파일 목록을 `artifact.provenance.recorded` 이벤트로
기록하므로 배포 task timeline에서 CI 산출물을 재현할 수 있다.

`AGK_PROVENANCE_TASK_ID`가 비어 있으면 workflow가
`POST /api/tasks/provenance/register`를 idempotency key(`github-{run_id}`)와 함께
호출해 실행 없는 provenance task를 만들고, 반환된 ID를 다음 단계에 주입한다.
따라서 재시도는 동일 task timeline에 합쳐지고 agent 실행을 부수적으로 시작하지 않는다.

## 이번 반영: QR pairing과 종단 간 암호화 relay

Paseo의 원격 연결 경계를 독립 구현한 `PairingManager`는 X25519 키 교환과
HKDF-SHA256으로 pairing별 세션 키를 만들고 ChaCha20-Poly1305로 relay envelope를
인증·암호화한다. QR payload에는 pairing ID, 일회성 8자리 코드, 서버 공개키와 만료
시각만 포함하며 서버에는 코드 digest만 보관한다. pairing 완료 후 코드 재사용은
거부되고, 회전은 key epoch을 증가시키며 대기열을 비우고, 폐기는 키와 대기열을
즉시 제거한다. relay는 복호화 검증을 통과한 opaque envelope만 bounded FIFO에
넣고 poll 시 순서대로 반환한다.

HTTP 계약은 인증된 control plane의 `POST /api/remote/pairing`(QR 발급),
`POST /api/remote/pairing/rotate`, `POST /api/remote/pairing/revoke`와 원격
bootstrap의 공개 `POST /api/remote/pairing/complete`, `POST
/api/remote/pairing/relay`, `POST /api/remote/pairing/relay/poll`로 분리했다.
공개 relay 경로는 평문을 받지 않으며, 모든 실패는 typed error code와 상태 코드로
매핑되고 pairing lifecycle은 감사 이벤트로 기록된다.

## 검증 결과

- 변경 Python 파일 `basedpyright`: 0 errors, 0 warnings
- 변경 파일 `ruff`와 `py_compile`: 통과
- 전체 pytest: 4,789 passed, 6 skipped; 별도 전체 재실행에서 기존 `tests/test_ci_tools.py::TestAutoLintToolInit::test_execute_passes_linter_arguments_without_shell_interpolation`가 worktree cleanup 호출 순서에 따라 1회 flaky 실패했으나 단독·파일 전체 재실행은 PASS
- 서비스 수명주기 통합 테스트: 실제 Python subprocess start/health/stop과 미등록 command 오류 경로 PASS
- 대시보드 전체 Vitest: 596 passed
- 대시보드 `tsc`, 변경 파일 ESLint, 프로덕션 Vite build: 통과
- 클라이언트 회귀 테스트: 첫 페이지의 `has_more=true`를 파싱하고 `after_sequence=501`로 다음 페이지를 요청해 `[501, 502]`를 반환
- 실제 ASGI HTTP 왕복: 첫 페이지 `[1, 2] / has_more=true`, 다음 페이지 `[3] / has_more=false`
- 실제 로컬 업스트림 왕복: 작업공간 서비스 HTTP 프록시와 WebSocket echo 모두 PASS
- 실제 Chromium E2E: 7 passed; 375/768/1280px에서 `0 → 3 → 5` catch-up과 live sequence gap(`2 → 4`, authoritative replay `after_sequence=2`) 복구, 불완전 terminal replay 차단, 재연결·fork·승인 흐름, Axe 0건, 수평 overflow 0을 확인
- dashboard Vitest: 596 passed; `taskEventReplica`의 sequence dedup, typed conflict, gap recovery, snapshot boundary, localStorage round-trip을 단위 검증
- 실제 `make dashboard-build-provenance`: Vite production build, 40개 파일 manifest 생성, `valid=true` 검증 PASS
- 임시 bundle 변조 후 provenance verify: `size_mismatch`를 반환하고 exit code 1로 gate 차단 PASS
- 실제 `make build-provenance`: wheel/sdist 생성, 3개 파일 manifest 생성, `valid=true` 검증 PASS
- provenance task 등록→동일 idempotency 재등록→manifest publish: task 등록 1건과 provenance event 1건의 timeline PASS
- 승인 UI: 기본 5.15:1·hover 6.46:1 대비, 좁은 화면에서도 대상 파일명 전체 표시를 독립 시각 리뷰 2회 PASS로 확인
- TypeScript no-excuse 보조 스크립트는 TypeScript 7의 `unstable/*` API를 요구하지만 현재 대시보드는 TypeScript 5.9.3이어서 실행할 수 없었다. 같은 변경 파일은 `tsc`와 ESLint에서 오류 없이 통과했다.

## 후속 도입 순서

### P1

1. CI task registration은 구현 완료. 다음 단계는 배포 환경에서 provenance task를 생성할 API URL과 PIN secret을 표준 운영 설정으로 배포하는 것이다.

### P2

1. 종단 간 암호화 relay와 QR pairing 구현 완료: X25519/HKDF/ChaCha20-Poly1305,
   일회성 코드, 만료·회전·폐기·bounded FIFO와 공개 bootstrap API를 제공한다.
2. timeline client replica는 구현 완료: `taskEventReplica.ts`가 sequence dedup/conflict 검출, contiguous cursor와 gap 범위, snapshot boundary 기반 compaction, Zod-검증 localStorage cache를 제공하고 `useTaskExecutionEvents`가 live gap을 authoritative replay로 자동 복구한다.

## 보류·비채택 사유

- Grok Bot 저장소의 [NOTICE](https://github.com/b-nnett/grok-bot-0.18-reconstructed/blob/a9f633e09d49a85829b8236331b9e21f7e612634/NOTICE.md)는 원본 소스 라이선스를 부여하지 않는다고 명시한다. 따라서 코드, renderer, 설치 artifact는 가져오지 않는다.
- Paseo는 Apache-2.0이지만 현재 변경은 작은 API 계약이라 의존성이나 소스 복사 없이 독립 구현했다.
- 현재 고정 8080 IDE proxy 위에 결정적 hostname만 얹는 안은 worktree별 서비스 격리를 제공하지 못하므로 채택하지 않았다.
