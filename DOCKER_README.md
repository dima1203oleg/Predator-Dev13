# Docker Build and Deployment Guide

## Prerequisites

- Docker Engine 24.0+
- Docker Compose V2
- Python 3.11+ (for local development)
- 16GB RAM minimum (32GB recommended)
- 50GB free disk space

## Building Images

### Option 1: Build Sequentially (Recommended)

Build images one by one to monitor progress:

```bash
# API Service
docker build -f api/Dockerfile -t predator-api:13.0.0 -t predator-api:latest .

# Agents Service
docker build -f agents/Dockerfile -t predator-agents:13.0.0 -t predator-agents:latest .

# Voice Service
docker build -f voice/Dockerfile -t predator-voice:13.0.0 -t predator-voice:latest .

# Model Router
docker build -f model-router/Dockerfile -t predator-model-router:13.0.0 -t predator-model-router:latest .

# Frontend
docker build -f frontend/Dockerfile -t predator-frontend:13.0.0 -t predator-frontend:latest .
```

### Option 2: Build with Script

```bash
# Using the automated build script
./scripts/build_local.sh
```

### Option 3: Parallel Build (Fastest)

```bash
# Build all images in parallel
./scripts/build_parallel.sh

# Monitor progress
tail -f /tmp/predator-build-logs/*.log
```

## Running with Docker Compose

### Start All Services

```bash
# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f agents
```

### Check Service Health

```bash
# Check all services
docker-compose ps

# API health check
curl http://localhost:8000/health

# Voice service health
curl http://localhost:8001/health

# Model router health
curl http://localhost:8002/health

# Frontend
curl http://localhost:3000
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Service Ports

- **API**: http://localhost:8000
- **Voice**: http://localhost:8001
- **Model Router**: http://localhost:8002
- **Frontend**: http://localhost:3000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **OpenSearch**: http://localhost:9200
- **Qdrant**: http://localhost:6333
- **Ollama**: http://localhost:11434

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://predator:predator_password@postgres:5432/predator_db

# Redis
REDIS_URL=redis://redis:6379/0

# OpenSearch
OPENSEARCH_URL=http://opensearch:9200

# Qdrant
QDRANT_URL=http://qdrant:6333

# Ollama
OLLAMA_HOST=http://ollama:11434

# API Keys (add your own)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key
GROQ_API_KEY=your_groq_key
```

## Troubleshooting

### Build Issues

**Poetry dependency resolution fails:**
```bash
# Update langchain versions in pyproject.toml
# Then rebuild
docker build --no-cache -f api/Dockerfile -t predator-api:latest .
```

**Out of disk space:**
```bash
# Clean up Docker resources
docker system prune -a --volumes

# Remove old images
docker images | grep predator | awk '{print $3}' | xargs docker rmi -f
```

### Runtime Issues

**Service won't start:**
```bash
# Check logs
docker-compose logs service_name

# Restart specific service
docker-compose restart service_name

# Rebuild and restart
docker-compose up -d --build service_name
```

**Database connection errors:**
```bash
# Wait for PostgreSQL to be ready
docker-compose exec postgres pg_isready

# Check PostgreSQL logs
docker-compose logs postgres
```

**Memory issues:**
```bash
# Increase Docker Desktop memory limit (Settings > Resources > Memory)
# Or reduce number of uvicorn workers in Dockerfile

# API: --workers 2 (instead of 4)
# Voice: --workers 1 (instead of 2)
```

## Production Deployment

### Using Helm (Kubernetes)

```bash
# Install Helm chart
helm install predator ./helm/predator-umbrella \
  --namespace predator \
  --create-namespace \
  --values ./helm/predator-umbrella/values-prod.yaml

# Check status
kubectl get pods -n predator
```

### Push to Registry

```bash
# Login to registry
docker login ghcr.io

# Tag and push
export REGISTRY=ghcr.io/your-org
export VERSION=13.0.0

for service in api agents voice model-router frontend; do
  docker tag predator-${service}:latest ${REGISTRY}/predator-${service}:${VERSION}
  docker push ${REGISTRY}/predator-${service}:${VERSION}
done
```

## Performance Tuning

### Reduce Build Time

1. **Use layer caching:**
   ```dockerfile
   # Copy only dependency files first
   COPY pyproject.toml ./
   RUN poetry install --only main --no-root
   
   # Then copy application code
   COPY agents/ ./agents/
   ```

2. **Build with BuildKit:**
   ```bash
   DOCKER_BUILDKIT=1 docker build -f api/Dockerfile -t predator-api:latest .
   ```

3. **Use multi-stage builds** (already implemented in Dockerfiles)

### Optimize Runtime

1. **Limit resources:**
   ```yaml
   # In docker-compose.yml
   services:
     api:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 4G
           reservations:
             cpus: '1'
             memory: 2G
   ```

2. **Use production ASGI server:**
   ```bash
   # Already using uvicorn with uvloop in production
   uvicorn api.main:app --loop uvloop --workers 4
   ```

## Monitoring

### View Resource Usage

```bash
# All containers
docker stats

# Specific container
docker stats predator-api
```

### Access Logs

```bash
# API logs
docker-compose logs -f api | grep ERROR

# All errors
docker-compose logs | grep -i error

# Export logs
docker-compose logs > predator-logs-$(date +%Y%m%d).txt
```

## Quick Commands Reference

```bash
# Build all images
./scripts/build_parallel.sh

# Start services
docker-compose up -d

# View logs
docker-compose logs -f api agents

# Restart service
docker-compose restart api

# Stop everything
docker-compose down

# Clean up
docker system prune -af --volumes

# Check health
curl http://localhost:8000/health
```

## Support

For issues:
1. Check logs: `docker-compose logs service_name`
2. Verify health: `docker-compose ps`
3. Review documentation in `/docs`
4. Check GitHub issues
