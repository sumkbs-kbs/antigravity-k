# Deployment

Antigravity-K can be deployed in three ways, in increasing order of production
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

### Steps

```bash
# 1. Create the auth secret.
kubectl create secret generic antigravity-k-auth \
  --namespace=antigravity-k \
  --from-literal=AGK_SEC_ACCESS_PIN='<your-strong-pin>'

# 2. Apply the manifests.
kubectl apply -f deploy/k8s/

# 3. Check rollout.
kubectl -n antigravity-k rollout status deployment/antigravity-k

# 4. Port-forward to test (before configuring Ingress/DNS).
kubectl -n antigravity-k port-forward svc/antigravity-k 8080:80
```

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

## CI/CD

- **`ci.yml`**: lint, test (ubuntu + macOS matrix), build, security scan, SBOM.
- **`container-scan.yml`**: Trivy image scan (HIGH/CRITICAL) on Dockerfile changes.
- **`release.yml`**: on `v*` tags, builds wheel + sdist, publishes to PyPI via
  Trusted Publishing (OIDC, no stored tokens), creates a GitHub Release.

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
