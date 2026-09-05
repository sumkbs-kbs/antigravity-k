---
title: F06 의존성 권고 triage 진행 기록
tags: [qa, security, dependencies, audit, remediation]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_with_documented_optional_residual_pending_commit
final_audit_utc: 2026-09-02T22:40:00Z
---

# F06 진행 기록

현재 의존성 권고를 실제 프로젝트 lock과 설치 환경 기준으로 재분류하고, 수정 가능한 base runtime/optional/dev 의존성을 갱신한 뒤 전체 회귀와 실제 배포물 검증을 수행했다. 최종 상태는 **base runtime 권고 0건, dashboard production 권고 0건, dev-only 권고는 범위를 명시**했으며, upstream에 fix 버전이 없는 ChromaDB 4건만 optional `rag` extra의 명시적 residual risk로 남는다.

## 상태 및 결론

1. 감사 대상을 전역 Python이 아니라 프로젝트 `.venv/bin/python`과 lockfile로 강제했다. 우연히 전역 환경을 감사한 74건 숫자는 폐기했다.
2. Python base runtime: cryptography, MCP, Starlette, python-multipart, pydantic-settings 권고를 모두 수정했다.
3. Python optional extras: aiohttp(RAG/Kubernetes 경로), transformers(MLX/transformers/RAG 관련 경로), datasets(finetune/MLX 경로)를 수정했다.
4. Python dev: pytest와 pytest-asyncio를 함께 major upgrade하고 전체 비벤치마크 suite를 통과시켰다.
5. Dashboard: pnpm 11.3의 실제 설치 tree에서 Monaco 아래 DOMPurify 3.4.8을 3.4.14로 override했다. npm package-lock도 같은 3.4.14 runtime closure를 유지한다.
6. Dashboard production audit(pnpm/npm 모두)은 0건이다. 전체 audit의 browserslist/qs/typed-rest-client는 Stryker 개발 tree 전용이며 브라우저 runtime 노출이 아니다.
7. VS Code extension audit의 browserslist/fast-uri도 개발/테스트 tree 전용이다. F13에서 clean install/test 계약을 다룰 때 함께 갱신한다.
8. Local bootstrap tooling의 pip/setuptools를 26.2.1/84.0.0으로 갱신해 tooling 권고를 제거했다. 이 두 패키지는 제품 manifest/runtime 의존성이 아니다.
9. ChromaDB 1.5.9의 4건은 pip-audit가 fix version을 보고하지 않는다. optional `rag` extra에만 설치되므로 base runtime 배포에 포함되지 않지만, RAG 서버를 인터넷에 노출하면 안 된다.

## 최종 잔존: ChromaDB optional RAG extra

ChromaDB는 `uv tree --invert --package chromadb` 기준으로 `antigravity-k[rag]`에서만 도달한다. base runtime SBOM에는 포함되지 않는다. 2026-09-03 기준 pip-audit이 fix version을 제공하지 않은 권고는 아래와 같다.

| advisory | alias | 공격 전제 | 조치 |
|---|---|---|---|
| PYSEC-2026-311 | GHSA-f4j7-r4q5-qw2c, CVE-2026-45829 | RAG API가 노출되고 unauthenticated attacker가 malicious model repository와 `trust_remote_code=true`로 collection 생성 가능할 때 코드 실행 | fix 미출시. RAG API 비노출/신뢰할 수 없는 model repository 거부 |
| CVE-2026-45830 | GHSA-2wm9-hf6c-p5cr | authenticated user가 다른 tenant collection에 읽기/쓰기/갱신/삭제 시도 | fix 미출시. tenant 분리가 필요한 환경에서 ChromaDB API 비노출 |
| CVE-2026-45833 | GHSA-36p7-vc44-83pf | authenticated attacker가 `UPDATE_COLLECTION` 권한과 malicious model repository 사용 | fix 미출시. 신뢰할 수 없는 model repository 거부 |
| CVE-2026-45831 | GHSA-xph7-9rjv-w5fr | SimpleRBACAuthorizationProvider 사용 시 tenant/database/collection 범위 미검사 | fix 미출시. 해당 provider를 신뢰 경계 보호용으로 사용하지 않음 |

이 residual은 예외를 숨기는 것이 아니라 audit exit code 1과 raw JSON으로 그대로 보존한다. ChromaDB fixed release가 나오면 `[rag]` 설치 환경에서 즉시 upgrade하고 RAG integration matrix를 다시 실행해야 한다.

## 실제 변경

