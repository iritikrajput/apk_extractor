#!/bin/bash

# ==============================================
# APK Extractor - Docker Setup Script
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo "APK Extractor - Docker Setup"
echo -e "==============================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check Docker
echo -e "${YELLOW}Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found.${NC}"
    echo ""
    echo "Please install Docker:"
    echo "  Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
    echo "  macOS: brew install --cask docker"
    echo ""
    exit 1
fi

DOCKER_VERSION=$(docker --version)
echo -e "${GREEN}✓ $DOCKER_VERSION${NC}"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker daemon is not running.${NC}"
    echo "Please start Docker and try again."
    exit 1
fi

# Check Docker Compose
echo -e "\n${YELLOW}Checking Docker Compose...${NC}"
COMPOSE_CMD=""

if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version)
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version)
else
    echo -e "${RED}✗ Docker Compose not found.${NC}"
    echo ""
    echo "Please install Docker Compose:"
    echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "  sudo chmod +x /usr/local/bin/docker-compose"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ $COMPOSE_VERSION${NC}"

# Check KVM support (for Android emulator performance)
echo -e "\n${YELLOW}Checking KVM support...${NC}"
if [ -e /dev/kvm ]; then
    echo -e "${GREEN}✓ KVM is available (hardware acceleration)${NC}"
else
    echo -e "${YELLOW}⚠ KVM not available${NC}"
    echo "  Android emulator will run slower without hardware acceleration."
    echo "  Enable KVM: sudo modprobe kvm"
fi

# Build options
echo -e "\n${CYAN}Build Options:${NC}"
echo "1. Build docker-android containers only"
echo "2. Build full stack (android + orchestrator + web-backend)"
echo "3. Build and start full stack"
echo ""
read -p "Select option [1-3]: " BUILD_OPTION

case $BUILD_OPTION in
    1)
        echo -e "\n${YELLOW}Building docker-android containers...${NC}"
        cd docker-android
        $COMPOSE_CMD build
        echo -e "${GREEN}✓ docker-android containers built${NC}"
        ;;
    2)
        echo -e "\n${YELLOW}Building full stack...${NC}"
        $COMPOSE_CMD build
        echo -e "${GREEN}✓ Full stack built${NC}"
        ;;
    3)
        echo -e "\n${YELLOW}Building and starting full stack...${NC}"
        $COMPOSE_CMD build
        $COMPOSE_CMD up -d
        echo -e "${GREEN}✓ Full stack built and started${NC}"
        
        echo -e "\n${CYAN}Container Status:${NC}"
        $COMPOSE_CMD ps
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "\n${CYAN}=============================================="
echo "Docker Setup Complete"
echo -e "==============================================${NC}"
echo ""
echo "Useful commands:"
echo ""
echo "  Start containers:"
echo "    $COMPOSE_CMD up -d"
echo ""
echo "  Stop containers:"
echo "    $COMPOSE_CMD down"
echo ""
echo "  View logs:"
echo "    $COMPOSE_CMD logs -f"
echo ""
echo "  Check status:"
echo "    $COMPOSE_CMD ps"
echo ""
echo "  Rebuild after changes:"
echo "    $COMPOSE_CMD build --no-cache"
echo ""
echo "Access the web interface at: http://localhost:8000"
echo "Default login: admin / apkextractor"
echo ""

# Note about Play Store setup
echo -e "${YELLOW}Important:${NC}"
echo "The Android emulator in Docker needs Play Store setup."
echo "This requires manual intervention the first time."
echo "See docker-android/README.md for instructions."
echo ""
