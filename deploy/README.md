# Deployment

Ssak-Ai can be deployed in three ways, in increasing order of production
readiness.

## 1. Local (development)

```bash
make dev
# or
pip install -e ".[dev,rag]"
agk  # CLI entry point
```

## 2. Docker

A hardened multi-stage Dockerfile is provided.

```bash
# Build
make docker-build

# Run (single container)
docker run -d \
  -p 8000:8000 \
  -v "$PWD/vault_data:/app/vault_data" \
  -v "$PWD/data:/app/data" \
  -e AGK_SEC_ACCESS_PIN='<your-pin>' \
  --name antigravity-k \
  antigravity-k:latest
```

The image runs as a non-root user (`agk`, uid 1001) and excludes dev
dependencies from the runtime stage.

### Docker Compose

```bash
docker compose up -d
```

Edit `docker-compose.yml` to set `AGK_SEC_ACCESS_PIN` and mount paths.

## 3. Kubernetes

Manifests are in `deploy/k8s/`. They provide a non-root security context,
resource limits, liveness/readiness probes, persistent volumes, a NetworkPolicy,
and an Ingress.

### Prerequisites

- A Kubernetes cluster (1.27+) with an ingress controller.
- A container registry hosting the image (e.g. `ghcr.io/<owner>/antigravity-k`).

### Steps (order matters)

A Secret cannot be created before its namespace exists, so the install is split
in three steps. Applying the whole directory at once leaves the Namespace/Secret
order undefined.

```bash
# 1. Namespace first.
kubectl apply -f deploy/k8s/namespace.yaml

# 2. Auth secret inside that namespace.
kubectl create secret generic antigravity-k-auth \
  --namespace=antigravity-k \
  --from-literal=AGK_SEC_ACCESS_PIN='<your-strong-pin>'

# 3. Everything else (Deployment/Service/Ingress/PVC/NetworkPolicy/PDB).
kubectl apply -f deploy/k8s/

# 4. Check rollout and readiness.
kubectl -n antigravity-k rollout status deployment/antigravity-k
kubectl -n antigravity-k get endpoints antigravity-k      # ready pod 가 있어야 채워진다

# 5. Port-forward to test (before configuring Ingress/DNS).
kubectl -n antigravity-k port-forward svc/antigravity-k 8080:80
curl -s localhost:8080/api/ready | python3 -m json.tool     # 인증 없이 열리는 진단 경로
```

**Missing or weak secret fails closed.** 파드는 `CreateContainerConfigError`
(secret 없음) 또는 시작 직후 종료(`StartupSecurityError`: production/non-loopback
에서 8자 미만 PIN + 유효 hash 없음)로 실패한다. 요청을 서비스하는 상태로
넘어가지 않는다.

**Remove only what this directory created.**

```bash
kubectl delete -f deploy/k8s/          # 이 디렉터리의 자원만 삭제
# namespace 는 다른 자원까지 함께 지우므로 따로 판단한다:
# kubectl delete ns antigravity-k
```

이전 manifest 로 되돌리기: `git show <이전 SHA>:deploy/k8s/deployment.yaml > /tmp/prev-deployment.yaml`
후 `kubectl apply -f /tmp/prev-deployment.yaml`. 되돌아간 뒤 `kubectl get endpoints` 가
비어 있다면 readiness 를 무시하지 말고 `/api/ready` 본문에서 실패한 검사
(`status`/`traffic`/`checks[].detail`)를 먼저 확인한다.

### Probe 와 트래픽 정책

| probe | 경로 | 보는 것 | 실패 시 동작 |
|---|---|---|---|
| `startupProbe` | `/health` | 프로세스 응답 | 최대 5분(5초+10초×30)까지 liveness/readiness 유예 |
| `livenessProbe` | `/health` | 프로세스 생존만 | 컨테이너 재시작. **의존성 검사를 쓰지 않는다** — 모델 로드/다운로드가 restart loop 가 되면 안 된다 |
| `readinessProbe` | `/api/ready` | task DB / registry / writable storage / model manager | 503 → EndpointSlice 에서 제외(약 30초 뒤). degraded 는 제외하지 않는다 |

`/api/ready` 계약 (`compute_readiness()`):

| status | 조건 | HTTP | traffic | kubernetes 효과 |
|---|---|---|---|---|
| `ready` | required·optional 모두 ready | 200 | `accept` | endpoint 유지 |
| `degraded` | required 전부 ready + optional ≥1 실패 | 200 | `accept` | endpoint 유지 |
| `not_ready` | required 검사가 하나라도 ready 아님 | 503 | `reject` | endpoint 제외 |

의존성 분류(코드에 `checks[].kind` 로 노출):

