#!/bin/bash

echo "Installing APK Extractor dependencies..."

# Install Python dependencies
echo "Installing Python packages..."
pip install -r device-agent/requirements.txt
pip install -r web-backend/requirements.txt

# Check for Android SDK
if [ -z "$ANDROID_HOME" ]; then
    echo "⚠ ANDROID_HOME not set!"
    echo "Please install Android SDK command-line tools"
    echo "Download from: https://developer.android.com/studio#command-tools"
    exit 1
fi

# Check for adb
if ! command -v adb &> /dev/null; then
    echo "⚠ adb not found in PATH"
    exit 1
fi

echo "✓ All dependencies installed!"
