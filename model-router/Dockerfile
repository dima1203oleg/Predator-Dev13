# Multi-stage build for Predator Analytics Model Router
FROM python:3.11.14-slim-bookworm AS builder

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
COPY pyproject.toml ./

# Install dependencies
# Note: Without poetry.lock, this will resolve to latest compatible versions
RUN poetry install --only main --no-root --no-interaction && rm -rf $POETRY_CACHE_DIR

# Runtime stage
FROM python:3.11.14-slim-bookworm AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r predator && useradd -r -g predator -u 1000 predator

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy model router code and registry
COPY agents/model_registry.yaml ./agents/model_registry.yaml
COPY agents/arbiter.py ./agents/arbiter.py
COPY agents/base_agent.py ./agents/base_agent.py

# Create model router service wrapper
RUN echo '#!/usr/bin/env python3\n\
from fastapi import FastAPI, HTTPException\n\
from pydantic import BaseModel\n\
import yaml\n\
import httpx\n\
import os\n\
from typing import Optional, Dict, Any\n\
\n\
app = FastAPI(title="Predator Model Router")\n\
\n\
# Load model registry\n\
with open("/app/agents/model_registry.yaml") as f:\n\
    MODEL_REGISTRY = yaml.safe_load(f)\n\
\n\
class ChatRequest(BaseModel):\n\
    prompt: str\n\
    agent: Optional[str] = "default"\n\
    max_tokens: Optional[int] = 2000\n\
    temperature: Optional[float] = 0.7\n\
\n\
class EmbedRequest(BaseModel):\n\
    text: str\n\
    model: Optional[str] = "nomic-embed-text"\n\
\n\
@app.get("/health")\n\
async def health():\n\
    return {"status": "healthy"}\n\
\n\
@app.post("/chat")\n\
async def chat(request: ChatRequest):\n\
    """Route chat request to appropriate LLM based on agent and availability"""\n\
    # TODO: Implement routing logic with fallback\n\
    return {"response": "Not implemented yet", "model": "placeholder"}\n\
\n\
@app.post("/embed")\n\
async def embed(request: EmbedRequest):\n\
    """Route embedding request to Ollama"""\n\
    # TODO: Implement embedding routing\n\
    return {"embedding": [], "model": request.model}\n\
\n\
if __name__ == "__main__":\n\
    import uvicorn\n\
    uvicorn.run(app, host="0.0.0.0", port=8002)\n\
' > /app/model_router.py && chmod +x /app/model_router.py

# Set ownership
RUN chown -R predator:predator /app

# Switch to non-root user
USER predator

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OLLAMA_HOST=http://ollama:11434

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Expose port
EXPOSE 8002

# Run model router
CMD ["python", "/app/model_router.py"]
