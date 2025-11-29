#!/bin/bash

# ==============================================
# APK Extractor - Dependency Installation Script
# ==============================================

set -e

echo "=============================================="
echo "APK Extractor - Installing Dependencies"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check Python
echo -e "\n${YELLOW}Checking Python...${NC}"
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

# Check pip
echo -e "\n${YELLOW}Checking pip...${NC}"
if command_exists pip3; then
    PIP_VERSION=$(pip3 --version 2>&1)
    echo -e "${GREEN}✓ pip3 available${NC}"
else
    echo -e "${RED}✗ pip3 not found. Please install pip${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"

echo "Installing device-agent dependencies..."
pip3 install -r device-agent/requirements.txt --quiet

echo "Installing web-backend dependencies..."
pip3 install -r web-backend/requirements.txt --quiet

echo "Installing orchestrator dependencies..."
pip3 install -r orchestrator/requirements.txt --quiet

echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Check for Android SDK
echo -e "\n${YELLOW}Checking Android SDK...${NC}"
if [ -n "$ANDROID_HOME" ]; then
    echo -e "${GREEN}✓ ANDROID_HOME is set: $ANDROID_HOME${NC}"
else
    echo -e "${YELLOW}⚠ ANDROID_HOME not set${NC}"
    echo "  For Phase 1 (single device), you need Android SDK."
    echo "  Set ANDROID_HOME in your shell profile:"
    echo "    export ANDROID_HOME=~/Android/Sdk"
    echo "    export PATH=\$PATH:\$ANDROID_HOME/platform-tools"
    echo "    export PATH=\$PATH:\$ANDROID_HOME/emulator"
fi

# Check for ADB
echo -e "\n${YELLOW}Checking ADB...${NC}"
if command_exists adb; then
    ADB_VERSION=$(adb version 2>&1 | head -1)
    echo -e "${GREEN}✓ $ADB_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ adb not found in PATH${NC}"
    echo "  Install Android platform-tools or add to PATH"
fi

# Check for Docker (Phase 2)
echo -e "\n${YELLOW}Checking Docker (optional, for Phase 2)...${NC}"
if command_exists docker; then
    DOCKER_VERSION=$(docker --version 2>&1)
    echo -e "${GREEN}✓ $DOCKER_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ Docker not found (optional for Phase 2)${NC}"
fi

# Check for Docker Compose (Phase 2)
echo -e "\n${YELLOW}Checking Docker Compose (optional, for Phase 2)...${NC}"
if command_exists docker-compose; then
    COMPOSE_VERSION=$(docker-compose --version 2>&1)
    echo -e "${GREEN}✓ $COMPOSE_VERSION${NC}"
elif command_exists docker && docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version 2>&1)
    echo -e "${GREEN}✓ $COMPOSE_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ Docker Compose not found (optional for Phase 2)${NC}"
fi

# Create necessary directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p device-agent/pulls
mkdir -p device-agent/logs
mkdir -p web-backend/logs
mkdir -p orchestrator/logs
echo -e "${GREEN}✓ Directories created${NC}"

# Copy env.example if .env doesn't exist
echo -e "\n${YELLOW}Checking configuration...${NC}"
if [ -f "env.example" ] && [ ! -f ".env" ]; then
    echo "Creating .env from env.example..."
    cp env.example .env
    echo -e "${GREEN}✓ .env created (please edit with your settings)${NC}"
elif [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env already exists${NC}"
else
    echo -e "${YELLOW}⚠ No env.example found${NC}"
fi

# Make scripts executable
echo -e "\n${YELLOW}Making scripts executable...${NC}"
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x emulator-setup/*.sh 2>/dev/null || true
echo -e "${GREEN}✓ Scripts are executable${NC}"

echo -e "\n=============================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Phase 1 (Single Device):"
echo "   - Set up Android emulator: ./emulator-setup/create_avd.sh"
echo "   - Start emulator: ./emulator-setup/start_emulator.sh"
echo "   - Start device agent: cd device-agent && python3 device_agent.py"
echo "   - Start web backend: cd web-backend && python3 web_backend.py"
echo "   - Open http://localhost:8000"
echo ""
echo "2. Phase 2 (Docker):"
echo "   - Build containers: ./scripts/docker_setup.sh"
echo "   - Start: docker-compose up -d"
echo "   - Open http://localhost:8000"
echo ""
echo "Default login: admin / apkextractor"
echo ""
