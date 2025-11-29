#!/bin/bash

# Create Android Virtual Device with Play Store

echo "Creating Android AVD with Play Store..."

# Set Android SDK paths
export ANDROID_HOME=~/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/emulator

# Install system image if not present
echo "Installing Android 11 system image with Play Store..."
sdkmanager "system-images;android-30;google_apis_playstore;x86_64"

# Create AVD
echo "Creating AVD 'playstore_device'..."
avdmanager create avd \
  -n playstore_device \
  -k "system-images;android-30;google_apis_playstore;x86_64" \
  -d pixel_3a \
  --force

echo "✓ AVD created successfully!"
echo "Start with: ./start_emulator.sh"
