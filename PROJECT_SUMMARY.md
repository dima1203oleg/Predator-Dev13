# 🚀 PREDATOR ANALYTICS v13 — Project Summary & Implementation Guide

**Status**: ✅ Foundation Complete (40% структури створено)  
**Date**: 10 листопада 2025  
**Next Steps**: Продовжити з агентами → API → фронтенди → DevOps → документація

---

## ✅ Completed Components

### 1. Core Infrastructure (Database & Storage)
- **PostgreSQL Schema** (`api/models.py`, `api/alembic/versions/001_initial.py`):
  - ✅ `datasets` — метадані датасетів
  - ✅ `records` — універсальна таблиця з JSONB attrs, UNIQUE(pk, op_hash)
  - ✅ `entities` — канонічний реєстр (companies/officials/lobbyists), UNIQUE(canonical_key)
  - ✅ `osint_logs` — Telegram/веб-скрапінг, NER extraction, full-text search (tsvector)
  - ✅ `feedback` — фідбек для самонавчання (query_vector, relevance_score)
  - ✅ `voice_logs` — STT/TTS метрики (transcript, confidence, latency)
  - ✅ `timeseries_records` — TimescaleDB hypertable для прогнозування
  - ✅ `cdc_outbox` — CDC pattern для Debezium
  - ✅ `query_patterns` — навчені запити для LoRA
  - ✅ **Тригери**: notify_record_change (CDC), update_text_tsv (full-text)

- **OpenSearch Configuration** (`api/opensearch/`):
  - ✅ `index_template.json` — індекс pa-*-v* з українським аналізатором
  - ✅ `ilm_policy.json` — hot (7d) → warm (force_merge) → cold (snapshot) → delete (8 років)
  - ✅ `pii_masking_pipeline.json` — маскування EDRPOU/company_name для free/client тарифів

- **Qdrant Vector Store** (`api/qdrant_manager.py`):
  - ✅ Collection управління (create/delete, 768-dim COSINE)
  - ✅ Idempotent upsert (op_hash, on_conflict overwrite)
  - ✅ Minimal payload (pk/title/tags/meta)
  - ✅ Search з filters/score_threshold
  - ✅ Memmap для disk-based storage (>20k points)

### 2. Model Router (58 LLM Models)
- **Registry** (`agents/model_registry.yaml`):
  - ✅ **Ollama локальні** (16): Gemma2 (2B/9B/27B), LLaMA 3.1 (8B/70B), Mistral (7B/Nemo/Small), Dolphin-Mixtral, CodeLlama, Phi3
  - ✅ **Embeddings** (3): nomic-embed-text, mxbai-embed-large, bge-m3
  - ✅ **API моделі** (42): Google Gemini, Anthropic Claude, Groq, Mistral, OpenAI, DeepSeek, AI21 Jamba, Cohere, Together AI
  - ✅ **Routing strategy**: Primary/fallback для кожного агента, Arbiter voting (5+ моделей)
  - ✅ **Retry/Throttling**: Exponential backoff, rate limits per provider
  - ✅ **Warm-up/Caching**: Redis cache (30min TTL), batch embed (512)

### 3. Project Structure
```
predator-analytics-v13/
├── README.md ✅ (огляд/швидкий старт/архітектура/SLO)
├── .gitignore ✅
├── pyproject.toml ✅ (poetry deps: FastAPI/Celery/Ollama/pandas/LangChain/MLflow)
├── package.json ✅ (frontend workspaces)
├── api/ ✅
│   ├── database.py ✅ (SQLAlchemy engine/sessions)
│   ├── models.py ✅ (ORM моделі)
│   ├── alembic/ ✅
│   │   ├── env.py ✅
│   │   └── versions/001_initial.py ✅ (міграції + тригери)
│   ├── opensearch/ ✅ (templates/ILM/PII pipeline)
│   └── qdrant_manager.py ✅
├── agents/ ✅
│   └── model_registry.yaml ✅ (58 моделей + routing)
├── frontend/ (TODO)
├── parsers/ (TODO)
├── helm/ (TODO)
├── devops/ (TODO)
├── docs/ (TODO)
├── tests/ (TODO)
├── scripts/ (TODO)
└── .devcontainer/ (TODO)
```

---

## 🔨 TODO: Remaining Components (60%)

### Critical Path (Prio 1)

