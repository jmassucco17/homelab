# k3s Migration Plan

## Overview

This document describes how to migrate the homelab from its current Docker Compose–based
deployment model to a **k3s** (lightweight Kubernetes) cluster running on the same
Hetzner VPS.

The migration is intentionally incremental. The plan is organized into self-contained
phases that can be executed one at a time, with the existing Docker Compose stack
continuing to serve production traffic between phases.

---

## Goals

- Replace `scripts/start_service.sh` + SSH-based CI deploys with `kubectl apply`.
- Keep the same Traefik v3 reverse proxy, Cloudflare DDNS, and Google OAuth setup.
- Preserve TLS automation (Cloudflare DNS challenge), replacing Traefik's built-in ACME
  with **cert-manager**.
- Replace Docker volumes with **PersistentVolumeClaims** backed by k3s's default
  `local-path` provisioner.
- Replace per-service `.env` files with **Kubernetes Secrets**.
- Maintain staging and production environments via separate Kubernetes namespaces.
- Keep the same GHCR image registry and GitHub Actions build pipeline.
- Remove the dependency on Tailscale + SSH for CI deploys (use kubeconfig instead).

---

## Why k3s?

| Property | Docker Compose | k3s |
|----------|---------------|-----|
| Rolling updates | Manual `down` + `up` | Built-in (Deployment rollout) |
| Health-based restarts | `restart: unless-stopped` | Liveness / readiness probes |
| Declarative state | Per-service YAML files | Single desired-state cluster |
| Secret management | `.env` files assembled at deploy time | Native Kubernetes Secrets |
| Multi-container coordination | `depends_on` | Init containers, readiness gates |
| Resource quotas | None | Namespace-level `LimitRange` / `ResourceQuota` |
| Path to multi-node | Requires Docker Swarm | Add worker node + `k3sup join` |
| CI deploy mechanism | SSH + `docker compose up` | `kubectl apply` over kubeconfig |

k3s is chosen over full Kubernetes or k8s distributions (kind, minikube, kubeadm) because
it ships as a single binary, has a sub-30-second install on the VPS, bundles a
`local-path` storage provisioner and Traefik ingress controller out of the box, and uses
under 512 MB RAM in a minimal configuration — appropriate for a single-node personal
homelab.

---

## Architecture: Before vs. After

### Before (Docker Compose)

```
Hetzner VPS
└── Docker
    ├── networking/       traefik + oauth2-proxy + cloudflare-ddns + whoami
    ├── monitoring/       node-exporter + cadvisor + alloy
    ├── shared-assets/    nginx
    ├── homepage/         nginx
    ├── blog/             FastAPI (uvicorn)
    ├── travel/           FastAPI (uvicorn) + SQLite volume
    ├── games/            FastAPI (uvicorn)
    ├── tools/            FastAPI (uvicorn)
    └── portainer/        Portainer CE

Networks: web (external), internal_metrics (external)
TLS: Traefik ACME, stored in acme.json bind-mount
Secrets: .env files written from GitHub secrets at deploy time via SSH
CI deploy: SCP archive → SSH → docker compose up
```

### After (k3s)

```
Hetzner VPS
└── k3s (single-node cluster)
    ├── kube-system/
    │   ├── traefik          (Traefik v3 IngressController, Helm chart)
    │   └── cert-manager     (TLS automation via Cloudflare DNS)
    ├── production/          (namespace)
    │   ├── cloudflare-ddns  (DaemonSet, hostNetwork)
    │   ├── oauth2-proxy     (Deployment + Service + IngressRoute)
    │   ├── shared-assets    (Deployment + Service + IngressRoute)
    │   ├── homepage         (Deployment + Service + IngressRoute)
    │   ├── blog             (Deployment + Service + IngressRoute)
    │   ├── travel           (Deployment + Service + IngressRoute + PVC)
    │   ├── games            (Deployment + Service + IngressRoute)
    │   ├── tools            (Deployment + Service + IngressRoute)
    │   └── monitoring       (node-exporter DaemonSet + cadvisor + alloy)
    └── staging/             (namespace — mirrors production)
        └── ... (same services, different IngressRoutes and image tags)

TLS: cert-manager ClusterIssuer (Cloudflare DNS-01 challenge) → Certificate → TLS Secret
Secrets: Kubernetes Secrets applied by CI (kubectl create secret)
CI deploy: docker build + push to GHCR → kubectl apply manifests (via kubeconfig)
```

