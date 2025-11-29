# Docker Android

Dockerized Android emulator with device agent for APK extraction.

## Features

- Android 11 emulator with Play Store
- Pre-installed device agent
- Optimized for headless operation
- Shared volume for APK storage

## Base Image

Uses `budtmo/docker-android:emulator_11.0` which provides:
- Android emulator
- ADB access
- VNC (optional)

## Build

```bash
docker build -t apk-extractor-android .
```

## Run Single Container

```bash
docker run -d \
  --privileged \
  -p 5001:5001 \
  -v $(pwd)/pulls:/app/pulls \
  --shm-size=2g \
  apk-extractor-android
```

## Run Multiple Containers

```bash
docker-compose up -d
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `emulator-5554` | ADB device ID |
| `EMULATOR_DEVICE` | `Samsung Galaxy S10` | Emulator device type |
| `WEB_VNC` | `false` | Enable VNC access |

## First-Time Setup

The Play Store needs to be configured manually:

1. Start container with VNC enabled:
   ```bash
   docker run -d -p 5001:5001 -p 6080:6080 \
     -e WEB_VNC=true \
     --privileged --shm-size=2g \
     apk-extractor-android
   ```

2. Open VNC: http://localhost:6080

3. In emulator:
   - Open Play Store
   - Sign in with Google account
   - Accept terms

4. Restart without VNC for production

## Directory Structure

```
docker-android/
├── Dockerfile           # Container definition
├── docker-compose.yml   # Multi-container setup
├── device_agent.py      # Extraction service
├── requirements.txt     # Python dependencies
├── start.sh             # Startup script
├── pulls/               # Shared APK storage
└── README.md
```

## Health Check

```bash
curl http://localhost:5001/health
```

## Logs

```bash
docker logs android-device-1
```

## Resource Requirements

Per container:
- **CPU**: 2 cores minimum
- **RAM**: 2GB minimum
- **Storage**: 10GB
- **Shared Memory**: 2GB (--shm-size)
