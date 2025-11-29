#!/bin/bash

# ==============================================
# APK Extractor - 24/7 Server Start Script
# ==============================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
AVD_NAME="${AVD_NAME:-playstore_device}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo "APK Extractor - 24/7 Server"
echo -e "==============================================${NC}"
echo ""

# Function to check if emulator is running
is_emulator_running() {
    adb devices 2>/dev/null | grep -q "emulator"
}

# Function to start emulator
start_emulator() {
    echo -e "${YELLOW}Starting emulator in headless mode (24/7)...${NC}"
    
    # Check AVD exists
    if ! avdmanager list avd 2>/dev/null | grep -q "Name: $AVD_NAME"; then
        echo -e "${RED}Error: AVD '$AVD_NAME' not found${NC}"
        exit 1
    fi
    
    # Start emulator with settings for 24/7 operation
    emulator -avd "$AVD_NAME" \
        -no-window \
        -no-audio \
        -no-boot-anim \
        -gpu swiftshader_indirect \
        -no-snapshot-save \
        -memory 2048 \
        &
    
    echo "Waiting for emulator to boot..."
    timeout 180 adb wait-for-device || {
        echo -e "${RED}Emulator failed to start${NC}"
        exit 1
    }
    
    # Wait for boot completion
    for i in {1..90}; do
        if adb shell pm list packages -s 2>/dev/null | grep -q "package:"; then
            break
        fi
        echo -ne "  Booting... ($i/90)\r"
        sleep 2
    done
    echo ""
    
    # Configure for 24/7 operation
    echo -e "${YELLOW}Configuring for 24/7 operation...${NC}"
    
    # Disable screen timeout
    adb shell settings put system screen_off_timeout 2147483647 2>/dev/null || true
    
    # Stay awake while plugged in
    adb shell settings put global stay_on_while_plugged_in 7 2>/dev/null || true
    
    # Disable lock screen
    adb shell settings put secure lockscreen.disabled 1 2>/dev/null || true
    
    # Wake up device
    adb shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true
    adb shell input swipe 500 1500 500 500 2>/dev/null || true
    
    echo -e "${GREEN}✓ Emulator ready (24/7 mode)${NC}"
}

# Check emulator
if is_emulator_running; then
    echo -e "${GREEN}✓ Emulator already running${NC}"
else
    start_emulator
fi

# Kill existing services (but NOT emulator)
echo -e "\n${YELLOW}Restarting services...${NC}"
pkill -f "device_agent.py" 2>/dev/null || true
pkill -f "web_backend.py" 2>/dev/null || true
sleep 2

# Start Device Agent
echo -e "${YELLOW}Starting Device Agent...${NC}"
cd "$SCRIPT_DIR/device-agent"
nohup python3 device_agent.py > /tmp/device_agent.log 2>&1 &
sleep 3

if curl -s http://localhost:5001/health > /dev/null; then
    echo -e "${GREEN}✓ Device Agent running on port 5001${NC}"
else
    echo -e "${RED}✗ Device Agent failed${NC}"
    cat /tmp/device_agent.log
    exit 1
fi

# Start Web Backend
echo -e "${YELLOW}Starting Web Backend...${NC}"
cd "$SCRIPT_DIR/web-backend"
nohup python3 web_backend.py > /tmp/web_backend.log 2>&1 &
sleep 3

if curl -s http://localhost:8000/api/health > /dev/null; then
    echo -e "${GREEN}✓ Web Backend running on port 8000${NC}"
else
    echo -e "${RED}✗ Web Backend failed${NC}"
    cat /tmp/web_backend.log
    exit 1
fi

# Get IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo -e "\n${CYAN}=============================================="
echo "APK Extractor Ready - 24/7 Mode"
echo -e "==============================================${NC}"
echo ""
echo -e "${GREEN}Web Interface:${NC}"
echo "  http://localhost:8000"
echo "  http://$LOCAL_IP:8000"
echo ""
echo -e "${CYAN}Features:${NC}"
echo "  ✓ Auto-install from Play Store"
echo "  ✓ Auto-cleanup after download"
echo "  ✓ 24/7 headless operation"
echo "  ✓ No emulator restart needed"

if [ -n "$GOOGLE_EMAIL" ]; then
    echo "  ✓ Google auto-login configured"
else
    echo -e "  ${YELLOW}⚠ Google login not configured${NC}"
    echo "    Set GOOGLE_EMAIL and GOOGLE_PASSWORD in .env"
fi

echo ""
echo -e "${YELLOW}Note: Emulator keeps running even after this script exits${NC}"
echo ""