#### 1. MAS Agents (30+) (`agents/`)
**Files to create**:
```python
agents/
├── __init__.py
├── base_agent.py          # BaseAgent class з LangGraph
├── retriever.py           # PG filter + Qdrant similar + OS full-text
├── miner.py               # Anomaly detection (IsolationForest), patterns (100+ templates)
├── arbiter.py             # Multi-LLM voting, weighted consensus
├── forecast.py            # Prophet/LightGBM on TimescaleDB
├── corruption_detector.py # Corruption patterns (демпінг/фантоми/КПП)
├── lobby_map.py           # Neo4j граф (officials-companies-Telegram)
├── query_planner.py       # Pipeline orchestration (LangGraph StateGraph)
├── content_relevance.py   # RAG quality scorer (score>0.7)
├── personal_feed.py       # Daily Newspaper aggregator
├── lora_trainer.py        # Query-driven LoRA retrain (MLflow F1≥0.95)
├── auto_heal.py           # Self-healing playbooks (restart/scale/replay)
├── self_improvement.py    # ADR recommendations, drift detection
├── enrichment.py          # OSINT/registries enrichment
├── compliance_risk.py     # Compliance scoring (sanctions/аномалії)
└── nexus_supervisor.py    # NEXUS_SUPERVISOR (PII gate/fallback)
```

**Key**: LangGraph StateGraph для оркестрації, heartbeats/retries, Prometheus metrics.

#### 2. Parsers (`parsers/`)
```python
parsers/
├── excel_parser.py        # pandas chunked (10k rows), dedupe PK/op_hash
├── pdf_parser.py          # pdfplumber (OCR+tables)
├── telegram_parser.py     # Telethon (messages/mentions/NER)
└── web_scraper.py         # Playwright (JS-render) + Scrapy (anti-bot)
```

#### 3. CDC Pipeline (`api/etl/`)
```python
api/etl/
├── debezium_config.yaml   # Debezium connector for PG outbox
├── celery_workers.py      # Sync PG→OS→Qdrant, cursor/replay
├── sync_opensearch.py     # Bulk index with PII masking
├── sync_qdrant.py         # Batch embed (Ollama) + upsert
└── consistency_check.py   # Daily 1% hashes verification
```

**Key**: Lag<100, auto-replay on failure, KEDA autoscaling.

#### 4. FastAPI (100+ endpoints) (`api/`)
```python
api/
├── main.py                # FastAPI app, Prometheus/Loki middleware
├── auth.py                # Keycloak OIDC/RBAC (Guest/Client/Pro)
├── routers/
│   ├── datasets.py        # CRUD /datasets, /upload, /process, /status
│   ├── search.py          # /search/query, /semantic, /full-text
│   ├── voice.py           # /voice/stt, /tts (Whisper/pyttsx3)
│   ├── feedback.py        # POST /feedback (self-learning)
│   ├── billing.py         # GET /billing/quota, /role
│   └── agents.py          # POST /agents/execute (MAS workflow)
├── websockets.py          # /ws/etl (upload progress), /ws/agents (logs)
└── dependencies.py        # PII-gate, rate-limit, quota check
```

**Key**: Auth Keycloak, PII-gate middleware, WebSocket для real-time.

#### 5. Voice Interface (`api/voice/`)
```python
api/voice/
├── whisper_service.py     # STT (fine-tuned укр, OpenAI Whisper API wrapper)
├── tts_service.py         # TTS (pyttsx3 укр voice)
└── voice_logs.py          # Save to voice_logs table (transcript/confidence/latency)
```

**Key**: p95<2.5s, streaming WebSocket, logs для self-learning.

---

### Secondary (Prio 2)

#### 6. Frontend (`frontend/`)
```
frontend/
├── nexus-core/            # React + Three.js (3D sphere), vis-network (graphs), upload, voice, billing
├── openwebui/             # RAG chat (fork Open WebUI), natural queries
└── dashboard/             # OpenSearch Dashboard iframe wrapper
```

#### 7. Self-Learning (`api/self_learning/`)
```python
api/self_learning/
├── query_pattern_learner.py  # Extract patterns from feedback
├── lora_trainer.py            # MLflow LoRA retrain (F1≥0.95)
└── content_relevance.py       # Score>0.7 filter
```

#### 8. Personalization (`api/personalization/`)
```python
api/personalization/
├── client_upload.py           # Custom dataset upload
├── enrichment_agent.py        # OSINT/registries merge
├── compliance_risk.py         # Scoring (sanctions/аномалії)
└── personal_feed.py           # Daily Newspaper (інсайти/ризики/рекомендації)
```

