---
title: Sandbox 읽기 경계와 예외 목록 (CR-03)
status: implemented (REVIEW — 독립 보안 검토 미배정)
date: 2026-09-12
owner: buffy
plan: docs/16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md (CR-03)
evidence: .omo/evidence/commercial-reliability/CR-03/attempt-001/
---

# Sandbox 읽기 경계 (macOS seatbelt)

에이전트가 실행하는 모델 생성 코드/셸은 `run_sandboxed_argv`를 통과하며, 읽기 경계는
`SandboxRunner(restrict_reads=True)`가 만드는 seatbelt 프로파일이 담당한다.

## 1. 경계의 형태

```
(deny default)
(allow process-fork) (allow process-exec) (allow signal (target self)) (allow sysctl-read)
(allow file-read*)                                  ; 기본 읽기
(deny file-read* (subpath "<민감 트리>"))             ; 아래 2절
(allow file-read* (literal "<workspace의 조상 디렉터리>"))   ; 자기 자신만(하위 트리 아님)
(allow file-read* (literal|subpath "<workspace|런타임|호출자 경로>"))  ; 재허용
(allow file-write* (subpath "<workspace>")) (allow file-write* (literal "/dev/null"))
(deny network*)                                     ; network=none일 때
```

seatelbelt는 같은 구체성에서 **나중 규칙을 우선**하므로 deny 뒤의 allow가 재허용이다.
경계는 자식 프로세스에 그대로 상속된다.

### 왜 "허용 목록(positive allowlist)"이 아닌가

계획 CR-03은 `restrict_reads`를 허용 목록으로 구현하라고 요구한다. 이번 후보에서
`(deny default)` + 좁은 read allow 목록은 macOS 26.6.2(arm64)에서 **실패**한다는 것을
실측했다(`repro/cr03_probe_allowlist.py`, `repro/cr03_matrix_probe.py`,
`repro/cr03_bisect_allowlist.py`):

| 후보 프로파일 | 결과 |
|---|---|
| `(deny default)` + `(allow file-read*)` | CPython 부팅 성공 |
| `(deny default)` + 전역 metadata + `/usr`,`/System`,`/bin`,`/Library`,`/dev`,`/private/etc`,`/private/var/db`,`/private/var/select`, 런타임 prefix, workspace | **SIGABRT(rc=-6)**, stderr 없음 |
| 동일 후보 + `mach-lookup` | SIGABRT |
| 15개 경로+런타임의 greedy 최소화 | 어떤 경로를 제거해도 실패 → 최소 부분집합을 찾을 수 없음 |

sh 래퍼 유무·env 주입 유무는 결과에 영향이 없었다(같은 행렬 실측). 즉 부팅 단계에서
CPython/dyld가 읽는 경로가 위 목록 밖에 있고, 그 경로를 열거할 수 없었다.
그래서 계획 문구와 실제 플랫폼 동작이 충돌하므로 계획 §1의 절차대로 **decision D-01**에
사유·영향·새 수용 기준을 기록하고, 보안 속성(아래 2·3절)을 실측으로 만족하는
"민감 트리 차단 + 최소 재허용" 경계를 구현했다.

## 2. 항상 차단하는 트리 (`RESTRICTED_DENIED_ROOTS`)

| 경로 | 이유 |
|---|---|
| 사용자 트리(`_user_tree_denied_root()`, 보통 `/Users`) | 다른 계정·홈의 개인 파일 |
| `/tmp`, `/private/tmp` | 공용 임시 파일(다른 프로세스 secret 가능) |
| `/var/tmp`, `/private/var/tmp` | 공용 임시 파일 |
| `/var/folders`, `/private/var/folders` | macOS per-user 임시 트리 — `tempfile.mkdtemp()`/pytest가 쓰는 위치(B02/S02 누출 지점) |

