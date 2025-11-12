#!/bin/bash
# Test script for Predator Analytics Docker containers

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🧪 Testing Predator Analytics Containers${NC}"
echo ""

# Function to test service health
test_service() {
    local service=$1
    local url=$2
    local timeout=60
    local elapsed=0
    
    echo -n "Testing ${service}... "
    
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ OK${NC}"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    echo -e "${RED}❌ FAILED (timeout after ${timeout}s)${NC}"
    return 1
}

# Check if containers are running
echo -e "${YELLOW}Checking running containers...${NC}"
docker-compose ps

echo ""
echo -e "${YELLOW}Testing service endpoints...${NC}"

# Test each service
test_service "PostgreSQL" "localhost:5432" || echo "  Try: docker-compose logs postgres"
test_service "Redis" "localhost:6379" || echo "  Try: docker-compose logs redis"
test_service "OpenSearch" "http://localhost:9200" || echo "  Try: docker-compose logs opensearch"
test_service "Qdrant" "http://localhost:6333/health" || echo "  Try: docker-compose logs qdrant"
test_service "Ollama" "http://localhost:11434/api/tags" || echo "  Try: docker-compose logs ollama"
test_service "API" "http://localhost:8000/health" || echo "  Try: docker-compose logs api"
test_service "Voice" "http://localhost:8001/health" || echo "  Try: docker-compose logs voice"
test_service "Model Router" "http://localhost:8002/health" || echo "  Try: docker-compose logs model-router"
test_service "Frontend" "http://localhost:3000" || echo "  Try: docker-compose logs frontend"

echo ""
echo -e "${GREEN}🎉 Testing complete!${NC}"
echo ""
echo -e "${YELLOW}Quick commands:${NC}"
echo "  View logs: docker-compose logs -f [service]"
echo "  Restart: docker-compose restart [service]"
echo "  Stop: docker-compose down"