| 범위 | package | 이전 | 최종 | 이유 |
|---|---|---:|---:|---|
| base runtime | cryptography | 48.0.0 | 50.0.1 | GHSA-537c-gmf6-5ccf, PYSEC-2026-3552/3553/3554. complete fix에 50 line 필요 |
| base runtime | mcp | 1.27.1 | 1.28.1 | PYSEC-2026-3481/3482/3483 |
| base runtime | starlette | 1.1.0 | 1.3.1 | PYSEC-2026-248/249 |
| base runtime | python-multipart | 0.0.29 | 0.0.31 | PYSEC-2026-3036/3037/3040 |
| base runtime | pydantic-settings | 2.14.1 | 2.14.2 | GHSA-4xgf-cpjx-pc3j |
| optional rag/ml | aiohttp | 3.13.5 | 3.14.3 | PYSEC-2026-2104–2113, 237, 3545–3547 |
| optional transformers/mlx/rag | transformers | 5.9.0 | 5.10.1 | CVE-2026-9856. advisory floor 5.10.0은 upstream yanked라 첫 안정 patch 5.10.1 사용 |
| optional finetune/mlx | datasets | 3.6.0 | 5.0.1 | PYSEC-2026-3716. 이 프로젝트의 `<4` cap과 의존 경로 재검토 후 5.x로 갱신 |
| dev | pytest | 8.4.2 | 9.0.3 | PYSEC-2026-1845 |
| dev | pytest-asyncio | 0.26.0 | 1.4.0 | pytest 9 지원 범위 |
| dashboard runtime | monaco-editor 내부 dompurify | 3.4.8 | 3.4.14 | GHSA-vxr8-fq34-vvx9, GHSA-cmwh-pvxp-8882, GHSA-c2j3-45gr-mqc4, GHSA-55q2-fjhq-7xh7 |
| local tooling | pip/setuptools | 25.3 / 81.0.0 | 26.2.1 / 84.0.0 | project venv tooling 권고 제거. 제품 manifest 아님 |

Manifest 계약:

- [pyproject.toml](../../../../pyproject.toml): `cryptography>=50.0.1,<51.0`, `pytest>=9.0.3,<10.0`, `pytest-asyncio>=1.4.0,<2.0`, `datasets>=5.0.1,<6.0`.
- [pnpm-workspace.yaml](../../../../dashboard/pnpm-workspace.yaml): pnpm 11.3가 읽는 `overrides.dompurify: 3.4.14`.
- [package.json](../../../../dashboard/package.json): npm package-lock용 scoped override는 기존 `monaco-editor > dompurify` 형태를 유지한다. npm은 direct dependency의 broad range와 global exact override를 함께 두면 `EOVERRIDE`로 실패한다.
- 두 lockfile 모두 package manager가 생성했다. lockfile을 수작업으로 병합하지 않았다.

## 해결된 Python 권고 상세

최초 43건/11개 package 감사에서 아래 권고를 제거했다. 원본 raw data는 evidence JSON과 TSV를 참조한다.

| package | advisory / aliases | fix floor | 실제 dependency path | 최종 |
|---|---|---|---|---:|
| cryptography 48.0.0 | GHSA-537c-gmf6-5ccf | 48.0.1 | antigravity-k; mcp[crypto]→pyjwt[crypto] | 50.0.1 |
| cryptography 48.0.0 | PYSEC-2026-3553, CVE-2026-69249 | 49.0.0 | 위와 동일 | 50.0.1 |
| cryptography 48.0.0 | PYSEC-2026-3554, CVE-2026-69248 | 49.0.0 | 위와 동일 | 50.0.1 |
| cryptography 48.0.0 | PYSEC-2026-3552, CVE-2026-69247 | 50.0.0 | 위와 동일 | 50.0.1 |
| mcp 1.27.1 | PYSEC-2026-3481/3482 | 1.27.2 | antigravity-k | 1.28.1 |
| mcp 1.27.1 | PYSEC-2026-3483 | 1.28.1 | antigravity-k | 1.28.1 |
| starlette 1.1.0 | PYSEC-2026-248 | 1.3.0 | antigravity-k→fastapi; mcp; gradio; sse-starlette | 1.3.1 |
| starlette 1.1.0 | PYSEC-2026-249 | 1.3.1 | 위와 동일 | 1.3.1 |
| python-multipart 0.0.29 | PYSEC-2026-3036/3037 | 0.0.30 | antigravity-k→mcp; mlx-vlm→gradio | 0.0.31 |
| python-multipart 0.0.29 | PYSEC-2026-3040 | 0.0.31 | 위와 동일 | 0.0.31 |
| pydantic-settings 2.14.1 | GHSA-4xgf-cpjx-pc3j | 2.14.2 | antigravity-k; mcp; optional rag→chromadb | 2.14.2 |
| aiohttp 3.13.5 | PYSEC-2026-2104–2113, 237, 3545–3547 | 3.14.0–3.14.3 | optional rag→chromadb→kubernetes; optional ML/finetune→fsspec[http] | 3.14.3 |
| transformers 5.9.0 | CVE-2026-9856 | 5.10.0 | optional transformers, rag, mlx-media, mlx | 5.10.1 |
| datasets 3.6.0 | PYSEC-2026-3716 | 5.0.1 | optional finetune; optional mlx→mlx-vlm | 5.0.1 |
| pytest 8.4.2 | PYSEC-2026-1845 | 9.0.3 | dev extra | 9.0.3 |

