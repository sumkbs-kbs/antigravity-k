# RP-01 implementation notes (attempt 001)

## 기존 재현 (수정 전, SHA 8794aae)

`unified_agent.py`의 `_run_code`(구 210라인)와 `_run_code_consistent`(구 276라인)이
`subprocess.run([sys.executable, "-m", "pytest", ...], env={**os.environ, ...})`로
호스트 프로세스 권한 그대로 사용자/모델 코드를 실행했다 (FR-01).

## 원인

- 두 경로 모두 표준 subprocess 직접 호출이었고 `run_sandboxed_argv`를 우회했다.
- `os.environ` 전체 상속으로 서버 시크릿이 테스트 코드에 노출됐다.
- 기존 seatbelt 프로파일은 `(allow file-read*)`로 사용자 HOME 전체를 읽게 했다.

## 수정한 계약

1. `engine/unified_agent.py`
   - 신규 `_run_test_suite(workdir)`: pytest argv를 `run_sandboxed_argv`로만 실행.
   - 최소 env(인터프리터 bin PATH, 전용 HOME/TMPDIR, PYTHONPATH,
     PYTHONDONTWRITEBYTECODE, PYTEST_DISABLE_PLUGIN_AUTOLOAD)만 구성.
   - sandbox error/timeout/not-sandboxed는 모두 실패로 반영되며 host fallback 없음.
   - `_run_code`, `_run_code_consistent` 양쪽이 이 helper를 사용.
2. `engine/sandbox.py`
   - `run_sandboxed_argv`: `restrict_reads=True` + python 런타임 read allow
     (sys.prefix, sys.base_prefix, interpreter bin) + `extra_read_paths` 지원.
   - `env=None`이면 `_minimal_child_env`로 최소 환경 구성(부모 os.environ 미상속).
   - `SandboxRunner`: `restrict_reads`, `read_allow_paths` 옵션 추가,
     `project_root`/allow 경로를 realpath로 canonicalize(`/var` → `/private/var`
     firmlink로 인한 subpath 불일치 수정).
   - restrict 프로파일: `(allow file-read*)` 후 사용자 트리(`/Users`, HOME 부모)와
     `/tmp`, `/private/tmp`, `/var/tmp`, `/private/var/tmp`를 deny하고 root/런타임
     경로만 재허용. 쓰기는 root + `/dev/null`만.
3. `engine/tdd_engine.py` 등 기존 호출자는 변경하지 않았으나, PATH 기본값에 인터프리터
   bin을 포함해 `python3`/`pytest` 이름 기반 호출이 계속 프로젝트 환경에서 resolve되도록 함.

## macOS 26 seatbelt 제약 (실험 근거)

- subpath 범위의 좁은 `(allow file-read*)`는 인터프리터 로딩 단계에서 SIGABRT(rc 134)를
  유발한다(echo/python 모두, Cryptex/Preboot 경로 허용 후에도 동일).
- 전체 읽기 허용 + 이후 deny + 재허용 나열 방식은 정상 동작한다(규칙 순서 우선).
- 결과: 사용자 트리 읽기 차단, 공유 /tmp 읽기/쓰기 차단, 쓰기 root 한정은 실측으로
  확보했으나, 시스템 파일(/etc 등)과 동일 사용자의 /var/folders 읽기는 여전히 허용된다.
  이는 백엔드 제약이며 RP-14 독립 보안 검토에서 한계로 명시한다.

## 영향 범위

- `run_sandboxed_argv` 호출자: tdd_engine, tdd_verifier, best_of_n_verifier,
  speculative_branching — 회귀 67 passed.
- `SandboxRunner(enabled=False)` 기존 동작 불변(restrict 옵션 기본 False).

## 실행한 검증

- `uv run --no-sync pytest -q tests/test_agent_ask_api.py tests/test_unified_agent.py
  tests/test_sandbox.py tests/test_fr01_agent_execution_isolation.py`
  → 42 passed (logs/regression-run.txt, exit 0)
- `uv run --no-sync pytest -q tests/test_tdd_engine.py tests/test_best_of_n_verifier.py
  tests/test_tdd_verifier.py tests/test_speculative_branching.py` → 67 passed
- ruff check/format: 통과
- 수동 실측: sentinel 읽기/쓰기 차단, secret 미노출, egress 차단, timeout 그룹 종료
  (commands.jsonl 참조)

## 대안 / 제한

- 좁은 read subpath 프로파일이 불가능한 환경 제약은 macOS 26 실험으로 확정.
  Docker backend(Linux)에서는 도구별 read 정책 재검토가 필요하며 본 세션에서 실측하지 못했다.
- R01-10(독립 보안 리뷰)은 RP-14에서 수행 예정.
