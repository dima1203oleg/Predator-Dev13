
# Predator Analytics v13 — QUICKSTART

> **Automation-First Platform: No Local Deploys, CI→CD→GitOps Only**

---

## 1. Швидкий старт (CI/CD, GitOps, SRE)

- **Всі деплои — тільки через CI/CD та GitOps**
- **Локальні деплои, ручні зміни в кластерах — ЗАБОРОНЕНО**
- **Всі зміни проходять через PR → CI → CD → ArgoCD → Rollouts → Smoke/Chaos → Auto-promotion**

### 1.1. Клонуйте репозиторій

```sh
git clone https://github.com/dima1203oleg/Predator-Dev13.git
cd Predator-Dev13
```

### 1.2. Встановіть DevContainer (VS Code)

- Відкрийте папку у VS Code
- Виберіть "Reopen in Container"
- DevContainer встановить: kubectl, helm, argocd, cosign, yq, poetry, pytest

### 1.3. Запуск задач (VS Code Tasks)

- **Лінт + формат:** `Ctrl+Shift+P → Tasks: Run Task → lint+format`
- **Тести:** `Ctrl+Shift+P → Tasks: Run Task → tests`
- **CI/CD:** Всі зміни проходять через PR та CI/CD pipeline
- **ArgoCD sync:** `Ctrl+Shift+P → Tasks: Run Task → argocd: sync`

---

## 2. CI/CD Pipeline (GitHub Actions)

- **Lint, Tests, KHAP (Security/Policy), Build+Push, GitOps bump, Smoke/Chaos, Promote**
- **KHAP:** kubeconform, kube-linter, Trivy, Kubescape, Kyverno — блокують PR на будь-які помилки
- **Buildx:** multi-platform build, SBOM (Syft), Cosign signing
- **GitOps bump:** автоматичне оновлення image у `platform/values-dev.yaml` через GH token
- **Argo Rollouts:** Canary deploy, auto-promotion, auto-rollback
- **Smoke/Chaos:** автоматичні перевірки після деплою

---

## 3. Secrets & ExternalSecrets

- **Всі секрети — через ExternalSecrets + Vault/Secret Manager**
- **.env файли та секрети у репозиторії — ЗАБОРОНЕНО**
- **Документація:** `infra/external-secrets/README.md`

---

## 4. Observability & DR

- **Prometheus, Grafana, Loki, Tempo, Alertmanager** — моніторинг, алерти, трейсінг
- **DR:** Velero, pgBackRest, MinIO versioning, DR drill playbook
- **Документація:** `infra/observability/README.md`, `infra/dr/README.md`

---

## 5. SRE Runbook

- **Всі операції — через PR та CI/CD**
- **Відновлення:** DR playbook, acceptance criteria (RTO ≤ 60 min, RPO ≤ 15 min)
- **Алерти:** HighErrorRate, HighLatency, CDC lag >100, QueueGrowing
- **Розгортання:** ArgoCD ApplicationSet, auto-sync, selfHeal
- **Політики:** PodSecurity, NetworkPolicy, Kyverno/OPA

---

## 6. Важливі файли та каталоги

- `.github/workflows/pipeline.yml` — CI/CD pipeline
- `charts/api/rollout.yaml` — Argo Rollouts Canary
- `infra/external-secrets/` — ExternalSecrets, Vault
- `infra/observability/` — Observability manifests
- `infra/dr/` — DR & backup
- `infra/policies/` — Security/Policy manifests
- `README.md` — Повна документація
- `PRODUCTION_READINESS_REPORT.md` — Production readiness

---

## 7. Вимоги до PR та деплою

- **Всі зміни — через PR, CI/CD, GitOps**
- **KHAP, SBOM, Cosign, Policy — блокують PR на будь-які помилки**
- **Всі секрети — через ExternalSecrets**
- **DR, Observability, Policy — обов'язкові для продакшн**

---

## 8. Контакти та підтримка

- **SRE/DevOps:** звертайтесь через GitHub Issues або Slack
- **Документація:** див. `README.md`, `infra/*/README.md`

---

> **Всі production деплои — тільки через CI/CD та GitOps!**
> **Локальні деплои, ручні зміни — ЗАБОРОНЕНО!**
