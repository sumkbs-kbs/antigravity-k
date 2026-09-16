---
title: NX-06 before (HEAD ffb0ebb3, readiness 가 프로세스 생존을 보고 있었다)
created: 2026-09-16
tags: [nx-06, before, evidence, deploy]
---

# NX-06 before — probe 역할이 뒤바뀌고 readiness 가 false ready 를 보고할 수 있었다

## 1. 기준 상태

```yaml
# deploy/k8s/deployment.yaml (HEAD)  — 발췌
livenessProbe:   {httpGet: {path: /v1/health}}
readinessProbe:  {httpGet: {path: /health}}      # ← 의존성 검사가 아니다
startupProbe:    {httpGet: {path: /v1/health}}
```

```python
# src/antigravity_k/api/routes/models_api.py (HEAD)
@router.get("/health")
@router.get("/v1/health")
def health_check() -> dict[str, object]:
    ...
    return {"status": "ok", ...}      # 의존성이 모두 죽어도 200
```

즉 `/health` 는 프로세스가 응답하면 항상 200 이고, 실제 의존성 readiness 를 구현한
`/api/ready`(OBS-01: required 실패 시 503)는 **manifest 어디에서도 쓰이지 않았다.**
그 결과 저장소가 읽기 전용이거나 task DB 가 깨져도 Pod 은 Ready 로 남아 트래픽을 받는다.

## 2. 재현 (기준 트리 = `git archive HEAD deploy src`)

```sh
NX06_TREE=before NX06_MANIFEST_DIR=/tmp/nx06-before/deploy/k8s \
  PYTHONPATH=/tmp/nx06-before/src .venv/bin/python \
  docs/qa/2026-09-16-followup/nx06/repro_nx06_readiness_probe.py    # → exit 3
```

`before-run-output.json` (발췌):

```json
{
  "readiness_probe_path": "/health",
  "liveness_probe_path": "/v1/health",
  "startup_probe_path": "/v1/health",
  "readiness_reports_dependencies": false,
  "report_keys": ["checked_at", "checks", "status"],
  "has_dependency_kind": false,
  "has_traffic_verdict": false,
  "missing_project_root_status": "ready",
  "missing_project_root_detail": "writable: data",
  "false_ready_on_missing_root": true,
  "kube_contexts": [],
  "runtime_observation": "BLOCKED (no kube context)",
  "defects": [
    "readinessProbe does not use /api/ready",
    "missing configured project root reported as ready",
    "required failure is not rejected",
    "degraded is not served"
  ]
}
```

### 확인된 결함

1. **readiness 가 의존성을 보지 않는다** — probe 가 `/health` 라 required 검사 실패가
   EndpointSlice 제외로 이어지지 않는다(카드 1단계 결함).
2. **liveness 가 정보성 endpoint 를 쓴다** — `/v1/health` 는 `/health` 와 같은 핸들러이며
   항상 200 이므로 위험은 낮지만, 의존성 판정과 역할이 문서화되어 있지 않았다.
3. **false ready** — `_check_writable_storage()` 는 설정된 프로젝트 루트가 존재하지 않으면
   조용히 `data/` 로 갈아타 `ready` 를 돌려준다(`missing_project_root_detail: "writable: data"`).
   마운트되지 않은 PVC 를 "정상"으로 보고하고 트래픽을 받게 만든다.
4. **판정 근거가 응답에 없다** — 보고서에 의존성 분류(`kind`)도 트래픽 판정(`traffic`)도 없어서
   "degraded 200 이 적절한가"를 계약으로 표현할 수 없었다(문서로만 존재).
5. **설치 순서가 성립하지 않는다** — `deploy/README.md` 는 1) Secret 생성 2) manifest apply
   순서였는데, namespace 를 만드는 것은 2단계의 `namespace.yaml` 이다. 즉 README 를 그대로
   따르면 1단계 Secret 생성이 namespace 부재로 실패한다.

### 확인하지 못한 것 (BLOCKED)

- **Pod/EndpointSlice 런타임 관측**: `kubectl config get-contexts` 결과가 비어 있고
  (`kube_contexts: []`), cluster 가 없어 `kubectl apply --dry-run=client` 조차 API discovery
  단계에서 실패한다(`unable to recognize "deploy/k8s/deployment.yaml"`). 카드가 요구한
  "실제 Pod readiness/EndpointSlice 관측"은 **BLOCKED** 이며 정적 수정만 REVIEW 로 남긴다.
- 네트워크 정책(CNI 별 kubelet probe 허용 여부)은 실 cluster 없이 판정할 수 없다 — README 에
  확인 절차로 남겼다.
