# Makefile with convenience targets to run helper scripts without needing to set exec bits

.PHONY: check-docker setup-python encode-kubeconfig fix-perms deploy-dev deploy-stage deploy-prod down lint test seed dryrun health reindex ollama-pull venv deps install-hooks precommit install-hooks

check-docker:
	@echo "Running check_docker.sh via bash (no chmod needed)"
	@bash ./scripts/check_docker.sh

setup-python:
	@echo "Run Python 3.11 venv helper (via bash)"
	@bash ./scripts/setup_python311.sh

encode-kubeconfig:
	@echo "Encode kubeconfig (base64) and print to stdout"
	@bash ./scripts/encode_kubeconfig.sh

fix-perms:
	@echo "Make scripts executable"
	@chmod +x ./scripts/*.sh || true
	@echo "Done. You can now run: ./scripts/<name>.sh"

# Removed local docker compose 'up' targets to enforce 'no local deploys' policy.
# Use remote deployment tools (kubectl, helm, argocd) instead.

# Example remote deployment targets (placeholders, actual implementation depends on ArgoCD setup)
deploy-dev:
	@echo "Deploying to development environment via ArgoCD"
	@argocd app sync predator-dev --wait --timeout 600

deploy-stage:
	@echo "Deploying to staging environment via ArgoCD (manual approval required)"
	@argocd app sync predator-stage --wait --timeout 600

deploy-prod:
	@echo "Deploying to production environment via ArgoCD (gated auto-promotion)"
	@argocd app sync predator-prod --wait --timeout 600

down:
	@echo "Bringing down local development containers (if any were started for testing utilities)"
	@docker compose -f .devcontainer/compose.yml down -v

lint:
	ruff check --fix . && ruff format .

test:
	pytest -q --maxfail=1

seed:
	python scripts/seed_db.py --db $(DB_URL)

dryrun:
	python scripts/parse_index_excel.py --input $(EXCEL_INPUT) --db $(DB_URL) --opensearch $(OPENSEARCH_URL) --qdrant $(QDRANT_URL) --minio $(MINIO_URL) --bucket raw --dry-run --embed-model $(EMBED_MODEL)

health:
	python scripts/healthcheck.py --db $(DB_URL) --opensearch $(OPENSEARCH_URL) --qdrant $(QDRANT_URL) --minio $(MINIO_URL) --ollama $(OLLAMA_URL)

reindex:
	python scripts/reindex.py --db $(DB_URL) --opensearch $(OPENSEARCH_URL) --qdrant $(QDRANT_URL)

ollama-pull:
	@echo "Pulling Ollama models: $(MODELS)"
	@for m in $(MODELS); do \
	  curl -sS -X POST $(OLLAMA_URL)/api/pull -d "{\"name\":\"$$m\"}" || exit 1; \
	done

venv:
	python -m venv .venv && . .venv/bin/activate && python -m pip install -U pip

deps: venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

precommit:
	. .venv/bin/activate && pre-commit run --all-files

install-hooks:
	. .venv/bin/activate && pre-commit install
