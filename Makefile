# Makefile with convenience targets to run helper scripts without needing to set exec bits

.PHONY: check-docker setup-python encode-kubeconfig fix-perms smoke

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

smoke:
	@echo "Bring up docker compose core profile (requires docker daemon)"
	@docker compose -f .devcontainer/compose.yml --profile core up -d
up:
	docker compose -f .devcontainer/compose.yml --profile core up -d

up-ml:
	docker compose -f .devcontainer/compose.yml --profile core --profile ml up -d

down:
	docker compose -f .devcontainer/compose.yml down -v

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
.PHONY: venv deps lint test dryrun precommit install-hooks

venv:
	python -m venv .venv && . .venv/bin/activate && python -m pip install -U pip

deps: venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

lint:
	. .venv/bin/activate && ruff check --fix . && ruff format .

test:
	. .venv/bin/activate && pytest -q --maxfail=1

dryrun:
	. .venv/bin/activate && python scripts/parse_index_excel.py --input sample.xlsx --dry-run --mock

install-hooks:
	. .venv/bin/activate && pre-commit install
# Makefile with convenience targets to run helper scripts without needing to set exec bits

.PHONY: check-docker setup-python encode-kubeconfig fix-perms smoke

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

smoke:
	@echo "Bring up docker compose core profile (requires docker daemon)"
	@docker compose -f .devcontainer/compose.yml --profile core up -d
up:
	docker compose -f .devcontainer/compose.yml --profile core up -d

up-ml:
	docker compose -f .devcontainer/compose.yml --profile core --profile ml up -d

down:
	docker compose -f .devcontainer/compose.yml down -v

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
.PHONY: venv deps lint test dryrun precommit install-hooks

venv:
	python -m venv .venv && . .venv/bin/activate && python -m pip install -U pip

deps: venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

lint:
	. .venv/bin/activate && ruff check --fix . && ruff format .

test:
	. .venv/bin/activate && pytest -q --maxfail=1

dryrun:
	. .venv/bin/activate && python scripts/parse_index_excel.py --input sample.xlsx --dry-run --mock

install-hooks:
	. .venv/bin/activate && pre-commit install
