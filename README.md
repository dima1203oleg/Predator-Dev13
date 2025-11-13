
# Predator Analytics v13 — Automation-First Production Platform

## Automation-First Production Rules

**Важливо:**

- ❌ **No local deploys** — всі production розгортання лише через CI/CD та GitOps (ArgoCD).
- ✅ Всі секрети — через Vault/ExternalSecrets, `.env` лише для локального dev.
- ✅ Всі зміни проходять через PR, автоматичні перевірки (lint, tests, KHAP, security, SBOM, signing).
- ✅ Production-ready лише після проходження всіх SLO/SLA, DR drill, chaos tests.

## CI/CD Pipeline

1. **Lint & Tests**: ruff, pytest, helm lint/template
2. **KHAP Security Gate**: kubeconform, kube-linter, Trivy, Kubescape, Kyverno (fail on any error)
3. **Build & Push**: buildx multi-platform, push до registry
4. **GitOps bump**: оновлення `platform/values-dev.yaml` у predator-gitops
5. **ArgoCD Sync & Smoke**: auto-sync, health checks, smoke-job
6. **Cosign Verify**: перевірка підпису образу
7. **Promote**: ручне або автоматичне просування на stage/prod

## Required GitHub Secrets

- `GH_TOKEN` — для gitops push
- `GITHUB_TOKEN` — для registry
- `ARGOCD_TOKEN` або `ARGOCD_USER`/`ARGOCD_PASS` — для ArgoCD sync
- `KUBE_CONFIG_DATA` — для kubectl
- `COSIGN_VERIFY_REQUIRED` — (true/false) для обов'язкової перевірки підпису

## SRE Runbook (Production)

- **DR Drill**: запуск `infra/dr/DR-drill-playbook.md` для перевірки RTO/RPO
- **Chaos**: запуск Litmus experiments (`infra/k8s-tests/chaos/`)
- **Smoke**: запуск smoke-job (`infra/k8s-tests/smoke-job.yaml`)
- **Observability**: перевірка алертів Prometheus/Grafana/Loki/Tempo
- **Security**: перевірка Kyverno/NetworkPolicy/PodSecurity
- **GitOps**: всі зміни через PR, ArgoCD auto-sync

Докладніше — у `PRODUCTION_READINESS_REPORT.md`, `infra/observability/README.md`, `infra/dr/DR-drill-playbook.md`, `infra/policies/README.md`.



**Версія**: 13.0 Extended Final

**Статус**: ✅ Production-Ready

**Готовність**: 100/100 — повний життєвий цикл: збір → зберігання → аналіз → інсайти → самонавчання

---

## 📖 Огляд

Predator Analytics v13 — це автономна **мультиагентна аналітична платформа (MAS)** для комплексної обробки та аналізу митних, податкових, реєстрових і OSINT-даних з акцентом на:

