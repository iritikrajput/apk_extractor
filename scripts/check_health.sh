#!/bin/bash

echo "Checking system health..."

# Check emulator
echo -n "Emulator: "
if adb devices | grep -q "emulator"; then
    echo "✓ Running"
else
    echo "✗ Not running"
fi

# Check device agent
echo -n "Device Agent: "
if curl -s http://localhost:5001/health > /dev/null; then
    echo "✓ Online"
else
    echo "✗ Offline"
fi

# Check web backend
echo -n "Web Backend: "
if curl -s http://localhost:8000 > /dev/null; then
    echo "✓ Online"
else
    echo "✗ Offline"
fi
echo "Health check complete."