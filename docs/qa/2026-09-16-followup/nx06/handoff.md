---
title: NX-06 배포 readiness와 신규 설치 순서 — 인계
created: 2026-09-16
state: REVIEW (정적 수정·계약 시험 green / 런타임 관측 BLOCKED)
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
depends_on: docs/qa/2026-09-16-followup/nx00/handoff.md, docs/qa/2026-09-16-followup/nx05/handoff.md
tags: [nx-06, deploy, readiness, k8s, handoff]
---

# NX-06 인계 기록 (정적 REVIEW / 런타임 BLOCKED)

```text
Task ID / attempt: NX-06 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토 필요)
State: REVIEW — 정적 수정과 계약 시험 완료, 실제 cluster 관측은 BLOCKED(원인/해제조건 아래).
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e
Dirty paths (secret contents excluded):
  deploy/k8s/deployment.yaml, deploy/k8s/namespace.yaml, deploy/README.md,
  src/antigravity_k/engine/operational_metrics.py, src/antigravity_k/api/server.py,
  tests/test_nx06_deploy_readiness.py(신규), docs/qa/2026-09-16-followup/nx06/**
Scope / files / symbols: deployment.yaml(probe 3종 경로·역할 주석), namespace.yaml(설치 순서 헤더),
  README.md(설치 3단계·probe/트래픽 표·의존성 분류·NetworkPolicy 주의·rollback),
  operational_metrics.py(_READINESS_CHECKS, ReadinessKind, _readiness_check, compute_readiness 의
  kind/traffic, _check_writable_storage 의 false-ready 제거), api/server.py(readiness_endpoint 문서·판정).
Preconditions / dependency evidence: NX-00 기준 SHA. OBS-01 의 기존 시험(11 passed)이 readiness 계약의 기반.
Observed failure before / exact reproduction: before.md §2 — readinessProbe=/health(의존성 미검사),
  보고서에 kind/traffic 없음, 프로젝트 루트 부재를 `writable: data` 로 ready 오보, README 설치 순서 성립 안 함.
Change and invariant: (1) readiness 는 의존성 검사(/api/ready)만, liveness/startup 은 생존(/health)만 본다.
  (2) required 검사 실패 → not_ready → 503 → endpoint 제외. (3) optional 의존성은 not_ready 도 degraded 로
  내려 트래픽을 막지 않는다(신규 설치의 정상 상태가 서비스되도록). (4) degraded 는 200(수용).
  (5) 설정된 프로젝트 루트가 없으면 ready 로 보고하지 않는다. (6) 설치 순서 namespace → secret → 나머지.
Commands / cwd / exit codes / environment: commands.txt (cwd = 레포 루트). 드라이버 before exit 3 → after exit 0.
Runtime expected vs observed: 정적 계약은 전부 통과. **Pod/EndpointSlice 관측은 미실시(BLOCKED)** —
  kube context 0개, kubectl client dry-run 도 API discovery 필요로 실패.
Regression results / raw log paths / hashes: regression.txt
  - tests/test_nx06_deploy_readiness.py 14 passed, 좁은 회귀 86 passed
  - 전체 스위트 6499 passed / 9 skipped / 0 failed (수집 6516 = NX-05 6502 + 14)
  - ruff / mypy clean. 대시보드 변경 없음.
Data migration / backup / rollback observed: 제품 데이터 변경 없음(계약·manifest 만).
  rollback = 이전 manifest 적용. 그 경우 readiness 가 다시 /health 를 보므로 endpoint 가 채워져도
  의존성 준비 여부는 보장되지 않는다(README 에 명시). 권장: `/api/ready` 본문을 먼저 확인.
Unverified / reason / impact (BLOCKED 해제 조건):
  (1) 런타임 관측 — 임시 cluster(예: kind/minikube)와 비운영 namespace 가 필요하다. 해제되면
      `kubectl -n <ns> apply -f deploy/k8s/` → `kubectl get pods -w`/`get endpoints`로
      required 실패 시 NotReady+endpoint 제외, 회복 시 복귀, degraded 유지 시 계속 서비스됨을 확인한다.
  (2) NetworkPolicy × CNI 의 kubelet probe 허용 — 실 cluster 에서만 판정 가능(README 에 절차 기록).
  (3) `degraded → 200` 은 신규 설치가 막히지 않게 하려는 결정이다. "degraded 도 endpoint 에서 제외"
      정책을 원하면 ADR 로 바꾼 뒤 `traffic` 판정만 변경하면 된다(시험 1건 수정).
Reviewer verdict / reviewed SHA / artifact: 미지정 — 독립 검토 필요.
Next owner / exact next action: 19번 체크리스트 순서상 NX-07(문서·지원 범위 단일 상태) 또는
  NX-06 의 런타임 해제(cluster 확보 후 BLOCKED 해제). NX-10 전에는 probe 경로와 `traffic` 계약을
  그대로 사용하고, manifest 는 실제 cluster 에서 한 번 이상 처음 설치부터 따라가야 한다.
```

