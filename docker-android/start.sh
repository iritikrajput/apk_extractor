#!/bin/bash

echo "Starting Docker Android Container..."

# Start Android emulator in background
echo "Starting emulator..."
/root/start-emulator.sh &

# Wait for emulator to be ready
echo "Waiting for emulator..."
timeout 300 adb wait-for-device
sleep 10

# Check device status
echo "Device status:"
adb devices

# Start device agent
echo "Starting device agent..."
cd /app
python3 device_agent.py
