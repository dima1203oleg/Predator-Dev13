# 🚀 Predator Analytics v13 - Production Deployment Guide

## Передумови

### Інфраструктура
- Kubernetes кластер v1.27+ (3 master, 6+ worker nodes)
- StorageClass з підтримкою RWX (для shared PVCs)
- LoadBalancer або Ingress Controller (NGINX/Istio)
- DNS записи налаштовані
- Мінімум 64 CPU cores, 256GB RAM загалом

### Інструменти
```bash
# Встановіть CLI інструменти
kubectl version --client  # v1.27+
helm version             # v3.12+
argocd version           # v2.8+
velero version           # v1.12+
```

### Secrets
Підготуйте наступні секрети:
- PostgreSQL credentials
- Redis password
- MinIO access/secret keys
- Keycloak admin password
- API keys: OpenAI, Anthropic, Groq, Google, DeepSeek, AI21, Cohere
- SMTP credentials
- Slack/Telegram webhooks
- Cosign signing keys

---

## Крок 1: Підготовка кластера

### 1.1 Створення Namespace
```bash
kubectl create namespace predator
kubectl label namespace predator \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### 1.2 Налаштування RBAC
```bash
kubectl apply -f helm/predator-umbrella/templates/rbac.yaml
```

### 1.3 Встановлення ExternalSecrets Operator
```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace
```

### 1.4 Конфігурація Vault/Secrets
```bash
# Створіть SecretStore
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: predator
spec:
  provider:
    vault:
      server: "https://vault.your-domain.com"
      path: "secret"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "predator-role"
EOF
```

---

## Крок 2: Встановлення Dependencies

### 2.1 Cert-Manager (для mTLS)
```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true
```

### 2.2 Istio Service Mesh
```bash
istioctl install --set profile=production -y
kubectl label namespace predator istio-injection=enabled
```

### 2.3 Kyverno (Policy Engine)
```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno \
  --namespace kyverno --create-namespace \
  --set replicaCount=3
```

---

## Крок 3: Підготовка Values

### 3.1 Копіювання та редагування values-prod.yaml
```bash
cd helm/predator-umbrella
cp values-prod.yaml values-prod-custom.yaml

# Відредагуйте критичні параметри
vim values-prod-custom.yaml
```

Ключові параметри для зміни:
```yaml
global:
  domain: "predator.your-domain.com"
  env:
    ENVIRONMENT: "production"
  
  ingress:
    className: "nginx"
    tls:
      enabled: true
      secretName: "predator-tls"

api:
  replicaCount: 3
  autoscaling:
    minReplicas: 3
    maxReplicas: 10

postgres:
  primary:
    persistence:
      size: 500Gi
      storageClass: "fast-ssd"

opensearch:
  data:
    replicaCount: 3
    persistence:
      size: 1Ti

qdrant:
  persistence:
    size: 500Gi

minio:
  persistence:
    size: 2Ti
```

### 3.2 Створення Global Secrets
```bash
kubectl create secret generic predator-prod-secrets \
  -n predator \
  --from-literal=POSTGRES_PASSWORD='<strong-password>' \
  --from-literal=REDIS_PASSWORD='<strong-password>' \
  --from-literal=MINIO_ACCESS_KEY='<access-key>' \
  --from-literal=MINIO_SECRET_KEY='<secret-key>' \
  --from-literal=OPENAI_API_KEY='<key>' \
  --from-literal=ANTHROPIC_API_KEY='<key>' \
  --from-literal=GROQ_API_KEY='<key>' \
  --from-literal=GOOGLE_API_KEY='<key>' \
  --from-literal=DEEPSEEK_API_KEY='<key>' \
  --from-literal=COHERE_API_KEY='<key>' \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD='<strong-password>' \
  --from-literal=SMTP_PASSWORD='<password>' \
  --from-literal=SLACK_WEBHOOK_URL='<webhook>' \
  --from-literal=TELEGRAM_BOT_TOKEN='<token>'
