#!/bin/bash

# ==============================================
# APK Extractor - Create Android Virtual Device
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo "APK Extractor - Create AVD with Play Store"
echo -e "==============================================${NC}"
echo ""

# Set Android SDK paths
if [ -z "$ANDROID_HOME" ]; then
    # Try common locations
    if [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
    elif [ -d "/opt/android-sdk" ]; then
        export ANDROID_HOME="/opt/android-sdk"
    elif [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    else
        echo -e "${RED}Error: ANDROID_HOME not set and couldn't find Android SDK${NC}"
        echo ""
        echo "Please set ANDROID_HOME environment variable:"
        echo "  export ANDROID_HOME=~/Android/Sdk"
        exit 1
    fi
fi

echo -e "${GREEN}ANDROID_HOME: $ANDROID_HOME${NC}"

# Update PATH
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
export PATH="$PATH:$ANDROID_HOME/platform-tools"
export PATH="$PATH:$ANDROID_HOME/emulator"

# Check for required tools
echo -e "\n${YELLOW}Checking required tools...${NC}"

if ! command -v sdkmanager &> /dev/null; then
    echo -e "${RED}Error: sdkmanager not found${NC}"
    echo "Please install Android SDK command-line tools"
    exit 1
fi
echo -e "${GREEN}✓ sdkmanager found${NC}"

if ! command -v avdmanager &> /dev/null; then
    echo -e "${RED}Error: avdmanager not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ avdmanager found${NC}"

# Configuration
AVD_NAME="${AVD_NAME:-playstore_device}"
SYSTEM_IMAGE="system-images;android-30;google_apis_playstore;x86_64"
DEVICE_TYPE="pixel_3a"

echo -e "\n${CYAN}Configuration:${NC}"
echo "  AVD Name: $AVD_NAME"
echo "  System Image: Android 11 (API 30) with Play Store"
echo "  Device: $DEVICE_TYPE"
echo ""

# Accept licenses
echo -e "${YELLOW}Accepting SDK licenses...${NC}"
yes | sdkmanager --licenses 2>/dev/null || true

# Install required packages
echo -e "\n${YELLOW}Installing required SDK packages...${NC}"

echo "Installing platform-tools..."
sdkmanager "platform-tools" --install 2>/dev/null || true

echo "Installing emulator..."
sdkmanager "emulator" --install 2>/dev/null || true

echo "Installing system image with Play Store..."
sdkmanager "$SYSTEM_IMAGE" --install

echo -e "${GREEN}✓ SDK packages installed${NC}"

# Delete existing AVD if it exists
if avdmanager list avd 2>/dev/null | grep -q "Name: $AVD_NAME"; then
    echo -e "\n${YELLOW}Deleting existing AVD '$AVD_NAME'...${NC}"
    avdmanager delete avd -n "$AVD_NAME" 2>/dev/null || true
fi

# Create AVD
echo -e "\n${YELLOW}Creating AVD '$AVD_NAME'...${NC}"

avdmanager create avd \
    -n "$AVD_NAME" \
    -k "$SYSTEM_IMAGE" \
    -d "$DEVICE_TYPE" \
    --force

echo -e "${GREEN}✓ AVD created successfully!${NC}"

# Configure AVD for better performance
AVD_CONFIG="$HOME/.android/avd/${AVD_NAME}.avd/config.ini"

if [ -f "$AVD_CONFIG" ]; then
    echo -e "\n${YELLOW}Configuring AVD for optimal performance...${NC}"
    
    # Set RAM
    if ! grep -q "hw.ramSize" "$AVD_CONFIG"; then
        echo "hw.ramSize=2048" >> "$AVD_CONFIG"
    else
        sed -i 's/hw.ramSize=.*/hw.ramSize=2048/' "$AVD_CONFIG"
    fi
    
    # Enable keyboard
    if ! grep -q "hw.keyboard" "$AVD_CONFIG"; then
        echo "hw.keyboard=yes" >> "$AVD_CONFIG"
    else
        sed -i 's/hw.keyboard=.*/hw.keyboard=yes/' "$AVD_CONFIG"
    fi
    
    # Set heap size
    if ! grep -q "vm.heapSize" "$AVD_CONFIG"; then
        echo "vm.heapSize=512" >> "$AVD_CONFIG"
    fi
    
    echo -e "${GREEN}✓ AVD configured${NC}"
fi

echo -e "\n${CYAN}=============================================="
echo "AVD Creation Complete"
echo -e "==============================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the emulator with GUI (first time setup):"
echo "   emulator -avd $AVD_NAME"
echo ""
echo "2. In the emulator:"
echo "   - Open Play Store"
echo "   - Sign in with a Google account"
echo "   - Accept terms and conditions"
echo "   - Install test apps"
echo ""
echo "3. After setup, start headless for production:"
echo "   ./start_emulator.sh"
echo ""
echo "Note: The first boot may take several minutes."
echo ""