---

## Concept Mapping

| Docker Compose concept | Kubernetes / k3s equivalent |
|------------------------|----------------------------|
| `docker-compose.yml` service | `Deployment` + `Service` manifest |
| `docker-compose.prod.yml` labels | `IngressRoute` (Traefik CRD) or `Ingress` |
| `docker-compose.staging.yml` | Kustomize overlay targeting `staging` namespace |
| Docker named volume | `PersistentVolumeClaim` (local-path provisioner) |
| Docker network `web` | Kubernetes `Service` (cluster-internal DNS) |
| Docker network `internal_metrics` | Kubernetes `Service` (ClusterIP, no Ingress) |
| `.env` file | Kubernetes `Secret` (Opaque) |
| `restart: unless-stopped` | `restartPolicy: Always` (Deployment default) |
| `healthcheck:` | `livenessProbe` + `readinessProbe` |
| `depends_on:` | Init containers or readiness gates |
| `pid: host` (node-exporter) | `hostPID: true` on the Pod spec |
| `network_mode: host` (ddns) | `hostNetwork: true` on the Pod spec |
| Traefik Docker label routing | `IngressRoute` (Traefik CRD) |
| Traefik middleware label | `Middleware` CRD referenced by `IngressRoute` |
| Traefik ACME `acme.json` | cert-manager `Certificate` → `Secret` |
| `scripts/start_service.sh` | `kubectl apply -f k8s/<service>/` |
| GitHub Actions SSH deploy | `kubectl apply` using `KUBECONFIG` secret |

---

## New Directory Structure

All Kubernetes manifests live under a new top-level `k8s/` directory. The layout mirrors
the existing module structure:

```
k8s/
├── README.md
├── base/                       # Shared resources
│   ├── namespaces.yaml         # production + staging namespaces
│   └── middlewares.yaml        # Traefik Middleware CRDs (ratelimit, oauth-auth)
├── traefik/
│   ├── helmchart.yaml          # HelmChart CRD overriding k3s built-in Traefik
│   └── cluster-issuer.yaml     # cert-manager ClusterIssuer (Cloudflare DNS-01)
├── networking/
│   ├── oauth2-proxy.yaml       # Deployment + Service + IngressRoute
│   ├── cloudflare-ddns.yaml    # DaemonSet (hostNetwork)
│   └── whoami.yaml             # Deployment + Service + IngressRoute
├── monitoring/
│   ├── node-exporter.yaml      # DaemonSet (hostPID + hostNetwork)
│   ├── cadvisor.yaml           # DaemonSet
│   └── alloy.yaml              # Deployment + ConfigMap
├── shared-assets/
│   └── deployment.yaml         # Deployment + Service + IngressRoute
├── homepage/
│   └── deployment.yaml
├── blog/
│   └── deployment.yaml
├── travel/
│   ├── deployment.yaml         # includes PVC reference
│   └── pvc.yaml
├── games/
│   └── deployment.yaml
├── tools/
│   └── deployment.yaml         # includes Secret reference for TMDB_API_KEY
└── portainer/
    └── deployment.yaml         # Portainer for Kubernetes
```

Staging-specific configuration uses **Kustomize overlays** in a `k8s/overlays/staging/`
directory that patches the `production` base to target the `staging` namespace and use
the staging image tag and subdomain.

---

## Phase 1: k3s Installation and Cluster Foundation

### 1.1 Install k3s on the server

```bash
# Run on the VPS
curl -sfL https://get.k3s.io | sh -s - \
  --disable traefik \
  --write-kubeconfig-mode 644
```