## 1. 왜 `degraded` 를 수용하는가 (검토자가 반드시 판단해야 할 결정)

`not_ready → 503 → endpoint 제외` 만으로는 **신규 설치가 서비스되지 않는다.** 새로 설치한 인스턴스는
활성 프로젝트가 없고(→ `registry: degraded`) 모델도 아직 로드되지 않는다(→ `model_manager: degraded`).
이 상태를 거부하면 사용자가 설정 화면을 열 수 없어 영원히 degraded 로 남는다. 그래서:

- 소프트 실패(정상적인 "아직 준비 안 된 기능")는 `degraded` → 200 으로 수용하고,
- 하드 실패(읽기/쓰기 불가, 크래시)만 `not_ready` → 503 으로 거부한다.

각 검사가 자기 실패모드를 스스로 판정하도록 남겨 두었다 — 예를 들어 `registry` 는 "활성 프로젝트
없음"을 degraded, 크래시를 not_ready 로 보고한다. 분류(`kind`)는 그 판단의 근거를 코드에 남기고
optional 검사가 ready 상태를 막지 못하게 하는 데 쓴다.

## 2. 함께 고친 것 (카드 범위지만 명시 필요)

- **false ready 제거**: `_check_writable_storage()` 가 설정된 프로젝트 루트를 찾지 못하면 `data/`
  로 갈아타 `ready` 를 반환했다. 이제 그 경우 `degraded`(실제 경로를 detail 에 표기)이며,
  프로젝트 루트가 아예 구성되지 않은 신규 설치에서만 데이터 디렉터리를 검사한다.
- **manifest 의 영속 볼륨 계약을 시험으로 고정**: `/app/data`(PIN hash + token secret)와
  `/app/vault_data` 가 PVC 여야 한다 — 아니면 재시작마다 token secret 이 바뀌어 모든 세션이 끊긴다
  (NX-05 의 폐기 계약과 직접 연결).
- **테스트 주입 계약 유지**: `_READINESS_CHECKS` 는 함수 객체가 아니라 이름+kind 를 담고 호출 시점에
  모듈 전역에서 찾는다. 그래야 `monkeypatch.setattr(om, "_check_task_db", …)` 같은 기존 실패 주입이
  계속 동작한다(OBS-01 회귀 시험이 이 계약에 의존한다 — 처음에 함수 객체를 담았다가 두 시험이
  조용히 무력화되어 되돌렸다).

## 3. 변경한 기존 계약 (검토 시 확인 필요)

| 파일 | 이전 | 이후 | 이유 |
|---|---|---|---|
| `compute_readiness()` 반환 | `{status, checks[{name,status,detail}], checked_at}` | + `checks[].kind`, + `traffic` | 판정 근거를 응답 계약으로. 필드 추가라 기존 소비자 호환 |
| `model_manager` 실패 | `not_ready`(→ 전체 not_ready) | `degraded`(optional 로 내려감) | 선택 의존성이 ready 를 막지 못하게. 카드의 "선택 의존성 실패→degraded" |
| `writable_storage` 프로젝트 루트 부재 | `ready` | `degraded` | 마운트되지 않은 볼륨을 ready 로 보고하지 않도록 |
| readinessProbe 경로 | `/health` | `/api/ready` | 카드 1단계(확정 결함) |
| livenessProbe 경로 | `/v1/health` | `/health` | 동일 핸들러지만 역할을 명확히(생존만) |

기존 OBS-01 시험 11건은 그대로 통과한다(계약 위반 없음). 전체 스위트도 0 failed.

## 4. 검토자가 우선 볼 지점

1. `degraded → 200` 결정(§1)이 제품 의도와 맞는지, 아니면 ADR 로 "degraded 도 제외"로 바꿀지.
2. required/optional 분류가 실제 실패모드와 맞는지 — 특히 `model_manager` 를 optional 로 본 근거
   (lazy 로드 + cloud provider 경로)가 이 배포(SKU=로컬 우선)에서 성립하는지.
3. liveness 가 `/health` 라는 점 — 의존성 실패로 재시작하지 않는 대신, 프로세스는 살아 있지만
   아무 것도 못 하는 상태가 readiness 로만 표현된다. 이 조합이 운영 runbook 과 맞는지.
4. NetworkPolicy 가 kubelet probe 를 막지 않는지(실 cluster 필요) — README 에 확인 절차만 있다.