```

---

## Крок 4: Встановлення Helm Chart

### 4.1 Додавання Helm Dependencies
```bash
helm dependency update helm/predator-umbrella
```

### 4.2 Dry-run для перевірки
```bash
helm install predator-umbrella helm/predator-umbrella \
  -n predator \
  -f helm/predator-umbrella/values-prod-custom.yaml \
  --dry-run --debug
```

### 4.3 Реальне встановлення
```bash
helm install predator-umbrella helm/predator-umbrella \
  -n predator \
  -f helm/predator-umbrella/values-prod-custom.yaml \
  --timeout 30m \
  --wait
```

### 4.4 Моніторинг встановлення
```bash
# В окремому терміналі
watch kubectl get pods -n predator

# Перевірка логів
kubectl logs -f -n predator -l app.kubernetes.io/name=predator-api
```

---

## Крок 5: Post-Deployment конфігурація

### 5.1 Ініціалізація PostgreSQL
```bash
# Застосувати міграції
kubectl exec -it -n predator postgres-0 -- \
  psql -U predator -d predator_analytics -f /migrations/001_initial.sql

# Створити Debezium publication
kubectl exec -it -n predator postgres-0 -- \
  psql -U predator -d predator_analytics -c \
  "CREATE PUBLICATION predator_pub FOR ALL TABLES;"
```

### 5.2 Налаштування OpenSearch
```bash
# Завантажити ILM policy
kubectl exec -it -n predator opensearch-0 -- curl -X PUT \
  "localhost:9200/_plugins/_ism/policies/predator_ilm" \
  -H 'Content-Type: application/json' \
  -d @/config/ilm_policy.json

# Завантажити index template
kubectl exec -it -n predator opensearch-0 -- curl -X PUT \
  "localhost:9200/_index_template/pa-template" \
  -H 'Content-Type: application/json' \
  -d @/config/index_template.json

# Створити ingest pipeline
kubectl exec -it -n predator opensearch-0 -- curl -X PUT \
  "localhost:9200/_ingest/pipeline/pii_masking_pipeline" \
  -H 'Content-Type: application/json' \
  -d @/config/pii_masking_pipeline.json

# Створити aliases
kubectl exec -it -n predator opensearch-0 -- curl -X POST \
  "localhost:9200/_aliases" \
  -H 'Content-Type: application/json' \
  -d '{"actions":[{"add":{"index":"pa-*","alias":"pa-safe"}},{"add":{"index":"pa-*","alias":"pa-restricted"}}]}'
```

### 5.3 Warm-up Ollama Models
```bash
# Перевірити, що моделі завантажені
kubectl exec -it -n predator model-router-0 -- ollama list

# Якщо потрібно, завантажити вручну
kubectl exec -it -n predator model-router-0 -- \
  ollama pull gemma2:9b mistral:7b nomic-embed-text
```

### 5.4 Створення Qdrant Collections
```bash
kubectl exec -it -n predator qdrant-0 -- curl -X PUT \
  "http://localhost:6333/collections/pa_domain_v1" \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    },
    "optimizers_config": {
      "memmap_threshold": 20000
    },
    "on_disk_payload": true
  }'
```

### 5.5 Keycloak Realm Import
```bash
kubectl exec -it -n predator keycloak-0 -- \
  /opt/keycloak/bin/kc.sh import \
  --file /config/predator-realm.json
```

---

## Крок 6: ArgoCD GitOps Setup

### 6.1 Встановлення ArgoCD
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Отримати admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

### 6.2 Створення Application
```bash
kubectl apply -f devops/argocd/application.yaml

# Синхронізація
argocd app sync predator-umbrella
```

---

## Крок 7: Observability Setup

### 7.1 Доступ до Grafana
```bash
kubectl port-forward -n predator svc/grafana 3000:80

# Username: admin
# Password: from secret
kubectl get secret -n predator grafana -o jsonpath="{.data.admin-password}" | base64 -d
```

### 7.2 Імпорт Dashboards
- API Performance: Dashboard ID 12345
- Database Metrics: Dashboard ID 12346
- SLO/SLA Overview: Custom JSON in `/devops/grafana-dashboards/`

### 7.3 Налаштування Alertmanager
```bash
kubectl apply -f helm/predator-umbrella/charts/observability/config/alertmanager.yaml
```

---

## Крок 8: Backups та DR

### 8.1 Встановлення Velero
```bash
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket predator-backups \
  --secret-file ./credentials-velero \
  --use-volume-snapshots=true \
  --backup-location-config region=us-east-1