위 표의 공격 전제와 설명은 raw advisory JSON에 있다. 본문에는 동일 설명을 반복 복사하지 않는다.

## 해결된 Dashboard DOMPurify 경로

pnpm 11.3에서 `package.json`의 `pnpm.overrides`는 무시된다. 최초 시도에서 `pnpm --dir dashboard install --lockfile-only`가 “Already up to date”를 반환했지만 lock에는 `dompurify@3.4.8`이 남았다. 이를 `pnpm-workspace.yaml`로 이동한 뒤 다시 생성했다.

최종 확인:

```text
@monaco-editor/react → monaco-editor → dompurify 3.4.14
monaco-editor → dompurify 3.4.14
direct dompurify 3.4.14
```

lockfile에는 `dompurify@3.4.8`이 존재하지 않는다. npm package-lock도 `node_modules/dompurify` 단일 항목 3.4.14를 유지한다.

## 감사 명령과 결과

Python은 반드시 프로젝트 interpreter를 강제한다.

```bash
PIPAPI_PYTHON_LOCATION="$PWD/.venv/bin/python" \
  uv run --no-sync pip-audit --format json \
  --output .omo/evidence/f06-dependency-triage/pip-audit-final.json
# exit 1: 4 known vulnerabilities in 1 package
# package: chromadb 1.5.9, optional rag extra, fix versions 없음
```

Dashboard:

```bash
pnpm --dir dashboard audit --prod --json
# exit 0, vulnerabilities all 0, production dependency 145

pnpm --dir dashboard audit --json
# exit 1: qs 3건, 모두 @stryker-mutator dev tree

npm audit --omit=dev --package-lock-only --json
# exit 0

npm audit --package-lock-only --json
# exit 1: browserslist(high), qs(moderate), typed-rest-client(moderate), 모두 dev tree
```

VS Code extension은 이번에 manifest를 바꾸지 않았다. 기존 감사의 browserslist/high와 fast-uri/high는 dev-only로 유지되며 F13에서 처리한다.

## 회귀 및 배포물 검증

| 검사 | 명령/환경 | 결과 |
|---|---|---|
| 관련 Python 집중 | `uv run --no-sync pytest -q tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py tests/test_mcp_session_manager.py tests/test_mcp_tool_loader.py tests/test_release_sbom.py tests/test_release_baseline.py` | 122 passed, 1 pre-existing Starlette deprecation warning |
| 전체 Python | `uv run --no-sync pytest tests -q -m 'not benchmark'` | 4,855 passed, 6 skipped, 16 deselected, 1 warning |
| Dashboard lint | `pnpm --dir dashboard lint` | exit 0 |
| Dashboard typecheck | `pnpm --dir dashboard typecheck` | exit 0 |
| Dashboard 전체 test | `pnpm --dir dashboard test` | 44 files / 598 tests passed |
| Dashboard production build | `pnpm --dir dashboard build` | exit 0, 실제 bundle 재생성 |
| Python static check | `uv run --no-sync ruff check pyproject.toml src tests scripts` | exit 0 |
| Lock 정합성 | `uv lock --check` | exit 0 |
| 실제 release generate/build/verify | 격리 `/tmp/agk-f06.z1d4ZQ` | dashboard 143, Python 61 components; wheel/sdist에 세 release 문서 포함, verify exit 0 |

`ruff format --check src tests scripts`는 여전히 165개 기존 파일을 보고한다. 이는 F06 변경 이전부터 존재하는 F15 formatter backlog이므로 이번 범위에서 일괄 수정하지 않았다.

격리 배포 검증에서 build isolation은 `setuptools>=77` 요구에 따라 setuptools 84.0.0을 사용했다. wheel/sdist artifact hash는 [release-supply-chain.json](../../../../.omo/evidence/f06-dependency-triage/release-supply-chain.json)에 있다.

## 증거 및 지문

Evidence directory: `.omo/evidence/f06-dependency-triage/`

