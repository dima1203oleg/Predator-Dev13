# Deployment Playbook: Predator Analytics v13 (Remote K8s)

This playbook guides you through deploying Predator Analytics v13 to a remote Kubernetes cluster using GitOps (Argo CD) and Helm umbrella charts. All heavy services (DBs, search, ML) run in the cluster; your MacBook is only for code editing and git push.

## Prerequisites

- **Cluster**: K8s 1.28+ with node pools (cpu-pool, ml-pool, storage-pool). StorageClass `fast-ssd` for stateful workloads.
- **Tools**: kubectl, helm, argocd CLI, docker (for local builds if needed).
- **Registry**: GHCR or private registry for images (e.g., ghcr.io/yourorg/predator-api).
- **Secrets**: Vault or external secrets manager for DB creds, API keys.
- **DNS**: Domain (e.g., predator.example.com) with TLS certs (cert-manager + Let's Encrypt).
- **Monitoring**: Prometheus/Grafana/Loki/Tempo stack pre-installed in `observability` namespace.
- **Security**: Kyverno/OPA policies, PodSecurity standards.

## Step 1: Cluster Preparation

### 1.1 Install Core Add-ons

```bash
# Ingress Controller (Nginx)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-system --create-namespace

# Cert-Manager for TLS
helm repo add cert-manager https://charts.jetstack.io
helm install cert-manager cert-manager/cert-manager -n cert-manager --create-namespace --set installCRDs=true

# Argo CD
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --create-namespace --set server.service.type=LoadBalancer

# External Secrets Operator (for Vault integration)
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace

# Prometheus/Grafana (if not already)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n observability --create-namespace

# Velero for backups
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm install velero vmware-tanzu/velero -n velero --create-namespace --set configuration.backupStorageLocation.bucket=velero-backups --set configuration.backupStorageLocation.config.region=minio --set configuration.backupStorageLocation.config.s3Url=http://minio.observability:9000
```

### 1.2 Configure Secrets

- Set up Vault or use K8s secrets for initial bootstrap.
- Create `regcred` secret for image pulls: `kubectl create secret docker-registry regcred --docker-server=ghcr.io --docker-username=YOUR_USER --docker-password=YOUR_TOKEN -n predator-dev`

### 1.3 Node Pools and Storage

Ensure node pools are labeled:
- `cpu-pool`: nodes with label `pool=cpu`
- `ml-pool`: nodes with label `pool=ml` (GPU optional)
- `storage-pool`: nodes with label `pool=storage`

Create StorageClass `fast-ssd` (e.g., for EBS/GCP disks).

## Step 2: Argo CD Setup

### 2.1 Access Argo CD UI

```bash
# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d

# Port-forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login via CLI
argocd login localhost:8080 --username admin --password <password>
```

### 2.2 Add Repository

```bash
argocd repo add https://github.com/dima1203oleg/Predator-Dev13 --username YOUR_GITHUB_USER --password YOUR_GITHUB_TOKEN
```

### 2.3 Create Root Application (App-of-Apps)

Apply the `infra/argocd-root.yaml` manifest:

```bash
kubectl apply -f infra/argocd-root.yaml
```

This creates the `platform` application that manages all sub-apps (api, db, etc.) via the `platform/` umbrella chart.

## Step 3: GitHub Secrets for CI

In your repo settings > Secrets and variables > Actions:

- `REGISTRY_USERNAME`: Your GHCR username
- `REGISTRY_PASSWORD`: GHCR token
- `KUBE_CONFIG`: Base64-encoded kubeconfig for cluster access (for GitOps updates)
- `VAULT_TOKEN`: If using Vault for secrets

## Step 4: Initial Deploy (Dev Namespace)

### 4.1 Push Code

Ensure `platform/values-dev.yaml` is configured with dev settings (1 replica, minimal resources).

```bash
git add .
git commit -m "feat: initial platform umbrella chart"
git push origin main
```

### 4.2 Monitor Argo CD

In Argo CD UI, watch the `platform` app sync. It should deploy all components to `predator-dev` namespace.

### 4.3 Warm-up Ollama

After deploy, Ollama should auto-pull models via post-install hook. Check logs:

```bash
kubectl logs -n predator-dev job/ollama-warmup
```

## Step 5: Smoke Test

### 5.1 Health Checks

```bash
# Port-forward API
kubectl port-forward svc/api -n predator-dev 8000:8000

# Check health
curl http://localhost:8000/health

# Check DB connection (via API or direct)
kubectl exec -n predator-dev deployment/api -- python scripts/healthcheck.py --db postgresql://... --opensearch http://opensearch.predator-dev:9200 --qdrant http://qdrant.predator-dev:6333 --minio http://minio.predator-dev:9000 --ollama http://ollama.predator-dev:11434
```

### 5.2 ETL Test

Upload a sample Excel to MinIO, then trigger ETL via API:

```bash
# Upload file
kubectl port-forward svc/minio -n predator-dev 9000:9000
# Use MinIO console at http://localhost:9000 to upload sample.xlsx to 'raw' bucket

# Trigger parse (via API endpoint or job)
curl -X POST http://localhost:8000/etl/parse-index --data '{"input": "s3://raw/sample.xlsx", "dry_run": false}'
```

Verify records in PG, indexes in OS/Qdrant.

## Step 6: Promote to Stage/Prod

### 6.1 Update Values

Edit `platform/values-stage.yaml` or `values-prod.yaml` with higher replicas/resources.

### 6.2 Argo CD Apps for Multi-Env

Create separate Argo CD apps for stage/prod, pointing to different values files or branches.

Example `infra/argocd-stage.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-stage
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/dima1203oleg/Predator-Dev13
    path: platform
    targetRevision: main
    helm:
      valueFiles: ["values-stage.yaml"]
  destination:
    server: https://kubernetes.default.svc
    namespace: predator-stage
  syncPolicy:
    automated: { prune: true, selfHeal: true }
```

Apply and promote via Argo CD UI or CLI.

## Step 7: Monitoring and Alerts

### 7.1 Grafana Dashboards

Import dashboards for:
- API latency/errors
- ETL throughput
- DB/OS/Qdrant metrics
- Resource usage per pool

### 7.2 Alerts

Configure Alertmanager for:
- High error rates (>5%)
- Latency > SLO (e.g., API p95 >800ms)
- Queue depth >1000
- Disk pressure >80%

## Step 8: DR and Backups

### 8.1 Velero Backups

Schedule daily backups:

```bash
velero schedule create daily-backup --schedule="0 2 * * *" --include-namespaces predator-prod
```

### 8.2 Restore Test

```bash
velero restore create restore-test --from-backup daily-backup-20251112 --include-namespaces predator-sandbox
```

### 8.3 PG PITR

Use pgBackRest for point-in-time recovery. Test quarterly.

## Troubleshooting

- **Sync Issues**: Check Argo CD logs: `kubectl logs -n argocd deployment/argocd-server`
- **Pod Crashes**: `kubectl describe pod <pod> -n predator-dev`
- **Resource Limits**: Adjust in `values-dev.yaml` if OOMKilled.
- **Network Policies**: Ensure policies allow traffic between services.
- **Secrets**: Verify ExternalSecrets are syncing from Vault.

## Next Steps

- Implement KEDA for auto-scaling workers.
- Add Debezium for CDC.
- Set up canary deployments with Argo Rollouts.
- Integrate OPA for fine-grained access control.

This playbook ensures a production-ready, GitOps-driven deployment with minimal local overhead.