The `--disable traefik` flag prevents k3s from installing its bundled Traefik v2; we
will install Traefik v3 ourselves via the `HelmChart` CRD in Phase 2.

### 1.2 Export kubeconfig for CI

```bash
# On the VPS
cat /etc/rancher/k3s/k3s.yaml
```

Replace `127.0.0.1` in `server:` with the VPS's Tailscale IP. Store the full kubeconfig
content as a new GitHub Actions secret `K8S_KUBECONFIG`.

CI workflows then authenticate with:
```yaml
- name: Configure kubectl
  env:
    KUBECONFIG_DATA: ${{ secrets.K8S_KUBECONFIG }}
  run: |
    mkdir -p ~/.kube
    printf '%s' "$KUBECONFIG_DATA" > ~/.kube/config
    chmod 600 ~/.kube/config
```

This replaces the Tailscale + SSH setup for all deploy jobs. The Tailscale connection is
still needed (to reach the VPS's private Tailscale IP in the kubeconfig), but SSH and
SCP are no longer required.

### 1.3 Create namespaces

`k8s/base/namespaces.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: staging
```

---

## Phase 2: Traefik v3 and TLS

### 2.1 Install Traefik v3 via HelmChart CRD

k3s supports a native `HelmChart` CRD that installs Helm charts automatically. Create
`k8s/traefik/helmchart.yaml`:

```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: traefik
  namespace: kube-system
spec:
  chart: traefik
  repo: https://traefik.github.io/charts
  version: "32.x"   # Traefik v3 chart; pin to a specific version
  targetNamespace: kube-system
  valuesContent: |-
    image:
      tag: v3.3
    ports:
      web:
        redirectTo:
          port: websecure
      metrics:
        expose:
          default: false
    providers:
      kubernetesCRD:
        enabled: true
      kubernetesIngress:
        enabled: false
    certificatesResolvers: {}   # cert-manager handles TLS; disable Traefik ACME
    logs:
      access:
        enabled: true
```

### 2.2 Install cert-manager

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

Or, preferably, as a HelmChart CRD alongside the Traefik chart (keep it in the repo):

`k8s/traefik/cert-manager-helmchart.yaml`:
```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: cert-manager
  namespace: kube-system
spec:
  chart: cert-manager
  repo: https://charts.jetstack.io
  version: "v1.17.x"
  targetNamespace: cert-manager
  valuesContent: |-
    crds:
      enabled: true
```

### 2.3 Create the Cloudflare ClusterIssuer

The existing `CLOUDFLARE_API_TOKEN` secret is reused. A Kubernetes Secret exposes it
to cert-manager:

```yaml
# k8s/traefik/cluster-issuer.yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-api-token
  namespace: cert-manager
type: Opaque
stringData:
  api-token: <CLOUDFLARE_API_TOKEN>   # applied by CI from secret; not committed
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: cloudflare-dns
spec:
  acme:
    email: <CLOUDFLARE_API_EMAIL>
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: api-token
```

CI applies this using `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_API_EMAIL` from GitHub
secrets (the same secrets already in use).

### 2.4 Define global Traefik Middlewares

`k8s/base/middlewares.yaml` (applied to the `production` namespace):

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: ratelimit
  namespace: production
spec:
  rateLimit:
    average: 50
    burst: 100
---
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: oauth-auth
  namespace: production
spec:
  forwardAuth:
    address: http://oauth2-proxy.production.svc.cluster.local:4180
    trustForwardHeader: true
    authResponseHeaders:
      - X-Auth-Request-User
      - X-Auth-Request-Email
```

These replace the Traefik `middlewares.ratelimit.*` and `middlewares.oauth-auth.*` Docker
labels that currently live in `networking/docker-compose.yml`.

---

## Phase 3: Service Migration

Each service follows the same pattern. Below is the pattern, followed by service-specific
notes.

### Standard service manifest pattern

```yaml
# k8s/<service>/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <service>
  namespace: production
spec:
  replicas: 1
  selector:
    matchLabels:
      app: <service>
  template:
    metadata:
      labels:
        app: <service>
    spec:
      containers:
        - name: <service>
          image: ghcr.io/jmassucco17/homelab/<service>:latest
          ports:
            - containerPort: <port>
          readinessProbe:
            httpGet:
              path: /health
              port: <port>
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: <port>
            initialDelaySeconds: 10
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: <service>
  namespace: production
spec:
  selector:
    app: <service>
  ports:
    - port: <port>
      targetPort: <port>
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: <service>-tls
  namespace: production
spec:
  secretName: <service>-tls
  issuerRef:
    name: cloudflare-dns
    kind: ClusterIssuer
  dnsNames:
    - <subdomain>.jamesmassucco.com
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: <service>
  namespace: production
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`<subdomain>.jamesmassucco.com`)
      kind: Rule
      services:
        - name: <service>
          port: <port>
  tls:
    secretName: <service>-tls