| 자료 | 링크 |
|---|---|
| 최초 프로젝트 venv audit(43건) | [pip-audit-current.json](../../../../.omo/evidence/f06-dependency-triage/pip-audit-current.json) |
| 최종 프로젝트 venv audit(ChromaDB 4건) | [pip-audit-final.json](../../../../.omo/evidence/f06-dependency-triage/pip-audit-final.json), [details](../../../../.omo/evidence/f06-dependency-triage/pip-audit-final-details.json) |
| 최초 Python 상세 TSV | [pip-audit-current-details.tsv](../../../../.omo/evidence/f06-dependency-triage/pip-audit-current-details.tsv) |
| pnpm production audit | [dashboard-pnpm-audit-after-prod.json](../../../../.omo/evidence/f06-dependency-triage/dashboard-pnpm-audit-after-prod.json) |
| pnpm full audit | [dashboard-pnpm-audit-after-full.json](../../../../.omo/evidence/f06-dependency-triage/dashboard-pnpm-audit-after-full.json) |
| npm production audit | [dashboard-npm-audit-after-prod.json](../../../../.omo/evidence/f06-dependency-triage/dashboard-npm-audit-after-prod.json) |
| npm full audit | [dashboard-npm-audit-after-full.json](../../../../.omo/evidence/f06-dependency-triage/dashboard-npm-audit-after-full.json) |
| 격리 build/verify 원문 | [generate](../../../../.omo/evidence/f06-dependency-triage/agk-f06-generate.log), [build](../../../../.omo/evidence/f06-dependency-triage/agk-f06-build.log), [verify](../../../../.omo/evidence/f06-dependency-triage/agk-f06-verify.log) |
| supply-chain manifest | [release-supply-chain.json](../../../../.omo/evidence/f06-dependency-triage/release-supply-chain.json) |

핵심 파일 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `pyproject.toml` | `e225bce647555febb444e6e8d1a83c371e5b751e8bf6f91faeaf4a68d43b2610` |
| `uv.lock` | `9fcd808695ed8db18672ddc6e51fd978f8a2ac992a42abc45073b9b11534cec4` |
| `dashboard/package.json` | `8b9de6dc904b3c449c97591ae08b1ba1dc41d452099289c3afe2a4b8a7c100d6` |
| `dashboard/package-lock.json` | `8576d03d69a7cf11f31c4254d79292ebb0ef479467938ccbfb782e7046bf74d1` |
| `dashboard/pnpm-lock.yaml` | `067f5027e227c1efc8fcb1ed7d76ae2fc42630fa84dfc6fd206df24acaed667e` |
| `dashboard/pnpm-workspace.yaml` | `3f0402705c58d184b06d794030ffef3ecafc9d54829df317d3671fa2baca73ff` |
| `pip-audit-final.json` | `acf4e9cc7fda93e52d4d3b8ee8c2d5377df9a61db2e8924f6e83dfa3c54beb06` |
| `release-supply-chain.json` | `c2690851e4b437ed1f86684e9d31959911c65d30631daf902cf984ae98d7607b` |

## 한계 및 다음 에이전트 지시

1. F06은 의존성 triage/upgrade 범위다. F11의 base+dev/RAG 설치 matrix, F08 Wiki HTML 안전성, F09/F10 실제 E2E, F13 extension 계약은 여전히 열려 있다.
2. `uv sync --frozen`은 local pip/setuptools tooling upgrade를 되돌릴 수 있다. 감사 전 `uv pip install --upgrade pip setuptools`를 실행하거나, tooling finding이 다시 나오면 manifest가 아니라 bootstrap 환경 상태임을 먼저 확인한다.
3. advisory DB는 계속 바뀐다. 재검증은 evidence 파일이 아니라 동일 명령을 fresh하게 실행한다.
4. `dashboard/package-lock.json`은 SBOM/공지 용도로 계속 유지되고, CI 설치는 `pnpm-lock.yaml`을 사용한다. 두 lock 중 하나만 바꾸면 F05 resolver 테스트와 production audit으로 즉시 확인해야 한다.
5. ChromaDB fixed release가 나오면 optional `rag` 환경에서만 먼저 upgrade 후 RAG integration regression과 `pip-audit`를 다시 실행한다.
6. 기존 repository는 `dashboard/node_modules` 일부를 추적한다. pnpm 설치가 tracked `vite` 실체를 symlink로 바꿔 Git dirty 상태를 만들 수 있다. 이번 검증 후 tracked node_modules 상태를 원래 index 내용으로 복원했다. package 설치 후 `git status --short dashboard/node_modules`를 반드시 확인한다.
