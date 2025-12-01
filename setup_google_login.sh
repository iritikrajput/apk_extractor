#!/bin/bash
# ==============================================
# One-Time Google Play Store Sign-In Setup
# ==============================================
#
# Google Play Store requires manual sign-in due to
# security measures (CAPTCHA, device verification).
#
# This script starts the emulator WITH a GUI so you
# can sign in manually. The credentials will persist
# for future headless runs.
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "=============================================="
echo "  Google Play Store - One-Time Setup"
echo "=============================================="
echo -e "${NC}"

# Check Android SDK
if [ -z "$ANDROID_HOME" ]; then
    export ANDROID_HOME=~/Android/Sdk
fi
export PATH=$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools

# Kill any running emulators
echo -e "${YELLOW}Stopping any running emulators...${NC}"
adb emu kill 2>/dev/null || true
pkill -f "qemu-system" 2>/dev/null || true
sleep 3

# Check if AVD exists
if ! emulator -list-avds 2>/dev/null | grep -q "Pixel_8_API_36"; then
    echo -e "${RED}Error: AVD 'Pixel_8_API_36' not found${NC}"
    echo "Create it first with: avdmanager create avd -n Pixel_8_API_36 -k 'system-images;android-34;google_apis_playstore;x86_64' -d 'pixel_3a'"
    exit 1
fi

echo ""
echo -e "${GREEN}Starting emulator WITH GUI...${NC}"
echo ""

# Start emulator with GUI
emulator -avd Pixel_8_API_36 -gpu swiftshader_indirect &
EMULATOR_PID=$!

echo -e "${CYAN}"
echo "=============================================="
echo "        MANUAL SIGN-IN REQUIRED"
echo "=============================================="
echo -e "${NC}"
echo ""
echo "In the emulator window:"
echo ""
echo -e "  ${GREEN}1.${NC} Wait for emulator to fully boot (1-2 minutes)"
echo -e "  ${GREEN}2.${NC} Open the ${YELLOW}Play Store${NC} app"
echo -e "  ${GREEN}3.${NC} Tap ${YELLOW}Sign in${NC}"
echo -e "  ${GREEN}4.${NC} Enter your Google credentials"
echo -e "  ${GREEN}5.${NC} Accept all terms and conditions"
echo -e "  ${GREEN}6.${NC} ${RED}IMPORTANT:${NC} Download any small app to verify sign-in works"
echo -e "  ${GREEN}7.${NC} Close the emulator window when done"
echo ""
echo -e "${YELLOW}After signing in:${NC}"
echo "  - The login will persist across emulator restarts"
echo "  - Run ${GREEN}./start_server.sh${NC} to start in headless mode"
echo ""
echo "=============================================="
echo ""
echo -e "${CYAN}Press Ctrl+C to cancel if needed${NC}"
echo ""

# Wait for emulator process
wait $EMULATOR_PID 2>/dev/null || true

echo ""
echo -e "${GREEN}Emulator closed.${NC}"
echo ""
echo "If you successfully signed in, you can now run:"
echo -e "  ${GREEN}./start_server.sh${NC}"
echo ""


