#!/bin/bash

# ==============================================
# APK Extractor - Health Check Script
# ==============================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo "APK Extractor - Health Check"
echo -e "==============================================${NC}"
echo ""

# Check if jq is available for JSON parsing
HAS_JQ=false
if command -v jq &> /dev/null; then
    HAS_JQ=true
fi

# Function to check service
check_service() {
    local name=$1
    local url=$2
    local expected=$3
    
    echo -n -e "${YELLOW}$name: ${NC}"
    
    response=$(curl -s -o /tmp/health_response.txt -w "%{http_code}" "$url" 2>/dev/null)
    
    if [ "$response" == "$expected" ] || [ "$response" == "200" ]; then
        echo -e "${GREEN}✓ Online (HTTP $response)${NC}"
        
        # Show additional info if jq is available
        if [ "$HAS_JQ" = true ] && [ -f /tmp/health_response.txt ]; then
            if [ "$name" == "Orchestrator" ]; then
                containers=$(cat /tmp/health_response.txt | jq -r '.healthy_containers // "N/A"' 2>/dev/null)
                total=$(cat /tmp/health_response.txt | jq -r '.total_containers // "N/A"' 2>/dev/null)
                queue=$(cat /tmp/health_response.txt | jq -r '.queue_size // "N/A"' 2>/dev/null)
                echo -e "   Containers: $containers/$total healthy, Queue: $queue"
            elif [ "$name" == "Device Agent" ]; then
                status=$(cat /tmp/health_response.txt | jq -r '.status // "N/A"' 2>/dev/null)
                devices=$(cat /tmp/health_response.txt | jq -r '.devices_count // .devices // "N/A"' 2>/dev/null)
                echo -e "   Status: $status, Devices: $devices"
            fi
        fi
        return 0
    else
        echo -e "${RED}✗ Offline or Error (HTTP $response)${NC}"
        return 1
    fi
}

# Check emulator/ADB
echo -e "${CYAN}Android Emulator:${NC}"
echo -n -e "${YELLOW}ADB Connection: ${NC}"
if command -v adb &> /dev/null; then
    devices=$(adb devices 2>/dev/null | grep -c "device$")
    if [ "$devices" -gt 0 ]; then
        echo -e "${GREEN}✓ $devices device(s) connected${NC}"
        
        # Get device info
        boot_completed=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
        if [ "$boot_completed" == "1" ]; then
            android_version=$(adb shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')
            model=$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r')
            echo -e "   Android: $android_version, Model: $model"
        else
            echo -e "   ${YELLOW}Device is still booting...${NC}"
        fi
    else
        echo -e "${RED}✗ No devices connected${NC}"
    fi
else
    echo -e "${RED}✗ ADB not found${NC}"
fi
echo ""

# Check services
echo -e "${CYAN}Services:${NC}"
check_service "Device Agent" "http://localhost:5001/health" "200"
check_service "Web Backend" "http://localhost:8000/api/health" "200"
check_service "Orchestrator" "http://localhost:8001/health" "200"
echo ""

# Check Docker containers (if docker is available)
if command -v docker &> /dev/null; then
    echo -e "${CYAN}Docker Containers:${NC}"
    
    containers=$(docker ps --filter "name=android" --format "{{.Names}}: {{.Status}}" 2>/dev/null)
    if [ -n "$containers" ]; then
        while IFS= read -r line; do
            if [[ $line == *"Up"* ]]; then
                echo -e "${GREEN}✓ $line${NC}"
            else
                echo -e "${RED}✗ $line${NC}"
            fi
        done <<< "$containers"
    else
        echo -e "${YELLOW}No Android containers running${NC}"
    fi
    echo ""
fi

# Disk space check
echo -e "${CYAN}Storage:${NC}"
if [ -d "device-agent/pulls" ]; then
    pulls_size=$(du -sh device-agent/pulls 2>/dev/null | cut -f1)
    echo -e "APK Storage: $pulls_size"
fi

# Count extracted packages
if [ -d "device-agent/pulls" ]; then
    pkg_count=$(find device-agent/pulls -maxdepth 1 -type d | wc -l)
    pkg_count=$((pkg_count - 1))  # Subtract the pulls directory itself
    echo -e "Extracted Packages: $pkg_count"
fi

echo ""
echo -e "${CYAN}=============================================="
echo -e "Health check complete"
echo -e "==============================================${NC}"

# Cleanup
rm -f /tmp/health_response.txt