원문 경로와 `realpath`(canonical)를 모두 deny 규칙으로 넣는다. seatbelt는 canonical
경로로 매칭하므로 alias(`/var/folders` ↔ `/private/var/folders`)도 함께 막힌다.

## 3. 다시 여는 것(허용 예외 목록)

| 대상 | 규칙 | 이유 |
|---|---|---|
| 작업 디렉터리(workspace) | literal + subpath | 실행 대상 코드/산출물 |
| 인터프리터 런타임(`_python_runtime_read_paths()`) | literal + subpath | venv/conda가 홈 아래에 있음 — HOME 전체가 아니라 이 prefix만 |
| 호출자 지정 `read_allow_paths` | literal + subpath | `run_sandboxed_argv(extra_read_paths=...)` |
| workspace/런타임/호출자 경로의 **조상 디렉터리** | literal만(subpath 아님) | 경로 해석과 pytest rootdir/패키지 탐색. 하위 트리는 열지 않는다 |
| 그 밖의 시스템 경로 | `(allow file-read*)` 기본값 | `/usr`, `/System`, `/Library`, `/dev` 등 — 개인 데이터가 아님 |

쓰기는 workspace subpath + `/dev/null`만 허용한다(비-restrict 모드의 `/tmp`,
`/var/folders`, `~/.cache` 쓰기 허용은 `restrict_reads=False` 호환 경로에만 남는다).

### 잔여 위험 (문서화된 한계)

1. **이름 수준 메타데이터**: workspace의 조상 디렉터리는 literal로 열리므로, 그 디렉터리의
   entry **이름**은 보일 수 있다(예: 같은 임시 루트의 형제 디렉터리 이름). 내용 읽기는
   거부된다(`tests/test_cr03_sandbox_read_boundary.py::test_ancestor_listing_may_reveal_names_but_not_contents`).
2. **시스템 경로 읽기**: `/usr`, `/System`, `/Library` 등은 계속 읽힌다. 사용자 secret이
   아니라 OS 런타임이므로 경계 대상이 아니다.
3. **Docker backend**: 읽기 경계는 bind mount가 담당한다(host project root만 `/workspace`로
   올라가고 HOME·`/tmp`·`/var/folders`는 컨테이너에서 보이지 않는다). Linux 실측은 이 후보에서
   수행하지 않았으므로 그 지원 행은 **검증 대기**다.
4. **Docker 미설치 + 비-Darwin**: `execute()`는 실행 없이 오류를 반환한다(fail-closed).
5. **`enabled=False`**: `SandboxRunner(enabled=False)`의 raw 실행은 문서화된 호환 모드로 남아
   있다. 모델 코드 경로(`run_sandboxed_argv`)는 `require_sandbox=True`로 이를 거부한다.
   API/tool 호출부의 설정 게이트는 **CR-04**가 소유한다.
6. **power/entitlement**: seatbelt는 프로세스 권한을 낮추는 것이 아니라 파일/네트워크/프로세스
   정책만 제한한다. 커널 취약점·샌드박스 탈출은 이 경계의 범위가 아니다.

## 4. 실측 환경

- macOS 26.6.2 (Darwin 25.0.0), arm64, CPython 3.13.9 (repo venv → miniforge3 3.13)
- 검증: `uv run --no-sync pytest tests/test_cr03_sandbox_read_boundary.py -q` (24건)
- 전체 suite: 5969 passed / 13 skipped
- 재현 스크립트: `.omo/evidence/commercial-reliability/CR-03/attempt-001/repro/`

## 5. 검증 명령

```bash
uv run --no-sync pytest tests/test_cr03_sandbox_read_boundary.py -q
uv run --no-sync python .omo/evidence/commercial-reliability/CR-00/attempt-001/repro/cr00_s02_sandbox_read_leak.py  # read_leaked: false 기대
uv run --no-sync pytest tests/test_fr01_agent_execution_isolation.py tests/test_sandbox_isolation.py -q
```
