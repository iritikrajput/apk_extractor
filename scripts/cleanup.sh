#!/bin/bash

# Clean up old APK files

PULLS_DIR="device-agent/pulls"

if [ -d "$PULLS_DIR" ]; then
    echo "Cleaning up APK files in $PULLS_DIR..."
    
    # Delete APK folders older than 7 days
    find "$PULLS_DIR" -type d -mtime +7 -exec rm -rf {} +
    
    echo "✓ Cleanup complete"
else
    echo "No pulls directory found"
fi
