---
title: F03 릴리스 버전 원천 통일 진행 기록
tags: [qa, release, metadata, remediation]
date: 2026-09-02
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
---

# F03 진행 기록

릴리스 workflow가 빌드된 배포물 대신 `pyproject.toml`의 존재하지 않는 정적 `project.version`을 읽던 결함을 수정했다. 실제 PyPI 업로드, GitHub Release 발행, 외부 저장소 push는 수행하지 않았다.

## 상태

1. 완료: 기준 SHA에서 인수인계 재현 명령이 `KeyError: 'version'`으로 실패하는 것을 확인.
2. 완료: wheel/sdist 메타데이터, 파일명, 소스 `__version__`, `v*` 태그를 하나의 배포 세트로 검증하는 `release_metadata` 모듈 추가.
3. 완료: release workflow와 CI build job이 동일 검증 CLI를 호출하도록 변경.
4. 완료: 실제 `python -m build` 산출물로 성공, 태그 불일치 거절, branch ref 통과를 직접 확인.
5. 완료: 전체 비벤치마크 회귀 4,847 passed / 6 skipped / 16 deselected 통과.

## 계약

- `pyproject.toml`은 계속 `dynamic = ["version"]`이며 버전을 중복 기입하지 않는다.
- `src/antigravity_k/__init__.py::__version__`만 소스 버전 원천이다.
- 배포 판정 버전은 wheel `METADATA`에서 읽는다.
- 다음 네 값이 모두 같아야 한다: wheel METADATA, wheel 파일명, sdist PKG-INFO, sdist 파일명.
- 소스 `__version__`도 wheel METADATA와 같아야 한다.
- `refs/tags/v<version>` push에서는 태그 버전도 wheel 버전과 같아야 한다. branch/manual dry-run ref에서는 태그 검증을 건너뛴다.
- 프로젝트 이름은 wheel/sdist 파일명과 메타데이터 모두 `antigravity-k`로 정규화되어야 한다.
- `dist/`에는 wheel과 sdist가 정확히 하나씩 있어야 한다.

## 원인 및 구현

기존 release workflow는 setuptools가 빌드한 wheel/sdist를 만든 뒤 TOML에서 `project['version']`을 읽었다. 이 프로젝트는 `dynamic = ["version"]`이므로 이 값이 존재하지 않고, build job이 항상 `KeyError`로 실패한다. 태그/버전 불일치 검증도 없었다.

- [release_metadata.py](../../../../src/antigravity_k/engine/release_metadata.py): 배포 세트 검증과 CLI를 추가했다.
- [release.yml](../../../../.github/workflows/release.yml): 정적 TOML 읽기를 실제 검증 CLI 호출로 교체하고, 검증된 JSON에서 버전 출력을 만든다.
- [ci.yml](../../../../.github/workflows/ci.yml): PR/CI build 산출물도 동일 검증기를 통과하도록 조기 게이트를 추가했다.
- [test_release_metadata.py](../../../../tests/test_release_metadata.py): workflow 호출 계약, 동적 버전 유지, metadata 파싱, 불일치/비정상 배포 세트 거절을 잠근다.

## RED

기존 표현식 재현:

```bash
uv run --no-sync python -c "from pathlib import Path; print(__import__('tomllib').loads(Path('pyproject.toml').read_text('utf-8'))['project']['version'])"
```

```text
KeyError: 'version'
```

추가한 계약 테스트는 구현 전 `ModuleNotFoundError: antigravity_k.engine.release_metadata`, workflow 문자열 부재로 실패했다. 첫 실제 CLI 실행에서는 Typer 단일 명령 앱에 불필요한 `verify` 인자를 전달해 "Got unexpected extra argument(s)"로 실패했고, 워크플로 호출을 수정했다. 다음 실행에서는 실제 sdist의 루트 `PKG-INFO`와 `src/antigravity_k.egg-info/PKG-INFO`가 함께 있어 "exactly one PKG-INFO" 오류가 나왔다. 검증기가 루트 `{project}-{version}/PKG-INFO`만 읽도록 계약을 명확히 했다. 두 실패는 수정 과정의 실측 RED로 보존한다.

