#!/bin/bash

echo "Setting up Docker Android environment..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠ Docker not found. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "⚠ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# Build containers
echo "Building Docker Android containers..."
cd docker-android
docker-compose build

echo "✓ Docker setup complete!"
echo ""
echo "To start containers:"
echo "  cd docker-android"
echo "  docker-compose up -d"
echo ""
echo "To start orchestrator:"
echo "  cd orchestrator"
echo "  python orchestrator.py"