```

### Service-specific notes

#### `networking` (oauth2-proxy + cloudflare-ddns + whoami)

- **oauth2-proxy**: Becomes a standard `Deployment + Service`. The `--cookie-domain`
  flag and all environment variables are the same; they move from Docker `environment:`
  to a Kubernetes `Secret` + `envFrom`.
- **cloudflare-ddns**: Requires `hostNetwork: true` on the Pod spec (replacing
  `network_mode: host`). Deploy as a `Deployment` with a single replica in the
  `production` namespace; no IngressRoute needed.
- **whoami**: Standard `Deployment + Service + IngressRoute` with the `oauth-auth` and
  `ratelimit` middlewares.
- **Traefik dashboard**: Exposed via an `IngressRoute` in the `kube-system` namespace
  pointing to the `api@internal` service; protected by the `oauth-auth` middleware.

#### `monitoring` (node-exporter + cadvisor + alloy)

- **node-exporter**: Becomes a `DaemonSet` with `hostPID: true`, `hostNetwork: true`,
  and the `/` → `/host` volume mount — same privileged access as the Docker `pid: host`
  configuration.
- **cadvisor**: Becomes a `DaemonSet` with the same host volume mounts (`/`, `/var/run`,
  `/sys`, `/var/lib/docker`, `/dev/disk`).
- **alloy**: Becomes a `Deployment`. The `alloy-config.alloy` file moves to a
  `ConfigMap`; the Docker socket mount (`/var/run/docker.sock`) is replaced with the
  Kubernetes API server discovery target (update `loki.source.kubernetes` and
  `prometheus.scrape` to use k8s service discovery). The Grafana Cloud credentials move
  from `monitoring/.env` to a Kubernetes `Secret`.
- The `internal_metrics` Docker network is replaced by direct Kubernetes `Service`
  DNS (e.g. `node-exporter.monitoring.svc.cluster.local:9100`). Deploy in a dedicated
  `monitoring` namespace (not `production` or `staging`).

#### `travel` (persistent storage)

The `travel-site_data-volume` Docker volume becomes a `PersistentVolumeClaim`:

```yaml
# k8s/travel/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: travel-data
  namespace: production
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 5Gi
```

The `Deployment` mounts it at `/data`.

**Data migration**: When cutting over, copy the existing Docker volume contents to the
PVC. The volume data lives on the host at
`/var/lib/docker/volumes/travel-site_data-volume/_data/`.

```bash
# 1. Stop the old travel container
docker compose -f /opt/homelab/travel/docker-compose.yml \
               -f /opt/homelab/travel/docker-compose.prod.yml down

# 2. Start a migration pod that mounts the PVC
kubectl apply -n production -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: volume-migration
spec:
  containers:
    - name: vol
      image: alpine
      command: ["sleep", "3600"]
      volumeMounts:
        - name: pvc
          mountPath: /data
  volumes:
    - name: pvc
      persistentVolumeClaim:
        claimName: travel-data
EOF
kubectl wait --for=condition=Ready pod/volume-migration -n production

