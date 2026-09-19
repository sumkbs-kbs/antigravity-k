---
title: CR-11 릴리스 부트스트랩과 의존성 감사 계약
status: active (CR-11 REVIEW)
date: 2026-09-12
owner: cr-11-maintenance
tags: [ci, release, supply-chain, audit, dependency]
---

# CR-11 릴리스 부트스트랩과 의존성 감사 계약

이 문서는 "왜 CI가 이 순서인가"와 "감사가 무엇을 보는가"를 다음 작업자·운영자가 다시 추론하지 않도록 고정한다.

## 1. Python 환경은 하나뿐이다

- 워크플로는 `uv sync --locked --no-editable --extra dev`만 쓴다. editable 설치와 `PYTHONPATH=src`는 금지다.
- 이유: 저장소 트리가 import 경로에 있으면 **배포 아티팩트에서 파일이 빠져도 스모크가 통과**한다. 이번에 발견한 R01(설치 전에 `python -m antigravity_k.engine.release_sbom` 실행 → 새 venv에서 ModuleNotFoundError)이 그 위에 숨어 있었다.
- 도구도 같은 환경에서 실행한다: `uv run --no-sync ruff|mypy|basedpyright|bandit|pytest`.
- 확인: `grep -n "pip install -e\|PYTHONPATH=src" .github/workflows/*.yml` → 주석 문구만 나와야 한다(계약 검사는 주석을 제거한 뒤 수행).

## 2. 감사 대상을 Dockerfile에서 파생한다

단일 진실원은 "제품이 실제로 설치하는 것"이다 → `Dockerfile`의 `pip install ".[rag]"`.

```bash
scripts/audit_python_dependencies.sh --print-targets
# AUDIT-INPUTS: {"shipped_extras":["rag"],"targets":{
#   "base":{"packages":65,"sha256_16":"..."},
#   "extras":{"rag":{"packages":145,"sha256_16":"..."}},
#   "union":{"packages":145,"sha256_16":"..."}}}
```

