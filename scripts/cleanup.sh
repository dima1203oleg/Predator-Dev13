#!/bin/bash
# Clean up script for Predator Analytics Docker resources

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🧹 Cleaning up Predator Analytics Docker resources${NC}"
echo ""

# Ask for confirmation
read -p "This will remove all Predator containers, images, and volumes. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Stopping and removing containers...${NC}"
docker-compose down -v || true

echo ""
echo -e "${YELLOW}Removing Predator images...${NC}"
docker images | grep predator | awk '{print $3}' | xargs docker rmi -f || true

echo ""
echo -e "${YELLOW}Removing dangling images...${NC}"
docker image prune -f

echo ""
echo -e "${YELLOW}Removing unused volumes...${NC}"
docker volume prune -f

echo ""
echo -e "${YELLOW}Current disk usage:${NC}"
docker system df

echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo ""
echo -e "${YELLOW}To free up more space, run:${NC}"
echo "  docker system prune -a --volumes"
