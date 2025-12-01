#!/bin/bash

# ==============================================
# APK Extractor - Start Android Emulator
# ==============================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
AVD_NAME="${AVD_NAME:-Pixel_8_API_36}"
HEADLESS="${HEADLESS:-true}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300}"

echo -e "${CYAN}=============================================="
echo "APK Extractor - Start Emulator"
echo -e "==============================================${NC}"
echo ""

# Set Android SDK paths
if [ -z "$ANDROID_HOME" ]; then
    if [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
    elif [ -d "/opt/android-sdk" ]; then
        export ANDROID_HOME="/opt/android-sdk"
    elif [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    else
        echo -e "${RED}Error: ANDROID_HOME not set${NC}"
        exit 1
    fi
fi

export PATH="$PATH:$ANDROID_HOME/emulator"
export PATH="$PATH:$ANDROID_HOME/platform-tools"

# Check if emulator is already running
if adb devices 2>/dev/null | grep -q "emulator"; then
    echo -e "${YELLOW}Emulator already running${NC}"
    adb devices
    
    # Check boot status
    boot_completed=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
    if [ "$boot_completed" == "1" ]; then
        echo -e "${GREEN}✓ Emulator is ready${NC}"
        exit 0
    else
        echo -e "${YELLOW}Emulator is still booting...${NC}"
    fi
fi

# Check if AVD exists
if ! avdmanager list avd 2>/dev/null | grep -q "Name: $AVD_NAME"; then
    echo -e "${RED}Error: AVD '$AVD_NAME' not found${NC}"
    echo "Create it first: ./create_avd.sh"
    exit 1
fi

echo "AVD: $AVD_NAME"
echo "Headless: $HEADLESS"
echo ""

# Build emulator command
EMULATOR_CMD="emulator -avd $AVD_NAME"

if [ "$HEADLESS" = true ]; then
    EMULATOR_CMD="$EMULATOR_CMD -no-window -no-audio -no-boot-anim"
fi

# Add GPU acceleration
if [ -e /dev/kvm ]; then
    EMULATOR_CMD="$EMULATOR_CMD -gpu host"
else
    EMULATOR_CMD="$EMULATOR_CMD -gpu swiftshader_indirect"
fi

# Add memory settings
EMULATOR_CMD="$EMULATOR_CMD -memory 2048"

# Start emulator in background
echo -e "${YELLOW}Starting emulator...${NC}"
echo "Command: $EMULATOR_CMD"
echo ""

$EMULATOR_CMD &
EMULATOR_PID=$!

# Wait for device
echo -e "${YELLOW}Waiting for device to appear...${NC}"
adb wait-for-device

# Wait for boot to complete
echo -e "${YELLOW}Waiting for boot to complete (timeout: ${WAIT_TIMEOUT}s)...${NC}"

start_time=$(date +%s)
while true; do
    boot_completed=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
    
    if [ "$boot_completed" == "1" ]; then
        break
    fi
    
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $WAIT_TIMEOUT ]; then
        echo -e "${RED}Error: Boot timeout after ${WAIT_TIMEOUT}s${NC}"
        exit 1
    fi
    
    echo -ne "  Waiting... (${elapsed}s)\r"
    sleep 5
done

echo ""
echo -e "${GREEN}✓ Emulator is ready!${NC}"
echo ""

# Show device info
echo -e "${CYAN}Device Info:${NC}"
echo "  Android: $(adb shell getprop ro.build.version.release | tr -d '\r')"
echo "  SDK: $(adb shell getprop ro.build.version.sdk | tr -d '\r')"
echo "  Model: $(adb shell getprop ro.product.model | tr -d '\r')"
echo ""

# Show connected devices
echo -e "${CYAN}Connected Devices:${NC}"
adb devices

echo ""
echo -e "${CYAN}=============================================="
echo "Emulator Started"
echo -e "==============================================${NC}"
echo ""
echo "You can now start the device agent:"
echo "  cd device-agent && python3 device_agent.py"
echo ""
echo "To stop the emulator:"
echo "  adb emu kill"
echo ""