- `packages`는 `name==version` 항목 수다(해시 연속 줄 제외).
- 지문은 주석 줄을 제외한 정규화 내용의 sha256 앞 16자리다. `uv export`가 헤더에 출력 경로를 적어 넣기 때문에 **파일 바이트를 그대로 해시하면 실행마다 달라진다**(수정 이력).
- 감사 입력은 합집합 파일이 아니라 **각 파일을 그대로** pip-audit에 넘긴다(`--requirement` 반복). requirements-txt의 줄 연속(`name==version \` + `--hash=...`)을 `sort -u`하면 항목과 해시가 갈라져 입력이 손상된다.
- pyproject에 없는 extra 이름은 조용히 무시하지 않고 **exit 2**로 거부한다.

## 3. 종료코드는 세 갈래다

| exit | 의미 | 예 |
|---|---|---|
| 0 | high/critical 미해결 0건 | 취약점이 없거나 전부 유효한 예외로 등록됨 |
| 1 | 취약점 발견 또는 **만료된 예외** | 미등록 권고, `expires` 지난 예외 |
| 2 | 사용법/인프라 오류(감사 미완료) | pyproject에 없는 extra, uv export 실패, 감사 도구 출력 해석 불가, 레지스트리 부재(취약점이 있을 때) |

## 4. 예외는 REL-03 레지스트리를 따른다

`config/audit-exceptions.json` — 각 항목은 owner/justification/expires/compensating_controls 4요소가 필수다.

- 판정 규칙(엔진 `antigravity_k.engine.audit_exceptions`와 동일):
  high/critical만 실패 대상, `(id, package, ecosystem, installed_version)` **정확 일치**, 만료 시 실패(deny-by-default).
- `id`는 **감사 도구가 보고하는 primary id**를 쓴다. pip-audit/PyPI는 같은 권고를 `PYSEC-xxxx-xxxx`로 보고하고 CVE/GHSA를 `aliases`로 준다. CVE로 등록하면 매칭되지 않아 게이트가 실패한다(의도된 동작).
- 두 곳(셸 스크립트/stdlib, 엔진/pydantic)이 같은 규칙을 각자 구현한다. 일치 여부는 `tests/test_cr11_release_bootstrap.py::test_audit_verdict_matches_the_engine_verdict`가 고정한다. 규칙을 바꾸면 두 곳을 함께 고치고 이 테스트를 갱신한다.
- 현재 등록(2026-09-12, 만료 2026-12-08): chromadb 1.5.9의 `PYSEC-2026-311`(CVE-2026-45829), `PYSEC-2026-3813`(CVE-2026-45830), `PYSEC-2026-3814`(CVE-2026-45833), `PYSEC-2026-3815`(CVE-2026-45831). 상류 fix가 나오면 lock을 올리고 예외를 제거한다.

## 5. 패키징 전에 대시보드를 다시 빌드한다

`src/antigravity_k/dashboard_dist`는 **추적 대상**이라 체크아웃에 낡은 번들이 들어 있다. `python -m build`만 돌리면 낡은 UI가 릴리스된다.

- 순서: `pnpm --dir dashboard install --frozen-lockfile` → `pnpm --dir dashboard build` → SBOM 생성 → `uv build --no-sources` → `bash scripts/verify_dashboard_bundle.sh --skip-build`.
- `verify_dashboard_bundle.sh`는 wheel 내부 `antigravity_k/dashboard_dist/**`와 소스 트리를 파일별 sha256으로 대조하고 `BUNDLE-FINGERPRINT`(디렉터리 지문)를 출력한다. 누락/추가/내용 불일치면 exit 1.
- 한계: 소스와 wheel이 같은 트리에서 나오므로 이 대조는 "낡음" 자체를 잡지 못한다. 낡음을 막는 것은 **재빌드 단계**이고, 대조는 "재빌드가 실제로 wheel에 들어갔는가"(outDir 변경·package-data 누락 등)를 잡는 증거다. 그래서 각 job에 재빌드가 있는지가 계약이다.

## 6. Node/pnpm 조합

- `dashboard/package.json`: `packageManager: pnpm@11.3.0`, `engines: { node: ">=22.13", pnpm: ">=11.3.0" }`.
- `pnpm@11.3.0`은 `node:sqlite` builtin을 쓰므로 Node 22.13 이상이 필요하다(Node 20에서는 설치 단계가 깨진다).
- CI 4개 job과 `Dockerfile`(`node:22.13-alpine`)이 같은 값을 쓴다. `pnpm/action-setup`은 `run_install: false`로 두고 `pnpm --dir dashboard install --frozen-lockfile`을 명시적으로 실행한다.
- 테스트: `tests/test_cr11_release_bootstrap.py::test_node_pins_satisfy_declared_engines`, `test_pnpm_pins_match_package_manager_declaration`.

## 7. 릴리스는 dry-run까지만 검증한다

- `release.yml`의 `dry_run` 입력 기본값은 `"true"`. `workflow_dispatch`에서는 `dry-run-report` job이 `RELEASE-DRY-RUN: publish=false`를 출력하고 아무 것도 배포하지 않는다.
- `publish-pypi`/`github-release`는 태그 push에서만 열리며 `inputs.dry_run != 'true'`가 함께 걸려 있다.
- 테스트 중 publish/upload 단계는 실행하지 않는다(별도 권한 필요).

## 8. 저장소 밖 설치 검증

```bash
bash scripts/verify_release_artifacts.sh            # wheel+sdist 빌드 후 저장소 밖 신규 venv에서 검증
bash scripts/verify_release_artifacts.sh --skip-build
```

각 아티팩트마다: 설치된 `antigravity_k`가 저장소 밖인지 → `agk --version`/`agk model list` → `python -m antigravity_k.engine.release_sbom --help` → FastAPI TestClient `/health` 200 → 토큰 발급/검증·PIN 해시/검증·정책 결정 → `pip check`. cwd는 저장소 밖 중립 디렉터리이고 `PYTHONPATH`는 제거한다.
