# Web Backend

Web interface and API gateway for APK Extractor.

## Features

- Simple, clean web interface
- Enter package name → Get APK download
- Supports single device and orchestrator modes
- Real-time extraction status

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start backend
python web_backend.py
```

Access at: http://localhost:8000

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_ORCHESTRATOR` | `false` | Enable orchestrator mode |
| `ORCHESTRATOR_URL` | `http://localhost:8001` | Orchestrator URL |
| `DEVICE_AGENT_URL` | `http://localhost:5001` | Device agent URL |
| `EXTRACTION_TIMEOUT` | `180` | Extraction timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/api/health` | GET | Health check |
| `/api/extract` | POST | Extract APK |
| `/api/status/{job_id}` | GET | Job status (orchestrator) |
| `/api/download/{pkg}/{file}` | GET | Download APK |
| `/api/packages` | GET | List packages |

## Usage

1. Open http://localhost:8000
2. Enter package name (e.g., `com.whatsapp`)
3. Click "Extract APK"
4. Wait for extraction
5. Download the APK files

## Directory Structure

```
web-backend/
├── web_backend.py     # Main application
├── requirements.txt   # Dependencies
├── Dockerfile         # Docker build
├── templates/         # HTML templates
│   ├── index.html     # Main UI
│   ├── 404.html       # Error page
│   └── 500.html       # Error page
└── logs/              # Logs
```
