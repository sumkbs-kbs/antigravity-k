---
title: F05 배포물 기반 SBOM 및 notices 진행 기록
tags: [qa, release, sbom, notices, remediation]
date: 2026-09-02
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_with_latent_hoisted_npm_regression_fixed_pending_commit
---

# F05 진행 기록

CI가 cyclonedx 도구 환경만 수집하던 결함을 수정했다. Python은 `uv.lock`, dashboard는 `dashboard/package-lock.json`의 runtime closure에서 SBOM과 notices를 생성하고, 최종 wheel/sdist의 byte-for-byte 문서 일치를 검증한다. 실제 PyPI 업로드, GitHub Release 발행, 외부 저장소 push는 수행하지 않았다.

## 상태

1. 완료: 기준 상태의 SBOM job이 `cyclonedx-py environment`만 호출하고 제품 lockfile을 소비하지 않는 것을 확인.
2. 완료: Python/dashboard lockfile runtime closure 계산기 추가. dev/optional extras와 npm `dev` package를 제외하고 그 범위를 SBOM metadata와 notices에 명시.
3. 완료: CycloneDX 1.5 `python.cdx.json`, `dashboard.cdx.json`, `THIRD_PARTY_NOTICES.txt` 생성기와 wheel/sdist 검증 CLI 추가.
4. 완료: package-data에 세 문서를 포함하고 CI/release에서 generate → build → verify → `release-supply-chain.json` 업로드 흐름을 연결.
5. 완료: 실제 임시 checkout에서 wheel/sdist를 빌드해 세 문서 포함과 검증 통과, 문서 변조 시 exit 2 거절을 확인.
6. 완료: 전체 비벤치마크 회귀 4,853 passed / 6 skipped / 16 deselected 통과.
7. 완료(2026-09-03 후속): 첫 구현이 dashboard hoisted transitive runtime dependency를 누락하는 latent regression이 있음을 실제 lock에서 확인하고 수정했다. 이후 실제 wheel/sdist 재검증에서 dashboard 143 component, Python 61 component를 확인했다.

## 계약

- Python SBOM은 `uv.lock`의 `antigravity-k` root 일반 dependencies에서 BFS한 runtime closure만 담는다.
- root `[package.optional-dependencies]`와 lockfile `provides-extras`는 제외하며, `agk:excluded-extras`로 전체 목록을 명시한다.
- 특정 의존성에 extras가 명시되면(예: `uvicorn[standard]`) 해당 package의 그 extras closure만 추가로 포함한다.
- Dashboard SBOM은 package-lock v3 `packages` 그래프에서 root 일반 `dependencies`를 재귀 추적한다. `dev: true` package와 root `devDependencies`는 제외한다.
- npm resolution은 parent 자신의 `node_modules/<child>` 후보를 먼저 시도하고, 없으면 각 상위 package scope의 `node_modules/<child>` 후보로 올라간다. 중첩 경로와 root hoisted 경로 모두 포함한다.
- Runtime dependency 후보가 lock에 없으면 임의 누락이 아니라 dependency/package/후보 경로를 포함한 명시적 오류로 실패한다.
- Python/dashboard 모두 애플리케이션 root component와 runtime component를 포함하고, 빌드 도구/개발 도구 환경은 포함하지 않는다.
- 이름/버전은 반드시 lockfile에서 온다. license/notice는 resolver/package metadata에서 온다. 값이 없으면 `license metadata unavailable`로 명시하고 허위 license를 만들지 않는다.
- wheel은 `antigravity_k/release/<document>`, sdist는 `<project>-<version>/src/antigravity_k/release/<document>` 경로의 byte가 원본과 같아야 한다.
- 검증 성공 시 `release-supply-chain.json`에 배포 파일 SHA-256과 문서 digest(`sha256-...`)를 기록한다.

## 구현

- [release_dependencies.py](../../../../src/antigravity_k/engine/release_dependencies.py): `uv.lock`/package-lock v3 경계 파싱과 runtime closure 계산.
- [release_sbom.py](../../../../src/antigravity_k/engine/release_sbom.py): SBOM/notices 생성, wheel/sdist 검증, supply-chain manifest, Typer CLI.
- [test_release_sbom.py](../../../../tests/test_release_sbom.py): closure 범위, 중첩 npm 의존성, 누락/변조 거절, sdist 검증, workflow/package-data 계약, CLI E2E.
- [pyproject.toml](../../../../pyproject.toml): 배포물에 포함될 세 release 문서를 package-data로 명시.
- [ci.yml](../../../../.github/workflows/ci.yml): build job과 SBOM job 모두 실제 lockfile 문서를 생성/검증하고 `release-supply-chain.json`을 업로드.
- [release.yml](../../../../.github/workflows/release.yml): build 전 generate, build 후 verify, 배포 artifact에 supply-chain manifest 포함.

개발용 생성물을 저장소에 항상 남기지 않는다. release/CI packaging 시점에 생성하며, 로컬 검증은 격리 복사본에서 수행했다.

