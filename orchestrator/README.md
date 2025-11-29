# Orchestrator

Load balancer and job queue manager for multi-container APK extraction.

## Features

- Container pool management
- Health monitoring
- Job queue with threading
- Result caching with expiration
- Round-robin load balancing

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start orchestrator
python orchestrator.py
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTAINER_URLS` | `http://localhost:5001,...` | Container URLs (comma-separated) |
| `WORKER_THREADS` | `3` | Worker thread count |
| `EXTRACTION_TIMEOUT` | `180` | Extraction timeout (seconds) |
| `HEALTH_CHECK_INTERVAL` | `60` | Health check interval (seconds) |
| `RESULT_EXPIRATION` | `3600` | Result cache expiration (seconds) |
| `MAX_CACHED_RESULTS` | `1000` | Maximum cached results |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health status |
| `/extract` | POST | Queue extraction job |
| `/status/{job_id}` | GET | Check job status |
| `/download/{pkg}/{file}` | GET | Download APK |
| `/packages` | GET | List packages |
| `/stats` | GET | System statistics |

## Architecture

```
Orchestrator
├── Job Queue (threading.Queue)
├── Worker Threads (3 default)
├── Container Pool
│   ├── android-1 (healthy/busy status)
│   ├── android-2
│   └── android-3
└── Result Cache (LRU with expiration)
```

## Job Flow

1. Request received → Job queued
2. Worker picks job from queue
3. Worker finds available container
4. Container extracts APK
5. Result cached
6. Container released
7. Client polls for result

## Monitoring

- `/health` - Container status, queue size
- `/stats` - Job statistics, configuration
