# 📦 APK Extractor

**Extract official, unmodified APK files from Google Play Store for security analysis.**

A complete solution for downloading authentic APKs directly from Google Play Store using real Android emulators, designed for enterprise security auditing and vulnerability assessment.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Docker](https://img.shields.io/badge/docker-supported-blue.svg)

---

## 🎯 Features

- **Official APKs** - Extract directly from Google Play Store (no third-party sources)
- **Split APK Support** - Handle modern Android App Bundles with multiple APK files
- **Integrity Verification** - SHA-256 hashing for all extracted files
- **Audit Logging** - Complete trail for compliance requirements
- **Web Interface** - Beautiful, modern UI for easy operation
- **Two Deployment Modes**:
  - **Phase 1**: Single device for development/testing
  - **Phase 2**: Multi-container Docker deployment for production

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │────▶│   Web Backend   │────▶│  Device Agent   │
│   (User UI)     │     │   (Flask:8000)  │     │  (Flask:5001)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │ ADB
                                                         ▼
                                               ┌─────────────────┐
                                               │    Android      │
                                               │   Emulator      │
                                               │  (Play Store)   │
                                               └─────────────────┘
```

**Phase 2 (Production)** adds:
- Orchestrator for load balancing
- Multiple Android containers
- Job queue for async processing
- Shared storage volume

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Android SDK with emulator (Phase 1)
- Docker & Docker Compose (Phase 2)
- Google account for Play Store

### Phase 1: Single Device Setup

```bash
# 1. Clone and install dependencies
git clone https://github.com/your-repo/apk-extractor.git
cd apk-extractor
./scripts/install_dependencies.sh

# 2. Create Android emulator
./emulator-setup/create_avd.sh

# 3. Start emulator (first time with GUI for Play Store setup)
emulator -avd playstore_device
# Sign into Play Store, then close

# 4. Start emulator headless
./emulator-setup/start_emulator.sh

# 5. Start services (in separate terminals)
cd device-agent && python3 device_agent.py
cd web-backend && python3 web_backend.py

# 6. Open browser
# http://localhost:8000
# Login: admin / apkextractor
```

### Phase 2: Docker Deployment

```bash
# 1. Setup Docker
./scripts/docker_setup.sh

# 2. Start all containers
docker-compose up -d

# 3. Open browser
# http://localhost:8000
```

---

## 📖 Usage

### Web Interface

1. Navigate to `http://localhost:8000`
2. Login with credentials (default: admin/apkextractor)
3. Enter package name: `com.whatsapp`
   - Or paste Play Store URL
4. Click "Extract APK"
5. Download extracted files

### API

```bash
# Health check
curl http://localhost:8000/api/health

# Extract APK (single device mode)
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -u admin:apkextractor \
  -d '{"package": "com.whatsapp"}'

# Download APK
curl -u admin:apkextractor \
  -o whatsapp.apk \
  http://localhost:8000/api/download/com.whatsapp/base.apk
```

See [docs/API.md](docs/API.md) for complete API documentation.

---

## ⚙️ Configuration

Copy `env.example` to `.env` and customize:

```bash
cp env.example .env
```

Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_ORCHESTRATOR` | Enable multi-container mode | `false` |
| `AUTH_ENABLED` | Enable authentication | `true` |
| `ADMIN_USERNAME` | Admin username | `admin` |
| `ADMIN_PASSWORD` | Admin password | `apkextractor` |
| `RATE_LIMIT_REQUESTS` | Requests per minute | `10` |
| `EXTRACTION_TIMEOUT` | Max extraction time (s) | `300` |

---

## 📁 Project Structure

```
apk-extractor/
├── device-agent/           # APK extraction service
│   ├── device_agent.py     # Main agent code
│   ├── requirements.txt
│   └── pulls/              # Extracted APKs storage
│
├── web-backend/            # Web interface & API
│   ├── web_backend.py      # Backend server
│   ├── templates/          # HTML templates
│   ├── static/             # CSS/JS assets
│   ├── Dockerfile
│   └── requirements.txt
│
├── orchestrator/           # Load balancer (Phase 2)
│   ├── orchestrator.py     # Job queue & routing
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-android/         # Docker Android setup
│   ├── Dockerfile          # Android container
│   ├── docker-compose.yml
│   ├── device_agent.py     # Containerized agent
│   └── start.sh
│
├── emulator-setup/         # Emulator configuration
│   ├── create_avd.sh       # Create Android device
│   ├── start_emulator.sh   # Start emulator
│   └── setup_playstore.md  # Play Store setup guide
│
├── scripts/                # Utility scripts
│   ├── install_dependencies.sh
│   ├── check_health.sh
│   ├── cleanup.sh
│   └── docker_setup.sh
│
├── docs/                   # Documentation
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
│
├── docker-compose.yml      # Full stack compose
├── env.example             # Configuration template
└── README.md
```

---

## 🔒 Security

- **Authentication** - Basic auth with session management
- **Rate Limiting** - Prevent abuse (configurable)
- **Input Validation** - Package name sanitization
- **Path Security** - Prevent directory traversal
- **Audit Logging** - Complete operation trail
- **Network Isolation** - Containers on internal network

### Security Best Practices

1. Change default credentials in production
2. Use HTTPS with reverse proxy (nginx/traefik)
3. Restrict network access to authorized users
4. Regular cleanup of extracted APKs
5. Monitor audit logs

---

## 🐳 Docker Details

### Container Architecture

| Container | Port | Purpose |
|-----------|------|---------|
| web-backend | 8000 | Web UI & API |
| orchestrator | 8001 | Load balancer |
| android-1 | 5001 | APK extraction |
| android-2 | 5002 | APK extraction |
| android-3 | 5003 | APK extraction |

### Resource Requirements

Per Android container:
- **CPU**: 2 cores
- **RAM**: 2GB
- **Storage**: 10GB
- **KVM**: Recommended for performance

---

## 🧪 Testing

```bash
# Health check
./scripts/check_health.sh

# Test extraction
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -u admin:apkextractor \
  -d '{"package": "com.android.chrome"}'
```

---

## 📋 Troubleshooting

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| Emulator won't start | Check KVM: `sudo modprobe kvm` |
| Play Store not working | Ensure `google_apis_playstore` image |
| App not found | Install app manually first |
| Extraction timeout | Increase `EXTRACTION_TIMEOUT` |
| Docker build fails | Check Docker daemon running |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions.

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open Pull Request

---

## ⚠️ Legal Notice

This tool is intended for **authorized security research** and **enterprise security auditing** only.

- Only extract APKs you have legal rights to analyze
- Respect application licenses and terms of service
- Comply with your jurisdiction's laws regarding reverse engineering
- This tool does not bypass any DRM or copy protection

---

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: [docs/](docs/)
- **Email**: security@yourcompany.com