- 🔍 **Прогнозування ризиків** (сезонність/тренди/зростання)
- 🚨 **Виявлення корупційних схем** (демпінг/фантоми/дублі/КПП без трафіку)
- 🕵️ **Лобізм** (чиновники/призначення/декларації/зв'язки)
- 🧠 **Персоналізація** (ранкова "газета"/дашборди/експорт/голос)
- 🔄 **Самонавчання** (query-driven LoRA/ContentRelevance)

### Ключові компоненти

| Компонент | Роль | Технології |
|-----------|------|------------|
| **PostgreSQL** | Структура/часові ряди/entities | Timescale, CDC triggers, UNIQUE constraints |
| **OpenSearch** | Повнотекст/дашборди/графіки | ILM, PII-masking (safe/restricted alias) |
| **Qdrant** | Семантичний пошук | nomic-embed-text, payload мінімальний, upsert idempotent |
| **Ollama** | Локальні LLM/embeddings | Gemma/Mistral/LLaMA/Dolphin, warm-up, LoRA retrain |
| **58 LLM Models** | Гібрид local/API | ModelRouter з arbit арем (Gemini/Claude/Groq/AI21) |
| **30+ MAS Agents** | Автоматизація аналізу | LangGraph/CrewAI, heartbeats/retries, NEXUS_SUPERVISOR |
| **Parsers** | Збір даних | pandas/pdfplumber/Telethon/Playwright/Scrapy |
| **CDC Pipeline** | Real-time sync | Debezium/Outbox, Celery/KEDA, курсори/auto-replay |
| **Voice Interface** | STT/TTS українською | Whisper (fine-tuned), pyttsx3, p95<2.5s |
| **GitOps/DevOps** | Розгортання/хаос/DR | ArgoCD/Tekton/LitmusChaos/Velero, umbrella Helm |
| **Observability** | Моніторинг/SRE | Prometheus/Grafana/Loki/Tempo, burn-rate alerts |

---

## 🚀 Швидкий старт

### Передумови

- Docker Desktop 24+ / Kubernetes 1.28+
- Helm 3.13+
- Python 3.11+
- Node.js 20+

### 1️⃣ Локальна розробка (DevContainer + docker-compose)

```bash
# Клонувати репо
git clone https://github.com/yourorg/predator-analytics-v13.git
cd predator-analytics-v13

# Запустити повний стек (PG/OS/Qdrant/Redis/MinIO/RabbitMQ/Ollama/Whisper/Keycloak/MLflow/Neo4j/Kafka)
make up

# Seed тестові дані
make seed

# Запустити ETL з файлу
make etl FILE=data/sample_customs_500k.xlsx

# Тест голосу
make voice-test AUDIO=data/test_query_ukr.wav

# Перевірка консистентності (1% hashes)
make check-consistency
```

### 2️⃣ Розгортання в Kubernetes (umbrella Helm + ArgoCD)

```bash
# Dev-середовище
helm upgrade --install predator-dev helm/predator-umbrella \
  -f helm/predator-umbrella/values-dev.yaml \
  --namespace predator-dev --create-namespace

# Production (GitOps через ArgoCD)
kubectl apply -f devops/argocd/applications/predator-prod.yaml
```

### 3️⃣ Міграція з AAPredator 8.0

```bash
# Запустити rsync_clean_import.sh
./scripts/rsync_clean_import.sh /path/to/AAPredator8.0

# Cleanup після успішного тесту
./scripts/rsync_clean_import.sh --cleanup
```

---


## 🏗️ Архітектура (життєвий цикл запиту)

```ascii
[UI: React/OpenWebUI/OS Dash + Voice STT/TTS] --Query/Upload--> [FastAPI/Kong Gateway] --Auth--> [Keycloak RBAC/PII-gate]
  |                                                     |
  v                                                     v
[MinIO raw] <--OSINT/Parser (Telethon/Playwright/pdfplumber/pandas/Scrapy)--> [Celery ETL + GE validation/dedupe]
  |                                                     |
  v                                                     v
[PG (structured/Timescale/entities)] <--> [CDC Debezium/Outbox] <--> [Qdrant vectors/payload] <--> [Ollama embed/LLM + LoRA]
  |                                                     |
  v                                                     v
[OpenSearch full-text/aggs/safe|restricted] <--> [Redis cache/queues/anti-stampede] <--> [Kafka events/MLflow]
  |                                                     |
  v                                                     v
[MAS Agents (LangGraph/30+)] --Arbiter--> [58 models hybrid local/API] --> [Grafana/Prom/Loki/Tempo + SRE alerts/burn-rate]
  |                                                     |
  v                                                     v
[Report/Graph/Newspaper/export] --> [MinIO signed URL] + [Voice TTS] + [Self-Learning feedback/LoRA retrain]
  |                                                     |
  v                                                     v
[AutoHeal/SelfImprovement/RedTeam] <--Chaos Litmus--> [DR Velero + drills]
```

### Потоки (E2E запит: "Аномалії холодильників 2023 + лобізм")

1. **Вхід**: UI/OpenWebUI + Voice STT → FastAPI `/search` | `/voice/stt`
2. **Auth/PII**: Keycloak RBAC → BillingGate (квоти/PII доступ)
3. **Retriever**: PG filter (hs=8418/year=2023) + Qdrant embed + OS full-text
4. **Miner/CorruptionDetector/LobbyMap**: Аномалії + шаблони (100+) + Neo4j граф
5. **Forecast**: Prophet/XGBoost на TimescaleDB
6. **QueryPlanner**: Pipeline (Retriever→Miner→Arbiter)
7. **Arbiter**: 5+ LLM (Gemma/Claude/Groq) → найкраща відповідь
8. **PersonalFeed**: Агрегат для "газети"
9. **Вихід**: UI дашборд/графік/vis-network/report + Voice TTS + export
10. **Self-Learning**: Фідбек → LoRA dataset → retrain → MLflow канарій

---

## 📊 Компоненти (деталі)


### 1. API (FastAPI, 100+ endpoints)

- `/datasets/*` — CRUD, upload, process, status
- `/search/*` — query (PG filter), semantic (Qdrant), full-text (OS)
- `/voice/*` — STT (Whisper укр), TTS (pyttsx3 укр)
- `/feedback` — self-learning
- `/billing` — квоти/ролі (Guest/Client/Pro)
- `/agents/execute` — запуск MAS workflow

**WebSocket**: `/ws/etl` (upload progress), `/ws/agents` (real-time logs)


### 2. Агенти (MAS, 30+)

- **Data (10)**: Ingest/Registry/Indexer/Vector/OSINT/Telegram/PDF/Excel/Validator/Cleaner
- **Query (5)**: SearchPlanner/ModelRouter/Arbiter/BillingGate/CacheManager
- **Analysis (7)**: Anomaly/Forecast/Graph/Report/Risk/Pattern/Sentiment
- **Self-Heal (10)**: Recovery/Restart/DepFix/Config/Perf/Patch/Integrity/Network/Backup/Monitor
- **Self-Optimize (10)**: TestGen/Migration/Lint/QueryOpt/CacheOpt/IndexOpt/Resource/Profiler/LoadBal/AutoScale
- **Self-Modernize (10)**: Arch/TechStack/Security/API/Database/Infra/DevOps/Comply/Access/Docs
- **Додаткові**: Retriever/Miner/CorruptionDetector/LobbyMap/QueryPatternLearner/LoRATrainer/HumanIntervention/RedTeam/ContentRelevance/PersonalFeed/ClientUpload/Enrichment/ComplianceRisk

**Оркестрація**: LangGraph/CrewAI/AutoGen, heartbeats/retries/timeouts/DLQ, NEXUS_SUPERVISOR


### 3. Моделі (58 LLM, hybrid local/API)

| Категорія | Моделі |
|-----------|--------|
| **Local (Ollama)** | Gemma 2 (2B/9B/27B), LLaMA 3.1 (8B/70B), Mistral (7B/Nemo/Small), Dolphin-Mixtral, Llama3-Groq-Tool-Use, OpenHermes 2.5, nomic-embed-text, mxbai-embed-large, bge-m3 |
| **API** | Gemini Pro 1.5 Flash, Claude 3 Haiku/Sonnet, Groq (Mixtral/LLaMA), Mistral Large, DeepSeek-V2, AI21 Jamba, Cohere Command R+ |

**ModelRouter**: primary/fallback/embed/vision, арбітраж (5+ LLM → найкраща відповідь), retry/throttling


### 4. Парсери (збір даних)

- **Excel/CSV**: pandas chunked (10k rows), dedupe PK/op_hash
- **PDF**: pdfplumber (OCR+tables)
- **Telegram**: Telethon (messages/mentions/NER)
- **Сайти**: Playwright (JS-render), Scrapy (anti-bot)

**Збагачення**: EnrichmentAgent → реєстри/OSINT/NER → `entities.attrs` jsonb


### 5. CDC Pipeline (real-time sync)

- **Triggers**: Debezium/Outbox → Kafka → Celery workers
- **Batch**: 5min cron, cursor last_pk/ts, lag<100
- **Replay**: Auto на збій, consistency suite (1% hashes щодня)


### 6. Фронтенди (3 UI)

- **React Nexus Core**: 3D сфера (Three.js), графи (vis-network), upload progress, агенти map, smart-autocomplete, what-if симулятор, хроно-карта, settings (UA/EN/WCAG), голос
- **OpenWebUI**: RAG-чат, upload PDF/Excel/Markdown, natural queries
- **OpenSearch Dashboard**: Raw дашборди/heatmap/timeline, iframe в Nexus, Pro raw-access


### 7. Персоналізація (Daily Newspaper)

1. **ClientUpload**: Клієнт завантажує дані (Excel/CSV/PDF)
2. **Enrichment**: → реєстри/OSINT/NER
3. **ComplianceRisk**: Скоринг (аномалії/sanctions/репутація)
4. **PersonalFeed**: "Ранкова газета" (інсайти/ризики/конкуренти/рекомендації)


### 8. Самонавчання (query-driven LoRA)

1. Запит/фідбек → Qdrant vector/classify (ContentRelevance score>0.7)
2. QueryPatternLearner → LoRA dataset (synthetic + real)
3. LoRATrainer cron → MLflow → LoRA fine-tune (F1 ≥0.95)
4. Канарій deploy (5% traffic → rollout)


### 9. Голос (українською)

- **STT**: Whisper fine-tuned укр, p95<2.5s, WebSocket streaming
- **TTS**: pyttsx3 укр voice, MP3 streaming
- **Інтеграція**: UI mic кнопка, чат voice message, логи для self-learning

---

## 🔐 Безпека (Zero-Trust)

- **Auth**: Keycloak OIDC/RBAC (Guest/Client/Pro), Vault/ExternalSecrets
- **Network**: mTLS/Istio, NetworkPolicies, WAF/Ingress headers/CORS
- **PII**: Masking (***) free/Pro, гейт/аудит, тумблер "розкрити дані"
- **Policies**: Kyverno/OPA (non-root/drop-caps/read-only/seccomp), PodSecurity baseline
- **Supply Chain**: SBOM (syft), Cosign sign, Trivy/CodeQL scans, DAST/ZAP

---

## 📈 Observability (SRE)


### Prometheus/Grafana

- **API**: Latency p95/p99, 5xx rate, RPS
- **OpenSearch**: Heap usage, query latency, indexing rate
- **Celery**: Queue depth, worker lag, task failures
- **Qdrant**: Search latency, vector lag (<100)
- **Voice**: STT/TTS latency p95 (<2.5s)


### Алерти (Burn-Rate 1h/6h)

- `HighErrorRate`: 5xx >1% (1h)
- `HighLatency`: p95 >800ms (6h)
- `HeapHigh`: OS heap >85%
- `QueueGrowing`: Celery queue >1000 (15min)
- `VectorLagHigh`: lag >100
- `DriftDetected`: PSI >0.2 (MLflow)


### AutoHeal (playbooks)

- `lag_high` → scale Celery workers, replay cursor
- `heap_high` → force_merge OS, scale pods
- `5xx_spike` → rollback deploy, circuit breaker


### Loki/Tempo

- Логи (errors/warnings, voice transcripts, agent traces)
- Tracing (E2E запит: UI → API → PG → Qdrant → Arbiter → UI)

**Alertmanager**: Telegram critical

---

## 🛠️ DevOps (GitOps)


### Helm Umbrella Chart

```text
helm/predator-umbrella/
├── Chart.yaml (deps: api, agents, frontend, db, observability)
├── values.yaml (global: imagePullPolicy, env, secretsRef)
├── values-dev.yaml (replicas:1, resources low)
├── values-prod.yaml (replicas:3+, HPA on, prod secrets)
└── charts/ (20+ компонентів)
```


### ArgoCD (GitOps)

- **Apps**: `predator-dev`, `predator-prod`
- **Sync**: Auto (3min poll), canary/rollback
- **Health**: Readiness/Liveness probes


### Tekton (CI/CD)

- **Pipeline**: lint → unit → build → push → SBOM → sign → notify
- **Triggers**: GitHub PR/push → EventListener


### Chaos Engineering (LitmusChaos)

- **Experiments**: pod-kill, network-delay, disk-pressure
- **AutoHeal**: Playbook replay (<5min recovery)


### DR (Disaster Recovery, Velero)

- **Backup**: Daily (PG/OS/Qdrant/MinIO), retention 30d
- **Drills**: Weekly (RTO ≤30min, RPO ≤15min)
- **Sandbox**: Restore test namespace

---

## 🧪 Тестування


### Unit (pytest)

- Агенти (Retriever/Miner/Arbiter)
- API endpoints (auth/search/voice)
- Парсери (pandas/pdfplumber/Telethon)


### Integration

- PG-OS-Qdrant consistency (hashes check 1%)
- CDC pipeline (insert → Debezium → Qdrant upsert)
- Voice STT/TTS roundtrip


### E2E (Cypress)

- Upload 500k rows → ETL → dashboard → search → voice → export
- Персоналізація (ClientUpload → Newspaper)


### Performance (k6/Locust)

- 1000 RPS API (p95<800ms)
- 5M rows batch ETL (<60s per 100k)
- Embed 1k texts (<60s)


### Chaos (LitmusChaos)

- Pod-kill → AutoHeal restart (<5min)
- Network-delay → retry/fallback


### Security (DAST)

- ZAP scan (OWASP Top 10)
- Trivy/CodeQL (CVE/SAST)

**Coverage**: >85%, CI gate

---

## 📚 Документація

- [Архітектура](docs/ARCHITECTURE.md) — діаграми, залежності, потоки
- [API Spec](docs/API.md) — 100+ endpoints, OpenAPI
- [Helm Deployment](docs/DEPLOYMENT.md) — umbrella chart, values
- [Міграція 8.0→11](docs/MIGRATION.md) — rsync_clean_import.sh
- [ADR](docs/adr/) — архітектурні рішення (vectors/embeddings/PII/billing)

---

## 🎯 SLO/SLA


| Компонент | SLI | SLO | Метрика |
|-----------|-----|-----|---------|
| API | p95 latency | <800ms | 99% |
| OpenSearch | query p95 | <500ms | 99% |
| Qdrant | search | <300ms | 99% |
| ETL | 100k rows | <60s | 99% |
| Embed | 1k texts | <60s | 99% |
| Voice STT | p95 | <2.5s | 95% |
| Vector lag | <100 | constant | 99.9% |
| **Uptime** | | 99.99% | **SLA** |

**MTTR**: <1min (AutoHeal), **Burn-Rate**: 1h/6h алерти

---

## 🤝 Contributing


1. Fork repo
2. Create feature branch (`git checkout -b feature/your-feature`)
3. Commit (`git commit -am 'Add feature'`)
4. Push (`git push origin feature/your-feature`)
5. Create Pull Request

**Стиль**: Black (Python), Prettier (JS/TS), pre-commit hooks

---

## 📜 License

MIT License — див. [LICENSE](LICENSE)

---

## 🙏 Подяки

- OpenSearch, Qdrant, Ollama спільноти
- LangChain/LangGraph, CrewAI, AutoGen
- Kubernetes, Helm, ArgoCD, Tekton

---

**✅ Production-Ready. Старт міграції/розгортання!**

🦅 **Predator Analytics v13** — Autonomous MAS Platform — *"Живий хижак" даних*