# 3. Copy Docker volume contents into the PVC via kubectl cp
kubectl cp -n production \
  /var/lib/docker/volumes/travel-site_data-volume/_data/. \
  volume-migration:/data/

# 4. Verify and clean up
kubectl exec -n production volume-migration -- ls /data
kubectl delete pod volume-migration -n production
```

#### `tools` (TMDB_API_KEY secret)

The `TMDB_API_KEY` environment variable moves from `tools/.env` to a Kubernetes `Secret`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tools-env
  namespace: production
type: Opaque
stringData:
  TMDB_API_KEY: <value>
```

Referenced in the Deployment:
```yaml
envFrom:
  - secretRef:
      name: tools-env
```

#### `portainer`

Portainer CE has a Kubernetes deployment mode. Replace the Docker Compose deployment with
[Portainer's official Kubernetes install](https://docs.portainer.io/start/install-ce/server/kubernetes/baremetal).
Alternatively, replace Portainer entirely with a lightweight Kubernetes dashboard (the
Kubernetes Dashboard or k9s for CLI use). The Docker socket volume mount is no longer
valid in a k3s context.

---

## Phase 4: CI/CD Pipeline Migration

### Current flow (Docker Compose)

```
push to main
  → _prep-server.yml: assemble .env files + SCP archive → SSH extract
  → _build-*.yml: docker build + push to GHCR
  → _deploy-*.yml: SSH → scripts/start_service.sh
```

### New flow (k3s)

```
push to main
  → build jobs: docker build + push to GHCR  (unchanged)
  → deploy job: kubectl apply k8s/<service>/  (replaces SSH deploy)
```

### Changes to `.github/workflows/`

#### Remove
- `_prep-server.yml` — no longer needed; manifests are applied directly.
- All Tailscale + SSH setup steps from deploy jobs (replaced by kubeconfig).
- `scripts/start_service.sh` — replaced by `kubectl apply`.
- `scripts/start_service.sh --staging` — replaced by Kustomize overlay apply.

#### Replace `_deploy-*.yml` with a single `_deploy.yml`

The three deploy workflow files (`_deploy-simple.yml`, `_deploy-python.yml`,
`_deploy-ots.yml`) are replaced by a single reusable workflow that:

1. Configures kubectl from the `K8S_KUBECONFIG` secret.
2. Creates or updates Kubernetes Secrets from GitHub secrets (idempotent `kubectl create
   secret --dry-run=client -o yaml | kubectl apply -f -`).
3. Runs `kubectl apply -f k8s/<service>/` for each enabled service.
4. Waits for rollout: `kubectl rollout status deployment/<service> -n production`.

For staging, the same workflow runs with `--namespace staging` and a Kustomize overlay
that patches image tags and subdomain rules.

#### New `_deploy.yml` sketch

```yaml
name: Deploy Service (Reusable)
on:
  workflow_call:
    inputs:
      service:
        type: string
        required: true
      environment:
        type: string
        default: production
      image_tag:
        type: string
        default: latest

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure kubectl
        env:
          KUBECONFIG_DATA: ${{ secrets.K8S_KUBECONFIG }}
        run: |
          mkdir -p ~/.kube
          printf '%s' "$KUBECONFIG_DATA" > ~/.kube/config
          chmod 600 ~/.kube/config

      - name: Update image tag in manifests
        env:
          SERVICE: ${{ inputs.service }}
          TAG: ${{ inputs.image_tag }}
        run: |
          sed -i "s|:latest|:${TAG}|g" "k8s/${SERVICE}/deployment.yaml"

      - name: Apply manifests
        env:
          SERVICE: ${{ inputs.service }}
          NAMESPACE: ${{ inputs.environment }}
        run: kubectl apply -f "k8s/${SERVICE}/" -n "$NAMESPACE"

      - name: Wait for rollout
        env:
          SERVICE: ${{ inputs.service }}
          NAMESPACE: ${{ inputs.environment }}
        run: |
          kubectl rollout status deployment/"$SERVICE" \
            -n "$NAMESPACE" --timeout=120s
```

#### New secrets required

| Secret | Description |
|--------|-------------|
| `K8S_KUBECONFIG` | Full kubeconfig for the k3s cluster (with Tailscale IP as server) |

Remove after migration is complete:
- `SSH_PRIVATE_KEY`
- `SERVER_SSH_HOST_KEY`
- `SERVER_HOST`

(Tailscale secrets remain for kubeconfig connectivity.)

---

## Phase 5: Staging Environment

### Current staging approach

Docker Compose uses `docker-compose.staging.yml` overlays and a `staging-<service>`
project name to run staging containers alongside production on the same host.

### k3s staging approach

Staging services run in the `staging` Kubernetes namespace. A Kustomize overlay patches:
- The namespace from `production` to `staging`.
- The `IngressRoute` hostnames to use `*-staging.jamesmassucco.com`.
- The image tag to the staging image tag (e.g. `sha-abc1234`).

Directory layout:
```
k8s/
├── overlays/
│   └── staging/
│       ├── kustomization.yaml   # namespace: staging, image tag patches
│       ├── blog-patch.yaml      # hostname → blog-staging.jamesmassucco.com
│       ├── travel-patch.yaml    # hostname + PVC name
│       └── ...
```

`kustomization.yaml`:
```yaml
namespace: staging
bases:
  - ../../blog
  - ../../travel
  - ...
images:
  - name: ghcr.io/jmassucco17/homelab/blog
    newTag: sha-abc1234
patches:
  - path: blog-patch.yaml
  - path: travel-patch.yaml
```

The staging volume for travel becomes a separate PVC named `travel-data-staging` in the
`staging` namespace. The "seed from prod" step copies the production PVC contents into
the staging PVC using a temporary pod (same concept as the current Docker volume seed).

---

## Phase 6: Monitoring Updates

With k3s, the Grafana Alloy configuration changes from Docker-socket–based discovery to
Kubernetes API–based discovery:

### Updated `alloy-config.alloy` (k8s version)

```river
// Kubernetes pod discovery replaces Docker socket discovery
discovery.kubernetes "pods" {
  role = "pod"
  namespaces {
    own_namespace = false
    names = ["production", "staging"]
  }
}

loki.source.kubernetes "pods" {
  targets    = discovery.kubernetes.pods.targets
  forward_to = [loki.write.grafana_cloud.receiver]
}

prometheus.scrape "node_exporter" {
  targets    = [{"__address__" = "node-exporter.monitoring.svc.cluster.local:9100"}]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}

// cadvisor, traefik, remote_write — same as current config
```

The Docker socket mount is removed. Alloy gains a `ServiceAccount` with read access to
pods and logs in the `production` and `staging` namespaces.

---

## Migration Checklist

The following tasks represent the full implementation. Complete one phase at a time.

### Phase 1: Foundation

- [ ] Install k3s on VPS with `--disable traefik`
- [ ] Export kubeconfig and add `K8S_KUBECONFIG` as a GitHub Actions secret
- [ ] Create `k8s/base/namespaces.yaml` and apply it
- [ ] Verify `kubectl get nodes` is healthy from CI

### Phase 2: Traefik v3 and TLS

- [ ] Create `k8s/traefik/helmchart.yaml` (Traefik v3 HelmChart CRD)
- [ ] Create `k8s/traefik/cert-manager-helmchart.yaml`
- [ ] Apply HelmCharts; verify Traefik and cert-manager pods are running
- [ ] Create `k8s/traefik/cluster-issuer.yaml`; apply using CI with Cloudflare secrets
- [ ] Test certificate issuance with a staging cert (Let's Encrypt staging server)
- [ ] Create `k8s/base/middlewares.yaml` (ratelimit + oauth-auth Middleware CRDs)

### Phase 3: Service Migration (per service)

For each service: `networking → shared-assets → homepage → blog → games → tools → travel`

- [ ] Write `k8s/<service>/deployment.yaml` (Deployment + Service + Certificate +
      IngressRoute)
- [ ] Write Kubernetes Secret manifest and CI step to apply it from GitHub secrets
- [ ] Write `k8s/<service>/pvc.yaml` (travel only)
- [ ] Apply manifests to `production` namespace and verify the service is reachable
- [ ] Confirm Traefik routes and TLS certificate are working
- [ ] Update CI to deploy this service via `kubectl apply` instead of SSH

### Phase 4: CI/CD Migration

- [ ] Create reusable `_deploy.yml` (kubectl-based)
- [ ] Update `build-and-deploy.yml` to call the new workflow for each service
- [ ] Remove `_prep-server.yml` and its callers
- [ ] Remove `_deploy-simple.yml`, `_deploy-python.yml`, `_deploy-ots.yml`
- [ ] Remove `scripts/start_service.sh` SSH deploy steps from all workflows
- [ ] Remove Tailscale setup steps from deploy workflows (keep for kubeconfig
      connectivity if kubeconfig uses Tailscale IP)
- [ ] Delete `scripts/start_service.sh` after all services are migrated

### Phase 5: Staging

- [ ] Create `k8s/overlays/staging/kustomization.yaml`
- [ ] Create per-service staging patches
- [ ] Update `build-and-deploy.yml` staging path to `kubectl apply -k k8s/overlays/staging`
- [ ] Test staging deploy for each service

### Phase 6: Monitoring

- [ ] Convert `monitoring/alloy-config.alloy` to Kubernetes discovery
- [ ] Write `k8s/monitoring/` manifests (node-exporter DaemonSet, cadvisor DaemonSet,
      alloy Deployment, ConfigMap, ServiceAccount)
- [ ] Apply manifests; verify data flows to Grafana Cloud
- [ ] Remove `monitoring/docker-compose.yml` after validation

### Phase 7: Cleanup

- [ ] Remove all `docker-compose*.yml` files from each module
- [ ] Remove `scripts/start_service.sh`
- [ ] Remove Docker network creation steps from `_prep-server.yml` (file deleted)
- [ ] Remove Docker-specific CI integration tests (replace with manifest validation)
- [ ] Update `docs/deployments.md` to describe the k3s-based workflow
- [ ] Update `docs/secrets.md` to replace `SSH_PRIVATE_KEY` / `SERVER_SSH_HOST_KEY`
      with `K8S_KUBECONFIG`
- [ ] Update `README.md`

---

## One-Time Server Setup

1. **Install k3s** (see Phase 1.1 above).
2. **Configure Tailscale** on the VPS if not already done — the kubeconfig server address
   will use the Tailscale IP so CI can reach the API server from GitHub Actions.
3. **Persist storage directory** — k3s's `local-path` provisioner stores PVC data at
   `/var/lib/rancher/k3s/storage/` by default. Back this up with the same mechanism used
   for the current Docker volume backups.
4. **Firewall**: Open port `6443` (k3s API server) to the Tailscale interface only; not
   to the public internet.
5. **Migrate Docker volumes** to PVCs before turning off the old Docker Compose services
   (see Phase 3 travel notes above for the copy procedure).

---

## Out of Scope

- **Multi-node cluster**: The plan targets a single-node k3s cluster. Multi-node is
  possible later with `k3sup join` but is not needed for a personal homelab.
- **Helm-based service packaging**: Each service is deployed with raw manifests
  (or Kustomize overlays). Converting services to Helm charts is a future improvement.
- **GitOps (Flux / ArgoCD)**: The CI/CD pipeline continues to use GitHub Actions
  `kubectl apply`. A GitOps controller would be a further improvement but adds
  operational complexity.
- **Network policies**: Default k3s allows all pod-to-pod communication. Adding
  `NetworkPolicy` resources to restrict traffic between namespaces is a future
  hardening step.
- **Horizontal pod autoscaling**: All services run as single-replica Deployments.
  HPA can be added later once resource usage under k3s is profiled.
- **Resource limits / requests**: Not set in Phase 1. Add after establishing a baseline
  with the monitoring stack.