| 검사 | kind | 왜 | 소프트/하드 실패모드 |
|---|---|---|---|
| `task_db` | required | 작업 원장을 읽을 수 없으면 task API 가 의미를 잃는다 | 생성 전이면 `ready`, 읽기 실패는 `not_ready` |
| `registry` | required | 프로젝트 해석이 불가하면 프로젝트 범위 요청이 전부 실패한다 | **활성 프로젝트 없음(신규 설치)은 `degraded`**, 크래시는 `not_ready` |
| `writable_storage` | required | 세션·산출물·대화를 저장할 수 없으면 요청을 받으면 안 된다 | 설정된 프로젝트 루트가 없으면 `degraded`, 쓰기 실패는 `not_ready` |
| `model_manager` | optional | 모델은 lazy 로드이고 cloud provider 경로도 있다 | 미로드/미가용은 `degraded`(not_ready 도 degraded 로 내려간다) |

**왜 `degraded` 를 수용하는가:** 신규 설치의 정상 상태(활성 프로젝트 없음,
모델 미로드)를 트래픽 거부로 처리하면 서비스가 영원히 열리지 않는다. 대신
required 검사 실패는 상태와 무관하게 503(`traffic: reject`)이며, single replica
배포에서는 이때 endpoint 가 비어 "잘못된 응답" 대신 "연결 실패"가 된다.

### Notes

- The Deployment uses `strategy: Recreate` with a single replica because the
  vault uses file-based Git locking. Scaling to multiple replicas requires a
  shared-writable volume (ReadWriteMany) or an external Git backend.
- **Edit** the Ingress `host` (`antigravity-k.example.com`) and TLS secret to
  match your domain.
- **Replace** the image reference in `deployment.yaml` with your registry path.
- The `AGK_ENABLE_TERMINAL_WS` env var is not set by default — the terminal
  WebSocket stays disabled in Kubernetes for security. Enable it only if you
  understand the risk and have network-level access controls in place.
- **NetworkPolicy 와 kubelet probe**: `antigravity-k-deny-ingress` 는 ingress-nginx
  와 kube-system 에서 오는 TCP 8000 만 허용한다. 대부분의 CNI 는 node(kubelet)
  에서 오는 probe 를 별도로 허용하지만, 모든 CNI 가 그렇지는 않다. probe 가
  실패해 파드가 ready 가 되지 않으면 CNI 의 node→pod 트래픽 허용 여부를 먼저
  확인하고, 필요하면 node 대역을 허용하는 규칙을 추가한다(`kubectl describe
  networkpolicy` + `kubectl get events -n antigravity-k`).
- readiness 는 매 주기 `/api/ready` 를 호출하므로 진단 정보다 — `checks[].detail`
  에는 경로와 오류 클래스만 담기고 secret 은 담기지 않는다. probe 응답을
  외부에 노출하지 않도록 Ingress 에서는 그대로 두고, 운영 runbook 에서만
  `kubectl -n antigravity-k exec deploy/antigravity-k -- curl -s localhost:8000/api/ready`
  로 읽는다.

## CI/CD

- **`ci.yml`**: lint, test (ubuntu + macOS matrix), build, security scan, SBOM.
- **`container-scan.yml`**: Trivy image scan (HIGH/CRITICAL) on Dockerfile changes.
- **`release.yml`**: on `v*` tags, builds wheel + sdist, publishes to PyPI via
  Trusted Publishing (OIDC, no stored tokens), creates a GitHub Release.

Every Python distribution, dashboard bundle, and Pages payload now receives a
SHA-256 provenance manifest. The CI and release jobs verify the manifest before
upload or deployment, so a changed artifact fails the pipeline. Locally, run
`make build-provenance` or `make dashboard-build-provenance`; use
`make dashboard-provenance-verify` to re-check an existing bundle.

To attach the verified manifest to a task timeline, configure the repository
variable `AGK_PROVENANCE_API_URL` and secret `AGK_PROVENANCE_PIN`. The workflow
creates an execution-free provenance task automatically when
`AGK_PROVENANCE_TASK_ID` is unset; set that variable to reuse an existing task.

### Creating a release

```bash
# Tag and push.
git tag v0.2.0
git push origin v0.2.0
# The release workflow builds, publishes to PyPI, and creates a GitHub Release.
```

Before the first PyPI publish, configure Trusted Publishing at
<https://pypi.org/manage/account/publishing/> pointing to this repository's
`release.yml` workflow.

## Observability

- **Prometheus**: scrape `http://<host>/metrics` for RED metrics (request count,
  latency histogram, in-flight gauge) and process uptime.
- **Health**: `GET /health` and `GET /v1/health` (public, for load balancers);
  `GET /api/health/deep` (requires auth, returns component-level status).
- **Correlation IDs**: every response includes an `X-Request-Id` header for
  tracing. Server-side logs include the same id.
