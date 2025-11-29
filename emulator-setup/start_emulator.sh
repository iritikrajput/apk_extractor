#!/bin/bash

# Start Android Emulator in headless mode

export ANDROID_HOME=~/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/emulator

echo "Starting Android emulator (headless)..."

emulator -avd playstore_device \
  -no-window \
  -no-audio \
  -no-boot-anim \
  -gpu swiftshader_indirect \
  -memory 2048 \
  &

echo "Waiting for device to boot..."
adb wait-for-device

echo "✓ Emulator is ready!"
adb devices