## RED

구현 전 집중 테스트는 다음과 같이 실패했다.

```text
ImportError: No module named 'antigravity_k.engine.release_sbom'
```

구현 후 첫 테스트는 Python `provides-extras` alias를 파싱하지 못해 `agk:excluded-extras == ""`로 실패했고, npm 중첩 의존성 경로를 root로 잘못 정규화해 `nested-lib`가 누락되었다. 두 실패를 계약으로 고정하고 수정했다.

2026-09-03 후속 RED: 실제 `dashboard/package-lock.json`에서 기존 resolver가 직접 의존성 20개만 반환하고 `scheduler` 같은 hoisted transitive runtime package를 누락했다. 합성 fixture에 `intermediate-lib -> hoisted-lib` 경로를 추가한 테스트, 실제 lock에서 `scheduler`/20개 초과를 검사하는 regression, unresolved runtime dependency가 무시 대신 실패하는 테스트가 모두 RED로 실패했다. 수정 후 3개 모두 GREEN이다.

## 실제 배포 표면 검증

임시 checkout `/var/folders/0c/ncf5ly7d36q53dy94lv6x_7w0000gn/T/agk-f05.L1n7QP`에서 수행했다. 원본 저장소에는 배포 생성물을 남기지 않았다.

```bash
uv run --no-sync python -m antigravity_k.engine.release_sbom generate \
  --project-root . --release-root src/antigravity_k/release
uv run --no-sync python -m build
uv run --no-sync python -m antigravity_k.engine.release_sbom verify \
  --distribution-root dist --release-root src/antigravity_k/release \
  --output dist/release-supply-chain.json
```

성공 출력 요지:

```json
{"dashboard_components":21,"python_components":61,"status":"generated"}
{"manifest":"dist/release-supply-chain.json","python_components":61,"status":"verified"}
```

wheel members:

```text
antigravity_k/release/THIRD_PARTY_NOTICES.txt
antigravity_k/release/dashboard.cdx.json
antigravity_k/release/python.cdx.json
```

sdist members:

```text
antigravity_k-0.1.0/src/antigravity_k/release/THIRD_PARTY_NOTICES.txt
antigravity_k-0.1.0/src/antigravity_k/release/dashboard.cdx.json
antigravity_k-0.1.0/src/antigravity_k/release/python.cdx.json
```

최종 supply-chain manifest:

```json
{
  "artifacts": {
    "antigravity_k-0.1.0-py3-none-any.whl": "ff9bd7817a799404eb0ffa6ae45ac9db77b2d5bd3b1425152ea362076bd450ed",
    "antigravity_k-0.1.0.tar.gz": "0351935e2576ec497bc256fecbeedc26e086c2adf2a2a3fdd802b8482637f022"
  },
  "documents": {
    "dashboard.cdx.json": "sha256-7d575746823d107fb8c383895774c9680e7ba8192548edec5716a5fab9c78a6d",
    "THIRD_PARTY_NOTICES.txt": "sha256-add3e0c169bc74c93592891373508ff31a183bbccb042add86436c938a300d8b",
    "python.cdx.json": "sha256-6e5d64fd8528d686dee4489d02f9bee6969056b8c7bbbdedecfc7b167935c76c"
  }
}
```

변조 검증: `python.cdx.json`을 `{}\n`으로 변경한 뒤 동일 verify를 실행하면 exit 2와 아래 오류로 실패한다.

```json
{"error":"python.cdx.json does not match wheel release document","status":"error"}
```

## 자동 검사

```bash
uv run --no-sync pytest tests/test_release_sbom.py -q
# 6 passed

uv run --no-sync pytest tests/test_release_sbom.py tests/test_release_metadata.py \
  tests/test_release_baseline.py tests/test_artifact_provenance.py \
  tests/test_artifact_provenance_api.py tests/test_dashboard_wheel_assets.py -q
# 36 passed

uv run --no-sync ruff check src/antigravity_k/engine/release_dependencies.py \
  src/antigravity_k/engine/release_sbom.py tests/test_release_sbom.py
uv run --no-sync ruff format --check src/antigravity_k/engine/release_dependencies.py \
  src/antigravity_k/engine/release_sbom.py tests/test_release_sbom.py
uv run --no-sync basedpyright src/antigravity_k/engine/release_dependencies.py \
  src/antigravity_k/engine/release_sbom.py tests/test_release_sbom.py
# ruff passed, format passed, basedpyright 0 errors / 0 warnings / 0 notes

uv run --no-sync python -c "from pathlib import Path; import yaml; yaml.safe_load(Path('.github/workflows/release.yml').read_text()); yaml.safe_load(Path('.github/workflows/ci.yml').read_text())"
# workflow YAML parsed

uv run --no-sync pytest tests -q -m 'not benchmark'
# 4853 passed, 6 skipped, 16 deselected
```

## 2026-09-03 hoisted npm regression 재검증