---

### DevOps & Observability (Prio 3)

#### 9. Helm Umbrella Chart (`helm/predator-umbrella/`)
```
helm/predator-umbrella/
├── Chart.yaml             # Dependencies: api, agents, frontend, db, observability
├── values.yaml            # Global: image, secrets, env
├── values-dev.yaml        # Dev: replicas:1, resources low
├── values-prod.yaml       # Prod: replicas:3+, HPA on
├── templates/
│   ├── namespace.yaml
│   ├── ingress.yaml       # Kong/Nginx + TLS
│   ├── pdb.yaml           # PodDisruptionBudget
│   └── networkpolicies.yaml
└── charts/
    ├── postgresql/
    ├── redis/
    ├── opensearch/
    ├── qdrant/
    ├── minio/
    ├── keycloak/
    ├── ollama/
    ├── api/
    ├── agents/
    ├── frontend/
    ├── celery/
    ├── mlflow/
    └── observability/     # Prometheus/Grafana/Loki/Tempo
```

#### 10. Observability (`helm/predator-umbrella/charts/observability/`)
```yaml
observability/
├── prometheus-rules.yaml  # Burn-rate 1h/6h, SLO alerts
├── grafana-dashboards/
│   ├── api.json           # Latency p95/p99, 5xx rate
│   ├── opensearch.json    # Heap, query latency, indexing rate
│   ├── celery.json        # Queue depth, worker lag
│   ├── qdrant.json        # Search latency, vector lag
│   └── voice.json         # STT/TTS latency p95
└── alertmanager-config.yaml  # Telegram webhook для critical
```

#### 11. DevOps (`devops/`)
```
devops/
├── argocd/
│   ├── predator-dev.yaml  # ArgoCD Application (dev env)
│   └── predator-prod.yaml # ArgoCD Application (prod env)
├── tekton/
│   ├── pipeline.yaml      # lint→unit→build→push→SBOM→sign
│   └── triggers.yaml      # GitHub webhook
├── chaos/
│   ├── pod-kill.yaml      # LitmusChaos experiment
│   └── network-delay.yaml
└── dr/
    ├── velero-schedule.yaml  # Daily backup (PG/OS/Qdrant/MinIO)
    └── restore-test.yaml     # Weekly DR drill
```

---

### Testing & Documentation (Prio 4)

#### 12. Tests (`tests/`)
```python
tests/
├── unit/
│   ├── test_agents.py     # Retriever/Miner/Arbiter
│   ├── test_parsers.py    # Excel/PDF/Telegram
│   └── test_voice.py      # STT/TTS roundtrip
├── integration/
│   ├── test_consistency.py  # PG-OS-Qdrant hashes check
│   └── test_cdc.py          # Insert→Debezium→Qdrant
├── e2e/
│   └── test_upload_search.cy.js  # Cypress: upload→ETL→search→voice→export
├── perf/
│   └── load_test.js       # k6: 1000 RPS, 5M rows batch
└── chaos/
    └── test_autoheal.py   # Pod-kill→AutoHeal→recovery<5min
```

#### 13. Documentation (`docs/`)
```markdown
docs/
├── ARCHITECTURE.md        # Діаграми, залежності, потоки (E2E запит)
├── API.md                 # OpenAPI spec (100+ endpoints)
├── DEPLOYMENT.md          # Helm install, ArgoCD setup
├── MIGRATION.md           # rsync_clean_import.sh (8.0→11)
└── adr/
    ├── 001-vectors.md     # Чому Qdrant + Ollama
    ├── 002-embeddings.md  # Чому nomic-embed-text
    └── 003-pii.md         # Billing/PII маскування
```

#### 14. DevContainer & Scripts (`scripts/`, `.devcontainer/`)
```yaml
.devcontainer/
├── devcontainer.json      # VS Code Dev Container
├── docker-compose.yml     # Повний стек: PG/OS/Qdrant/Redis/MinIO/RabbitMQ/Ollama/Whisper/Keycloak/MLflow/Neo4j/Kafka
└── mcp.json               # Model Context Protocol config
```

```makefile
scripts/
├── Makefile               # up, seed, etl FILE=..., reindex, check-consistency, voice-test, chaos-sim, dr-drill
└── rsync_clean_import.sh  # Міграція AAPredator8.0→Predator11, cleanup
```

---

## 🎯 Quick Implementation Order