## 실제 배포 표면 검증

```bash
tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/agk-f03-dist.XXXXXX")
uv run --no-sync python -m build --outdir "$tmpdir"
uv run --no-sync python -m antigravity_k.engine.release_metadata \
  --distribution-root "$tmpdir" --git-ref refs/tags/v0.1.0
```

성공 출력:

```json
{"sdist":"antigravity_k-0.1.0.tar.gz","source_version":"0.1.0","version":"0.1.0","wheel":"antigravity_k-0.1.0-py3-none-any.whl"}
```

태그 불일치:

```bash
uv run --no-sync python -m antigravity_k.engine.release_metadata \
  --distribution-root "$tmpdir" --git-ref refs/tags/v0.9.9
```

```text
exit 2
{"error":"tag version 0.9.9 does not match wheel version 0.1.0","status":"error"}
```

branch ref:

```text
{"sdist":"antigravity_k-0.1.0.tar.gz","source_version":"0.1.0","version":"0.1.0","wheel":"antigravity_k-0.1.0-py3-none-any.whl"}
```

## 자동 검사

```bash
uv run --no-sync pytest tests/test_release_metadata.py tests/test_release_baseline.py \
  tests/test_artifact_provenance.py tests/test_artifact_provenance_api.py -q
# 29 passed

uv run --no-sync pytest tests/test_release_metadata.py tests/test_release_baseline.py \
  tests/test_artifact_provenance.py tests/test_artifact_provenance_api.py \
  tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py \
  tests/test_vault.py tests/test_vault_api.py tests/test_tool_sandbox_coverage.py -q
# 97 passed

uv run --no-sync ruff check src/antigravity_k/engine/release_metadata.py tests/test_release_metadata.py
uv run --no-sync ruff format --check src/antigravity_k/engine/release_metadata.py tests/test_release_metadata.py
uv run --no-sync basedpyright src/antigravity_k/engine/release_metadata.py tests/test_release_metadata.py
# 0 errors, 0 warnings, 0 notes

uv run --no-sync python -c "from pathlib import Path; import yaml; yaml.safe_load(Path('.github/workflows/release.yml').read_text()); yaml.safe_load(Path('.github/workflows/ci.yml').read_text())"
# workflow YAML parsed
```

전체 비벤치마크 회귀:

```bash
uv run --no-sync pytest tests -q -m 'not benchmark'
# 4847 passed, 6 skipped, 16 deselected
```

## 한계 및 남은 위험

- GitHub Actions 러너와 OIDC environment의 실제 실행, PyPI 업로드, GitHub Release 발행은 하지 않았다.
- `git describe` 기반 버전 자동 추론은 이번 범위가 아니다. 현재 프로젝트는 정적 `__version__ = "0.1.0"`을 사용한다.
- F05 배포물 기반 SBOM/notices는 이 수정과 별개로 열려 있다.

## 검증 대상 지문

모든 수정은 기준 commit `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 위의 미커밋 변경이다.

| 파일 | SHA-256 |
|---|---|
| `.github/workflows/ci.yml` | `784bd407e3f02474bd3eae5a72eb39f42e736d5a1aa252580b23bb53fc57b621` |
| `.github/workflows/release.yml` | `f23bbdb95c42963ced04df3fb15fc35fe0174d198df0f7dc0bbe92f7690349eb` |
| `src/antigravity_k/engine/release_metadata.py` | `4e7e6918df31bffe0ddab72334ef448cddb76e30be52e02bc79b8cb85fc5b095` |
| `tests/test_release_metadata.py` | `e92e622b0d9261cf22291565897ab5429a955bfc63e02b6edc1a40d0f147c3fd` |
