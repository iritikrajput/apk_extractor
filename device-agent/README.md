# Device Agent

APK extraction service that interfaces with Android devices via ADB.

## Features

- Extract APKs from installed apps
- Support for split APKs (Android App Bundles)
- SHA-256 hash verification
- Audit logging
- Input validation
- ADB retry logic

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Android emulator is running
adb devices

# Start agent
python device_agent.py
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_ID` | `emulator-5554` | ADB device identifier |
| `APK_STORAGE_PATH` | `./pulls` | APK storage directory |
| `LOG_PATH` | `./logs` | Log directory |
| `ADB_TIMEOUT` | `60` | ADB command timeout (seconds) |
| `EXTRACTION_TIMEOUT` | `300` | Max extraction time (seconds) |
| `MAX_RETRIES` | `3` | ADB retry attempts |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/extract_apk` | POST | Extract APK |
| `/download_apk/{pkg}/{file}` | GET | Download APK |
| `/list_packages` | GET | List extracted packages |
| `/delete_package/{pkg}` | DELETE | Delete package |

## Directory Structure

```
device-agent/
├── device_agent.py    # Main application
├── requirements.txt   # Dependencies
├── pulls/             # Extracted APKs
│   └── com.example/
│       ├── base.apk
│       └── split_1.apk
└── logs/              # Logs
    ├── device_agent.log
    └── audit.log
```