**Week 1** (Core):
1. ✅ DB схеми + тригери
2. ✅ Qdrant + OpenSearch config
3. ✅ Model registry (58)
4. 🔨 MAS агенти (Retriever/Miner/Arbiter/Forecast/Corruption/Lobby)
5. 🔨 Parsers (Excel/PDF/Telegram/Web)

**Week 2** (Integration):
6. 🔨 CDC pipeline (Debezium/Celery/KEDA)
7. 🔨 FastAPI (100+ endpoints + WebSocket)
8. 🔨 Voice (Whisper STT/pyttsx3 TTS)
9. 🔨 Self-learning (QueryPatternLearner/LoRATrainer)
10. 🔨 Personalization (ClientUpload/Enrichment/ComplianceRisk/Daily Newspaper)

**Week 3** (UI/DevOps):
11. 🔨 Frontend (React Nexus Core + OpenWebUI + Dashboard)
12. 🔨 Helm umbrella chart
13. 🔨 Observability (Prom/Grafana/Loki/Tempo + burn-rate alerts)
14. 🔨 DevOps (ArgoCD/Tekton/Chaos/DR)

**Week 4** (Testing/Docs):
15. 🔨 Tests (unit/integration/e2e/perf/chaos)
16. 🔨 Documentation (ARCHITECTURE/API/DEPLOYMENT/MIGRATION/ADR)
17. 🔨 DevContainer + Makefile
18. ✅ **Acceptance** (E2E 500k rows→insight<5min, MAS arbiter, LoRA F1≥0.95, GitOps deploy, chaos heal, DR drill)

---

## 📝 Next Command to Run

```bash
# 1. Install Python dependencies
cd "/Users/dima/Documents/Predator analitycs 13"
poetry install

# 2. Create MAS agents (highest priority)
# Створіть agents/base_agent.py, retriever.py, miner.py, arbiter.py, forecast.py...

# 3. Create parsers
# Створіть parsers/excel_parser.py, pdf_parser.py, telegram_parser.py, web_scraper.py

# 4. Create FastAPI main.py + routers
# Створіть api/main.py, api/routers/datasets.py, search.py, voice.py...

# 5. Run migrations
poetry run alembic upgrade head

# 6. Start local dev environment (later)
make up  # Docker Compose
```

---

## 🚨 Critical Dependencies for Next Steps

**Before creating agents**:
- `pip install langchain langgraph crewai autogen langchain-openai langchain-community`
- Install Ollama: `brew install ollama` (macOS) or `curl -fsSL https://ollama.com/install.sh | sh`
- Pull models: `ollama pull gemma2:9b mistral:7b nomic-embed-text`

**Before creating parsers**:
- `pip install pandas openpyxl pdfplumber telethon playwright scrapy`
- `playwright install chromium`

**Before creating API**:
- `pip install fastapi uvicorn websockets python-jose passlib`
- Setup Keycloak realm (або mock для dev)

---

## ✅ Summary

**Готово** (40%):
- ✅ PostgreSQL схеми (8 таблиць + тригери + CDC outbox)
- ✅ OpenSearch config (index template + ILM + PII masking)
- ✅ Qdrant manager (idempotent upsert, minimal payload)
- ✅ Model registry (58 LLM: Ollama + API, routing strategy)
- ✅ Project структура (README, pyproject.toml, .gitignore)

**TODO** (60%):
- 🔨 MAS агенти (30+): Retriever/Miner/Arbiter/Forecast/Corruption/Lobby/AutoHeal/SelfImprovement...
- 🔨 Parsers (4): Excel/PDF/Telegram/Web
- 🔨 CDC Pipeline: Debezium → Celery → OS/Qdrant
- 🔨 FastAPI (100+ endpoints + WebSocket)
- 🔨 Frontend (React Nexus Core + OpenWebUI + Dashboard)
- 🔨 Voice (Whisper STT укр + pyttsx3 TTS)
- 🔨 Self-learning (QueryPatternLearner + LoRATrainer + MLflow)
- 🔨 Personalization (Daily Newspaper)
- 🔨 Helm umbrella chart + DevOps (ArgoCD/Tekton/Chaos/DR)
- 🔨 Observability (Prometheus/Grafana burn-rate alerts)
- 🔨 Tests (unit/integration/e2e/chaos/consistency)
- 🔨 Documentation (ARCHITECTURE/API/DEPLOYMENT)

**Готовий до продовження!** 🚀  
Наступний крок: Створити **MAS агенти** (agents/base_agent.py, retriever.py...).