```

### 8.2 Створення Backup Schedule
```bash
velero schedule create predator-daily \
  --schedule="0 2 * * *" \
  --include-namespaces predator \
  --ttl 720h
```

### 8.3 Запуск DR Drill (щотижнево)
```bash
chmod +x devops/dr_drill.sh
./devops/dr_drill.sh
```

---

## Крок 9: Security Hardening

### 9.1 Застосування Kyverno Policies
```bash
kubectl apply -f helm/predator-umbrella/charts/keycloak/config/kyverno-policies.yaml
```

### 9.2 Network Policies
```bash
kubectl apply -f helm/predator-umbrella/templates/networkpolicies.yaml
```

### 9.3 PodDisruptionBudgets
```bash
kubectl apply -f helm/predator-umbrella/templates/pdb.yaml
```

---

## Крок 10: Smoke Tests

### 10.1 Health Checks
```bash
# API
curl https://predator.your-domain.com/health

# Keycloak
curl https://predator.your-domain.com/auth/realms/predator

# Grafana
curl https://predator.your-domain.com/grafana/api/health
```

### 10.2 End-to-End Test
```bash
# Upload test dataset
curl -X POST https://predator.your-domain.com/api/datasets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/sample_data.xlsx"

# Search
curl -X POST https://predator.your-domain.com/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"аномалії імпорту"}'
```

### 10.3 Performance Test
```bash
cd tests/performance
k6 run --vus 100 --duration 5m load_test.js
```

---

## Крок 11: Chaos Engineering

### 11.1 Встановлення Litmus
```bash
kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v2.14.0.yaml
```

### 11.2 Запуск Chaos Experiments
```bash
kubectl apply -f devops/chaos/litmus-experiments.yaml
```

---

## Troubleshooting

### Pods не стартують
```bash
kubectl describe pod <pod-name> -n predator
kubectl logs <pod-name> -n predator --previous
```

### PVC не bound
```bash
kubectl get pvc -n predator
kubectl describe pvc <pvc-name> -n predator
```

### Ingress не працює
```bash
kubectl get ingress -n predator
kubectl describe ingress predator-ingress -n predator
```

### Database connection issues
```bash
kubectl exec -it -n predator postgres-0 -- psql -U predator -c "\l"
```

---

## Rollback

У разі критичних проблем:
```bash
# Helm rollback
helm rollback predator-umbrella -n predator

# ArgoCD rollback
argocd app rollback predator-umbrella

# Velero restore
velero restore create --from-backup <backup-name>
```

---

## Maintenance

### Оновлення версії
```bash
# 1. Update values
vim helm/predator-umbrella/values-prod-custom.yaml

# 2. Helm upgrade з canary
helm upgrade predator-umbrella helm/predator-umbrella \
  -n predator \
  -f helm/predator-umbrella/values-prod-custom.yaml \
  --wait

# 3. ArgoCD sync
argocd app sync predator-umbrella
```

### Scaling
```bash
# Manual scaling
kubectl scale deployment predator-api -n predator --replicas=5

# HPA adjustment
kubectl patch hpa predator-api-hpa -n predator -p '{"spec":{"maxReplicas":15}}'
```

---

## Metrics & SLOs

Моніторинг в Grafana:
- **API Latency (p95)**: < 800ms (SLO: 99%)
- **Error Rate**: < 1% (SLO: 99.99%)
- **Uptime**: 99.99% (SLA)
- **CDC Lag**: < 100 messages
- **Voice STT Latency**: < 2.5s (p95)

---

## Contacts

- **On-call**: Slack #predator-oncall
- **Incidents**: PagerDuty / Opsgenie
- **Runbooks**: `/docs/runbooks/`
- **Architecture Decisions**: `/docs/adr/`

---

**✅ Production Ready!** 🚀
