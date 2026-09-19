# CR-04 — API shell 실행·승인 경계 (운영 계약)

`POST /api/agent/tools/shell/run`은 이제 **요청이 들어온 시점에 확정한 실행 root**와
**현재 요청의 기존 권한 모드**로 명령을 판단하고, CR-03의 제한 읽기 경계를 그대로
재사용한다. 이 문서는 배포·운영·보안 검토가 기대해야 하는 계약과, 아직 닫히지 않은
잔여 위험을 고정한다.

## 1. 실행 전 결정 (fail-closed)

| 상황 | HTTP | `error` | 자식 프로세스 실행 |
| --- | --- | --- | --- |
| 인증 필요(PIN 설정) + 토큰 없음 | 401 | (기존 auth 계약) | **0회** |
| 실행 모드가 도구 차단(Plan 등) | 403 | `shell_policy_denied` | **0회** |
| 권한 모드 ASK(읽기 전용) | 403 | `shell_approval_required` | **0회** |
| 권한 모드 DENY(위험 명령·경계 밖 cwd) | 403 | `shell_policy_denied` | **0회** |
| OS sandbox 비활성/backend 없음 | 503 | `sandbox_unavailable` | **0회** |
| ALLOW + 실행 성공 | 200 | — | 1회 |
| ALLOW + 명령이 비정상 종료 | 200 | — (`ok=false`, `returncode`) | 1회 |
| ALLOW + 제한 시간 초과 | 504 | `shell_timeout` | 1회(종료됨) |
| 예상 밖 내부 오류 | 500 | (일반 오류 본문) | — |

* **승격 없음**: 이 엔드포인트에는 승인 workflow가 없으므로 ASK는 allow로 올리지 않는다.
  ASK를 실제 승인 flow로 연결하는 작업은 별도 명세가 필요하다(계획 CR-04 명시).
* **raw 폴백 없음**: `security.sandbox_enabled=false`이거나 정책 생성/backend가 실패하면
  host shell로 대체하지 않고 503으로 거부한다(`require_sandbox=True`).
* **wire 어휘 고정**: `src/antigravity_k/api/contracts/shell.py`의
  `SHELL_ERROR_HTTP_STATUS`가 유일한 진실이며 테스트가 이를 freeze한다.

## 2. 실행 root 고정 규칙

`_shell_request_root()`가 요청 시작 시 1회 root를 확정하고, 그 뒤에는 **전역 active
project를 다시 읽지 않는다**.

우선순위:

1. 이미 바인딩된 ARC-01 요청 실행 컨텍스트(chat/task가 실행한 경우)
2. 요청 본문의 `project_id`(ARC-01 resolution)
3. `X-AGK-Session-Id` 헤더의 session active-project binding
4. 그 외 구형 클라이언트 → 서버 기본 `config.paths.project_root`

`cwd`는 확정된 root 하위여야 하며, 벗어나면 실행 전에 403이다. 검사 경로와 실행
경로는 **같은 root**를 쓴다(`project_root=root`, `cwd=<root 안>`).

## 3. 유출 차단

* 부모 `os.environ`을 상속하지 않는다(`_minimal_child_env`): 자식 env는
  `PATH`, `HOME`, `TMPDIR`, `PYTHONDONTWRITEBYTECODE` 4개뿐이고 `HOME`/`TMPDIR`는
  실행 root 안쪽 전용 디렉터리다. 모델 provider 키·서버 PIN/token secret이
  자식 셸로 넘어가지 않는다.
* 오류 응답에 내부 경로·실행 환경을 넣지 않는다. sandbox 실패 원문은 서버 로그에만
  남기고 공개 `detail`은 고정 문장이다. `except (OSError, ValueError)`의 500도
  `str(e)` 대신 고정 문장을 반환한다.
* 읽기 경계는 CR-03 소유 `sandbox.py`를 그대로 쓴다(`restrict_reads=True`,
  `read_allow_paths=[cwd, *_python_runtime_read_paths()]`) — workspace 밖 symlink target,
  다른 프로세스의 임시 파일은 읽히지 않는다.

## 4. 응답 모양

정상 응답은 기존 키(`ok`, `stdout`, `stderr`, `returncode`, `sandboxed`,
`output_truncated`)를 그대로 유지하고 `timed_out: bool`을 **추가**한다(하위 호환).
명령 실패(`exit 3`)는 정책 오류가 아니라 `ok=false` 결과로 돌아온다.

## 5. 잔여 위험 / 지원 범위

* **seatbelt 실측은 macOS만** — Linux/Docker backend에서 이 경계는 mock/코드 경로로만
  검증됐다. Docker는 bind mount가 읽기 경계이며, 해당 행은 검증 대기다.
* `@requires_seatbelt` 표시 테스트는 비-macOS에서 skip된다. skip 통과를 실측으로
  승격하지 않는다.
* CR-03과 동일하게 조상 디렉터리는 `literal`(이름만) 허용이므로 상위 디렉터리 이름은
  child에서 보일 수 있다(파일 내용·형제 subtree는 열리지 않는다).
* **API 키의 브라우저 영속 제거**는 CR-05 소관이다 — 이 경계는 서버측 실행 경계만
  다룬다.

## 6. 배포 시 확인

```bash
# 1) 설정: sandbox가 켜져 있어야 shell이 동작한다(raw 폴백 없음)
#    security.sandbox_enabled=true

# 2) 회귀: 경계·소비자 확인
uv run --no-sync pytest tests/test_cr04_shell_api_boundary.py \
                      tests/test_cr03_sandbox_read_boundary.py \
                      tests/test_agent_tools_api.py -q

# 3) 전체 게이트
uv run --no-sync pytest tests/ -q
uv run --no-sync ruff check src/ tests/ && uv run --no-sync mypy src/
```

롤백: 이 변경은 단일 라우트(`run_shell`)와 신규 계약 파일에 국한된다. 되돌리면
`mode="auto-pilot"` 고정·env 상속·raw 폴백이 함께 복귀하므로 **되돌리지 않는 것을
권장**한다(되돌림은 S01 재개방과 동일하다).
