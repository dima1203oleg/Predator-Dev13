#!/bin/bash
set -e

# Build and push Docker images for Predator Analytics v13
# Usage: ./scripts/build_images.sh [registry] [version]

REGISTRY="${1:-ghcr.io/your-org}"
VERSION="${2:-13.0.0}"
PLATFORM="linux/amd64,linux/arm64"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building Predator Analytics Docker Images${NC}"
echo -e "${YELLOW}Registry: ${REGISTRY}${NC}"
echo -e "${YELLOW}Version: ${VERSION}${NC}"
echo ""

# Check if buildx is available
if ! docker buildx version &> /dev/null; then
    echo -e "${RED}❌ Docker buildx not found. Please install Docker Buildx.${NC}"
    exit 1
fi

# Create buildx builder if not exists
if ! docker buildx inspect predator-builder &> /dev/null; then
    echo -e "${YELLOW}Creating buildx builder 'predator-builder'...${NC}"
    docker buildx create --name predator-builder --use
fi

# Function to build and push image
build_and_push() {
    local service=$1
    local dockerfile=$2
    local context=$3
    
    echo -e "${GREEN}Building ${service}...${NC}"
    
    docker buildx build \
        --platform ${PLATFORM} \
        --file ${dockerfile} \
        --tag ${REGISTRY}/predator-${service}:${VERSION} \
        --tag ${REGISTRY}/predator-${service}:latest \
        --push \
        ${context}
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${service} built and pushed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to build ${service}${NC}"
        exit 1
    fi
    echo ""
}

# Build images
echo -e "${YELLOW}1/5 Building API service...${NC}"
build_and_push "api" "./api/Dockerfile" "."

echo -e "${YELLOW}2/5 Building Agents service...${NC}"
build_and_push "agents" "./agents/Dockerfile" "."

echo -e "${YELLOW}3/5 Building Frontend service...${NC}"
build_and_push "frontend" "./frontend/Dockerfile" "."

echo -e "${YELLOW}4/5 Building Voice service...${NC}"
build_and_push "voice" "./voice/Dockerfile" "."

echo -e "${YELLOW}5/5 Building Model Router service...${NC}"
build_and_push "model-router" "./model-router/Dockerfile" "."

echo -e "${GREEN}🎉 All images built and pushed successfully!${NC}"
echo ""
echo -e "${YELLOW}Images:${NC}"
echo "  - ${REGISTRY}/predator-api:${VERSION}"
echo "  - ${REGISTRY}/predator-agents:${VERSION}"
echo "  - ${REGISTRY}/predator-frontend:${VERSION}"
echo "  - ${REGISTRY}/predator-voice:${VERSION}"
echo "  - ${REGISTRY}/predator-model-router:${VERSION}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update helm/predator-umbrella/values-prod.yaml with new image tags"
echo "2. Run ./scripts/preflight_check.sh"
echo "3. Deploy with helm install or ArgoCD"
