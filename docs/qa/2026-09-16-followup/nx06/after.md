---
title: NX-06 after — probe 역할 분리와 readiness 판정 계약
created: 2026-09-16
tags: [nx-06, after, evidence, deploy]
---

# NX-06 after — 같은 입력에서 관측된 변화

```sh
NX06_TREE=after PYTHONPATH=src .venv/bin/python \
  docs/qa/2026-09-16-followup/nx06/repro_nx06_readiness_probe.py    # → exit 0
```

`after-run-output.json` (발췌):

```json
{
  "readiness_probe_path": "/api/ready",
  "liveness_probe_path": "/health",
  "startup_probe_path": "/health",
  "readiness_reports_dependencies": true,
  "report_keys": ["checked_at", "checks", "status", "traffic"],
  "has_dependency_kind": true,
  "has_traffic_verdict": true,
  "missing_project_root_status": "degraded",
  "missing_project_root_detail": "storage: configured project root missing (/nonexistent/nx06-configured-root)",
  "false_ready_on_missing_root": false,
  "required_failure_status": "not_ready",
  "required_failure_traffic": "reject",
  "required_failure_rejected": true,
  "optional_failure_status": "degraded",
  "optional_failure_traffic": "accept",
  "optional_failure_served": true,
  "degraded_is_accepted": true,
  "runtime_observation": "BLOCKED (no kube context)",
  "defects": [],
  "contract_met": true
}
```

## 1. 구현한 계약

| 요소 | 이전 | 이후 |
|---|---|---|
| readinessProbe | `/health`(프로세스 생존) | **`/api/ready`**(task DB / registry / writable storage / model manager) |
| livenessProbe | `/v1/health` | `/health` — 프로세스 생존만. 의존성 실패로 컨테이너를 재시작하지 않는다 |
| startupProbe | `/v1/health` | `/health` — 초기화(모델 다운로드 포함) 동안 liveness/readiness 유예(최대 5분) |
| readiness 보고서 | `{status, checks, checked_at}` | + `checks[].kind`(required/optional), + `traffic`(accept/reject) |
| 판정 | 서버 코드의 `status == "not_ready"` 비교 | `report["traffic"] == "reject"` — 계약이 응답 본문과 일치 |
| optional 의존성 | 실패 시 `not_ready` 가능 | optional 검사의 `not_ready` 는 `degraded` 로 내려가 트래픽을 막지 않는다 |
| false ready | 설정된 프로젝트 루트 부재 → `ready` | `degraded` + 실제 경로를 detail 에 표기 |
| 설치 순서 | README 가 Secret→apply (namespace 부재로 실패) | namespace → Secret → 나머지, 세 단계로 분리 |

의존성 분류(README 표와 시험으로 1:1 고정):

| 검사 | kind | 하드 실패 | 소프트 실패 |
|---|---|---|---|
| `task_db` | required | 읽기 실패 → `not_ready`(503) | 아직 생성 전 → `ready` |
| `registry` | required | 크래시 → `not_ready`(503) | 활성 프로젝트 없음(신규 설치) → `degraded`(200) |
| `writable_storage` | required | 쓰기 실패 → `not_ready`(503) | 설정된 루트 부재 → `degraded`(200) |
| `model_manager` | optional | — (degraded 로 내려감) | 미로드/크래시 → `degraded`(200) |

## 2. 카드 시험 ↔ 구현 매핑

| 카드 시험 | 구현 |
|---|---|
| 정상 readiness | `test_readiness_classification_matches_the_documented_table` + `/api/ready` 200 경로 |
| 필수 의존성 실패 → 503/endpoint 제외 | `test_required_failure_rejects_traffic_with_503` (503 + `traffic: reject`) |
| 회복 → 복귀 | `test_readiness_recovers_to_200_after_the_dependency_returns` |
| 선택 의존성 실패 → degraded | `test_optional_failure_is_served_as_degraded` (200 + `accept` + detail 표기) |
| 컨테이너 시작 지연 | `test_liveness_stays_200_while_readiness_fails` — 모든 required 검사가 실패해도 `/health` 는 200(재시작 루프 금지), startup 유예는 manifest 시작값으로 고정 |
| 잘못된 인증 secret 은 안전하게 실패 | `test_bad_auth_secret_fails_closed_at_startup` (production + 0.0.0.0 + 약한 PIN + hash 없음 → `StartupSecurityError`) |
| 생성한 namespace 만 삭제 | `test_install_order_and_removal_scope_are_documented` (`kubectl delete -f deploy/k8s/` + namespace 별도 판단 문구) |
| manifest 정적 검증 | `test_readiness_probe_uses_dependency_check_not_process_health`, `test_probe_ports_and_resource_names_are_consistent`, `test_every_namespaced_resource_uses_the_created_namespace`, `test_deployment_fails_closed_without_the_auth_secret`, `test_readiness_and_health_paths_are_public_for_probes` |
| secret 미노출 | `test_readiness_never_exposes_secret_material` (응답 문자열에 pin/token/secret/password 부재) |
| false ready 재발 방지 | `test_missing_configured_project_root_is_not_reported_as_ready` + 드라이버 |

## 3. 운영 영향 / rollback

- single replica + `strategy: Recreate` 이므로 required 실패 시 endpoint 가 비어 **연결 실패**로
  나타난다(잘못된 200 응답 대신). degraded 는 계속 서비스되므로 신규 설치가 막히지 않는다.
- `/app/data`(PIN hash + token secret)와 `/app/vault_data` 는 모두 PVC 다 — 영속 볼륨이 없으면
  재시작마다 secret 이 바뀌어 모든 세션이 끊긴다(NX-05 폐기 계약과 연결되는 조건, 시험으로 고정).
- rollback: 이전 manifest 를 적용하면 readiness 가 다시 `/health` 를 본다 → `kubectl get endpoints`
  가 차 있어도 의존성이 준비되었는지는 보장되지 않는다. README 에 명시했다.
- **런타임 관측은 BLOCKED**: cluster/kube context 가 없어 Pod readiness·EndpointSlice 는 관측하지
  못했다. 정적 수정은 REVIEW 이며, DONE 로 올리려면 카드대로 실제 cluster 관측이 필요하다.
