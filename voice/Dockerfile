# Multi-stage build for Predator Analytics Voice Service
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

# Install dependencies
RUN poetry install --only main --no-root && rm -rf $POETRY_CACHE_DIR

# Runtime stage
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r predator && useradd -r -g predator -u 1000 predator

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY voice/ ./voice/
COPY api/models.py ./api/models.py

# Create directory for Whisper models
RUN mkdir -p /app/.cache/whisper && \
    chown -R predator:predator /app

# Switch to non-root user
USER predator

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Run voice service with uvicorn
CMD ["uvicorn", "voice.voice_interface:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
