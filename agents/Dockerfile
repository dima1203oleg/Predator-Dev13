# Multi-stage build for Predator Analytics Agents
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.7.1 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies including LangGraph, CrewAI, AutoGen
RUN poetry install --only main --no-root && rm -rf $POETRY_CACHE_DIR

# Runtime stage
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r predator && useradd -r -g predator -u 1000 predator

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY agents/ ./agents/
COPY api/models.py ./api/models.py
COPY api/database.py ./api/database.py
COPY api/qdrant_manager.py ./api/qdrant_manager.py
COPY parsers/ ./parsers/
COPY etl/ ./etl/

# Set ownership
RUN chown -R predator:predator /app

# Switch to non-root user
USER predator

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check (agents respond to arbiter requests)
HEALTHCHECK --interval=60s --timeout=15s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run agent orchestrator
CMD ["python", "-m", "agents.arbiter"]