```bash
uv run --no-sync pytest tests/test_release_sbom.py -q
# 8 passed

uv run --no-sync ruff check src/antigravity_k/engine/release_dependencies.py tests/test_release_sbom.py
uv run --no-sync ruff format --check src/antigravity_k/engine/release_dependencies.py tests/test_release_sbom.py
uv run --no-sync basedpyright src/antigravity_k/engine/release_dependencies.py tests/test_release_sbom.py
# ruff passed, format passed, basedpyright 0 errors / 0 warnings / 0 notes

uv run --no-sync pytest tests/test_release_sbom.py tests/test_release_metadata.py \
  tests/test_release_baseline.py tests/test_artifact_provenance.py \
  tests/test_artifact_provenance_api.py tests/test_dashboard_wheel_assets.py -q
# 38 passed
```

격리 임시 checkout `/var/folders/0c/ncf5ly7d36q53dy94lv6x_7w0000gn/T/agk-f05-hoisted.FahH9h/repo`에서 실제 배포 경로를 반복했다. 원본에는 배포 생성물을 남기지 않았다.

```bash
uv run --no-sync python -m antigravity_k.engine.release_sbom generate \
  --project-root . --release-root src/antigravity_k/release
# {"dashboard_components":143,"python_components":61,"status":"generated"}

uv run --no-sync python -m build
# Successfully built antigravity_k-0.1.0.tar.gz and antigravity_k-0.1.0-py3-none-any.whl

uv run --no-sync python -m antigravity_k.engine.release_sbom verify \
  --distribution-root dist --release-root src/antigravity_k/release \
  --output dist/release-supply-chain.json
# {"dashboard_components":143,"status":"verified"}
```

생성된 `dashboard.cdx.json`에는 `scheduler`가 포함되어 있다. wheel/sdist member 목록에 세 release 문서가 모두 있고, manifest는 [f05-hoisted-supply-chain.json](../../../../.omo/evidence/f05-hoisted-supply-chain.json), build 원문은 [f05-hoisted-build.log](../../../../.omo/evidence/f05-hoisted-build.log)에 보존했다.

| artifact | SHA-256 |
|---|---|
| wheel | `77be71b6a337a51ad160cda107f75b1f7c2e274f3b4bba8569109f4c7c06e52a` |
| sdist | `a5d186cd9fe94d74b1d037120c8f177b5bbdae1a81722e3fc4bdef4f0b3d0070` |

## 한계 및 남은 위험

- GitHub Actions 러너, OIDC environment, PyPI 업로드, GitHub Release 발행은 실제로 실행하지 않았다.
- Python license는 현재 resolver 환경의 installed metadata에서 읽는다. 완전 offline 빌드에서 metadata가 없으면 unavailable로 명시된다.
- CycloneDX JSON의 외부 schema validator는 별도로 실행하지 않았다. 필수 구조와 실제 artifact 포함/변조 검증은 통과했다.
- `F14`의 금지 SPDX scanner, provenance inventory 검증 강화는 이 트랙과 별개로 열려 있다.
- Dashboard 번들 자체를 npm tarball로 배포하는 경로는 없다. dashboard SBOM/notices는 Python 배포물 안에 포함된다.

## 검증 대상 지문

모든 수정은 기준 commit `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 위의 미커밋 변경이다.

| 파일 | SHA-256 |
|---|---|
| `.github/workflows/ci.yml` | `edb110bbe771abd4b97c7820e2d7162585eb9dfef5922c05c3f79a37bed81dc3` |
| `.github/workflows/release.yml` | `350074b06eb3c9d93a6bec1b94245bb4d6cf7723d708157176a9b56cb28c3206` |
| `pyproject.toml` | `c05f99022c0cb010ec3ce4a1f85caf658a988b81331a127eeb7ab8646d7a5b59` |
| `src/antigravity_k/engine/release_dependencies.py` | `422c162b8eb64b96897bd4e9da57af30e0d13d69be1eaef207998791eae820a9` |
| `src/antigravity_k/engine/release_sbom.py` | `35c34de9399ff9e70634a44d3a74a4d7dfe23448631ced7f0652b1effc0ea2f9` |
| `tests/test_release_sbom.py` | `041166b73e5b770ae6a8fc8a5695cfbd693a47c1d081faf288062c054b8947a7` |

2026-09-03 후속 수정 직후 최종 지문:

| 파일 | SHA-256 |
|---|---|
| `src/antigravity_k/engine/release_dependencies.py` | `d74808a3aa36d435a8969ee96005bee662ea54d46590e4cac80577dd1a73c0f7` |
| `tests/test_release_sbom.py` | `9a355c2ff4e7980eccf12e4bb1bbd5348099047450e23a84bf11d906d9813336` |

문서 자체의 hash는 문서 내용이 바뀔 때마다 함께 바뀌므로 본 문서에 자기 참조로 기록하지 않는다. 외부 검증이 필요하면 그 시점의 `sha256sum` 출력을 별도 evidence로 남긴다.
