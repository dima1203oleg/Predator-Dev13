#!/bin/bash
set -e

# Build Docker images locally for Predator Analytics v13
# Usage: ./scripts/build_local.sh

VERSION="13.0.0"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building Predator Analytics Docker Images Locally${NC}"
echo -e "${YELLOW}Version: ${VERSION}${NC}"
echo ""

# Create poetry.lock if it doesn't exist
if [ ! -f "poetry.lock" ]; then
    echo -e "${YELLOW}Creating poetry.lock file...${NC}"
    cd "/Users/dima/Documents/Predator analitycs 13"
    source venv/bin/activate
    poetry lock --no-interaction || {
        echo -e "${RED}Failed to create poetry.lock, continuing without it${NC}"
    }
fi

# Function to build image locally
build_image() {
    local service=$1
    local dockerfile=$2
    local context=$3
    
    echo -e "${GREEN}Building ${service}...${NC}"
    
    docker build \
        --file ${dockerfile} \
        --tag predator-${service}:${VERSION} \
        --tag predator-${service}:latest \
        ${context}
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${service} built successfully${NC}"
    else
        echo -e "${RED}❌ Failed to build ${service}${NC}"
        return 1
    fi
    echo ""
}

# Build images
echo -e "${YELLOW}1/5 Building API service...${NC}"
build_image "api" "./api/Dockerfile" "." || exit 1

echo -e "${YELLOW}2/5 Building Agents service...${NC}"
build_image "agents" "./agents/Dockerfile" "." || exit 1

echo -e "${YELLOW}3/5 Building Frontend service...${NC}"
build_image "frontend" "./frontend/Dockerfile" "." || exit 1

echo -e "${YELLOW}4/5 Building Voice service...${NC}"
build_image "voice" "./voice/Dockerfile" "." || exit 1

echo -e "${YELLOW}5/5 Building Model Router service...${NC}"
build_image "model-router" "./model-router/Dockerfile" "." || exit 1

echo -e "${GREEN}🎉 All images built successfully!${NC}"
echo ""
echo -e "${YELLOW}Built images:${NC}"
docker images | grep "predator-" | grep -E "${VERSION}|latest"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test containers: docker run -d -p 8000:8000 predator-api:latest"
echo "2. Use docker-compose to run full stack"
echo "3. Push to registry if needed"
