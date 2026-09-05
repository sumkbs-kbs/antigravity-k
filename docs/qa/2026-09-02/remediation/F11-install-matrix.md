---
title: F11 선택 의존성/설치 matrix 진행 기록
tags: [qa, dependencies, installation, ci, uv, optional-extras, remediation]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
verification_utc: 2026-09-03T04:25:00Z
---

# F11 진행 기록

이 문서는 작업이 진행되는 동안 실시간으로 갱신한다. 다른 에이전트는 이 문서의 `status`와 “다음 작업”을 먼저 읽고 중복 작업을 피한다.

## 현재 상태

- baseline HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`
- base+dev 격리 환경에서 RED 재현 후 수정까지 완료. 전체 비벤치마크 suite 통과.
- 커밋/푸시/배포 없음.
- `data/benchmark_results.json`과 다른 에이전트/user 변경을 건드리지 않는다.

## 현재 관찰

1. `chromadb`는 `rag` extra에만 존재한다:
   - `pyproject.toml`: `chromadb>=1.5.0,<2.0`
   - `uv.lock`: `chromadb`는 `extra == 'rag'` marker로 설치된다.
2. 현재 로컬 `.venv`에는 `chromadb`가 설치되어 있다. 따라서 현재 환경에서 F11 실패를 곧바로 재현할 수 없으며, 별도 격리 환경이 필요하다.
3. `VectorStore.__init__`은 chromadb 부재를 명확한 `RuntimeError`로 변환한다. 메시지는 `VectorStore requires chromadb but it is unavailable: ...`이다.
4. `MemoryService`는 vector store 초기화를 시도하고, 없으면 keyword-only 동작으로 fallback하는 속성/테스트 구조를 가진다.
5. `tests/test_memory_service.py`에는 chromadb 부재 시 skip/marker가 없다. 특히 `test_adds_knowledge_with_vector_store_still_works`는 `mem.vector_store is not None`을 요구한다.
6. 기존 다른 테스트는 `VectorStore`를 직접 생성하거나 mock/double로 대체한다. 전체 suite를 base+dev에서 실행할 때 optional 경계가 실제로 어디에서 깨지는지 격리 실행으로 확정해야 한다.
7. CI `test` job은 이미 `pip install -e ".[dev,rag]"`를 사용한다. 반면 문서의 재검증 기준은 `uv sync --frozen --extra dev`다. base+dev 실행 계약이 CI와 문서 사이에서 다르다.
8. README 기본 설치는 `dev+rag+mlx`를 안내한다. dev-only 설치도 실제 사용자 경로가 될 수 있으므로 실패하지 않아야 한다.

## 가설

1. **테스트 계약 혼합**: `test_memory_service.py`가 optional vector backend 존재를 기본 전제로 작성되어 dev-only 환경에서 실패한다. 구분 증거는 base+dev 격리 pytest의 exact failure.
2. **의존성 그룹 계약 부재**: dev만으로 전체 test collection을 보장하려는 정책과 rag 전용 테스트를 분리하는 설치 matrix가 없다. 구분 증거는 CI job과 개발 문서의 현재 설치 명령.
3. **런타임 fallback 손상 가능성**: `MemoryService`의 fallback이 아니라 특정 테스트가 vector store 존재를 잘못 assert하고 있을 수 있다. 구분 증거는 소스의 초기화 예외 처리와 base+dev exact failure 대조.

## RED 재현

격리 경로: `/tmp/agk-f11-base.oTeYEj` (HEAD archive, 별도 `.venv`; 원본 worktree 미변경)

```bash
uv sync --locked --extra dev
uv run --no-sync python -c 'import importlib.util; print(importlib.util.find_spec("chromadb"))'
uv run --no-sync pytest tests/test_memory_service.py -q
```

관찰:

- `chromadb=None`
- `1 failed, 34 passed`, exit 1
- 실패: `TestMemoryServiceAddKnowledge::test_adds_knowledge_with_vector_store_still_works`
- 정확한 오류: `assert None is not None`
- 로그에서 제품은 `RuntimeError: VectorStore requires chromadb ... ModuleNotFoundError`를 잡고 “keyword-only mode”로 fallback했다.

해석: 런타임 fallback은 설계대로 동작한다. 결함은 테스트가 optional backend 존재를 기본 전제로 assert한다는 점이다. base+dev 환경의 올바른 기대는 `vector_store is None`이고 keyword-only 동작이 동작하는 것이다.

Evidence:

- [base-dependency-probe.txt](../../../../.omo/evidence/f11-install-matrix/base-dependency-probe.txt)
- [base-memory-service-red.log](../../../../.omo/evidence/f11-install-matrix/base-memory-service-red.log)

## 안전/소유권 지침

- 이번 작업 소유 예상 파일: `tests/test_memory_service.py`, CI 설치/테스트 step, 관련 개발 문서. 필요 시 `pyproject.toml`만 최소 변경.
- `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`은 이미 다른 수정이 포함된 dirty file이다. 기존 hunk를 되돌리지 않고 F11 범위만 추가한다.
- base+dev 환경은 새 `mktemp -d` 격리 checkout/export와 별도 `.venv`로 만든다. 현재 `.venv`를 재동기화하거나 오염시키지 않는다.
- rag 환경은 별도 venv로 실행하고 디스크/네트워크 설치 비용을 기록한다.
- 테스트를 전체 skip하거나 assertion을 삭제해 통과시키지 않는다.

## 다음 작업

1. 권한이 확보되면 실제 GitHub Actions에서 base/rag 4개 matrix가 모두 실행/보고되는지 확인한다.
2. 커밋 전 review를 받는다.

## 구현 초안 (2026-09-03)

1. `tests/test_memory_service.py`
   - 잘못된 `mem.vector_store is not None` assertion을 제거했다.
   - 새 테스트 `test_adds_knowledge_when_vector_backend_is_unavailable`은 `sys.modules["chromadb"]`를 `None`으로 만들어 optional backend 부재를 시뮬레이션하고, 지식 저장 성공 + `vector_store is None`을 검증한다.
   - 전체 파일 skip이나 assertion 삭제 없이 base 계약을 검증한다.
   - 환경에 실제 chromadb가 설치되어 있어도 이 시나리오는 backend를 사용하지 않는 경로를 강제한다.
2. `.github/workflows/ci.yml`
   - `test` job matrix에 `deps: [base, rag]`를 추가했다.
   - base는 `uv sync --locked --extra dev`, rag는 `uv sync --locked --extra dev --extra rag`를 사용한다.
   - pytest는 두 경우 모두 `uv run --no-sync`로 실행해 설치 후 extras 재동기화로 환경이 바뀌는 문제를 차단한다.
   - artifact 이름에 deps 차원을 추가해 base/rag 충돌을 방지한다.
   - coverage report는 `coverage-xml-ubuntu-latest-rag`를 사용한다.

## 검증 결과

| 환경 | 검사 | 결과 |
|---|---|---|
| base+dev 격리 (`/tmp/agk-f11-base.oTeYEj`) | `tests/test_memory_service.py` 수정 전 | 1 failed, 34 passed, exit 1 |
| base+dev 격리 | `tests/test_memory_service.py` 수정 후 | 35 passed, exit 0 |
| base+dev 격리 | 전체 `pytest -m 'not slow and not benchmark'` | 4775 passed, 8 skipped, 19 deselected, exit 0 |
| 현재 rag 설치 환경 | `tests/test_memory_service.py` + `tests/test_rag.py` | 38 passed, exit 0 |
| 정적 | `git diff --check` | exit 0 |
| CI YAML | unique-key parse + matrix/assertion 검사 | 4 조합(base/rag × ubuntu/macos) 확인, artifact 이름 일치 |
| 정적 | `ruff check tests/test_memory_service.py` | exit 0 |
| 정적 | `basedpyright tests/test_memory_service.py` | 0 errors, 0 warnings, 0 notes |

base 전체 실행의 8 skipped는 기존 optional/환경 경계이며 F11로 새 skip을 추가하지 않았다. rag 환경의 `test_rag.py`는 기존 `importorskip("chromadb")` 경계를 그대로 사용한다.

추가 evidence:

- [base-memory-service-green.log](../../../../.omo/evidence/f11-install-matrix/base-memory-service-green.log)
- [base-full-suite.log](../../../../.omo/evidence/f11-install-matrix/base-full-suite.log)
- [rag-memory-rag-green.log](../../../../.omo/evidence/f11-install-matrix/rag-memory-rag-green.log)

## 지문

아래 `metadata.json`이 최종 파일 해시를 보존한다:

| 파일 | 링크 |
|---|---|
| `tests/test_memory_service.py`, `.github/workflows/ci.yml`, 문서 SHA-256 | [metadata.json](../../../../.omo/evidence/f11-install-matrix/metadata.json) |

노트: `ruff format --check`는 이 파일 전체에서 이미 존재하던 formatting drift를 보고한다. F11 changed hunk만 포맷했고 무관한 파일 전체 mechanical rewrite는 하지 않았다.

## 정리

- 격리 환경 `/tmp/agk-f11-base.oTeYEj`(772MB)와 경로 기록 파일을 제거했다. 경로 기록 파일은 삭제 커맨드 중 이미 없어서 `No such file or directory`가 관찰되었지만, 대상 디렉터리는 정상 제거를 확인했다.
- 원본 `.venv`, 사용자 데이터, 다른 agent 변경을 변경하지 않았다.
