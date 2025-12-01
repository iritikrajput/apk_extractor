# APK Extractor - Deployment Guide

Complete guide for deploying APK Extractor in various environments.

## Table of Contents

1. [Requirements](#requirements)
2. [Phase 1: Single Device](#phase-1-single-device)
3. [Phase 2: Docker Multi-Container](#phase-2-docker-multi-container)
4. [Production Deployment](#production-deployment)
5. [Scaling](#scaling)
6. [Monitoring](#monitoring)

---

## Requirements

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 200+ GB SSD |
| KVM Support | Yes (for performance) | Yes |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.8+ | Backend services |
| Android SDK | Latest | Emulator (Phase 1) |
| Docker | 20.10+ | Containers (Phase 2) |
| Docker Compose | 1.29+ | Container orchestration |

---

## Phase 1: Single Device

Best for development, testing, and low-volume production.

### Step 1: Install Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip openjdk-11-jdk curl wget unzip

# Install Android SDK
mkdir -p ~/Android/Sdk
cd ~/Android/Sdk

# Download command-line tools
wget https://dl.google.com/android/repository/commandlinetools-linux-latest.zip
unzip commandlinetools-linux-latest.zip -d cmdline-tools
mv cmdline-tools/cmdline-tools cmdline-tools/latest

# Set environment
echo 'export ANDROID_HOME=~/Android/Sdk' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/emulator' >> ~/.bashrc
source ~/.bashrc

# Accept licenses
yes | sdkmanager --licenses
```

### Step 2: Create Android Emulator

```bash
# Run installation script
cd apk-extractor
./scripts/install_dependencies.sh

# Create AVD
./emulator-setup/create_avd.sh

# First-time setup (with GUI)
emulator -avd Pixel_8

# In emulator:
# 1. Open Play Store
# 2. Sign in with Google account
# 3. Accept terms
# 4. Close emulator
```

### Step 3: Configure

```bash
# Copy configuration template
cp env.example .env

# Edit configuration
nano .env

# Key settings:
# USE_ORCHESTRATOR=false
# AUTH_ENABLED=true
# ADMIN_PASSWORD=your-secure-password
```

### Step 4: Start Services

```bash
# Terminal 1: Start emulator (headless)
./emulator-setup/start_emulator.sh

# Terminal 2: Start device agent
cd device-agent
python3 device_agent.py

# Terminal 3: Start web backend
cd web-backend
python3 web_backend.py

# Access: http://localhost:8000
```

### Step 5: Create Systemd Services (Optional)

```bash
# /etc/systemd/system/apk-device-agent.service
[Unit]
Description=APK Extractor Device Agent
After=network.target

[Service]
Type=simple
User=apkextractor
WorkingDirectory=/opt/apk-extractor/device-agent
ExecStart=/usr/bin/python3 device_agent.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## Phase 2: Docker Multi-Container

Best for production, high availability, and scaling.

### Step 1: Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Verify
docker --version
docker compose version
```

### Step 2: Enable KVM (for Performance)

```bash
# Check KVM support
egrep -c '(vmx|svm)' /proc/cpuinfo

# Load KVM module
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Verify
ls -la /dev/kvm

# Make persistent
echo "kvm" | sudo tee -a /etc/modules
```

### Step 3: Configure

```bash
# Copy and edit configuration
cp env.example .env
nano .env

# Key settings:
# USE_ORCHESTRATOR=true
# CONTAINER_URLS=http://android-1:5001,http://android-2:5001,http://android-3:5001
# ADMIN_PASSWORD=your-secure-password
```

### Step 4: Build and Start

```bash
# Build containers
docker compose build

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Step 5: First-Time Play Store Setup

Each Android container needs Play Store setup:

```bash
# Connect to container's VNC (if enabled)
# Or use adb:

# Container 1
docker exec -it android-device-1 adb shell

# Open Play Store
am start -a android.intent.action.VIEW -d "market://details?id=com.android.chrome"
```

---

## Production Deployment

### Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/apk-extractor
server {
    listen 80;
    server_name apk.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name apk.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/apk.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/apk.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=apk:10m rate=10r/s;
    limit_req zone=apk burst=20 nodelay;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long extractions
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }

    # Large file downloads
    location /api/download/ {
        proxy_pass http://localhost:8000;
        proxy_buffering off;
        proxy_read_timeout 600s;
    }
}
```

### SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d apk.yourdomain.com
```

### Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Don't expose internal ports (5001, 8001) externally
```

### Backup

```bash
# Backup extracted APKs
rsync -avz /opt/apk-extractor/pulls/ /backup/apks/

# Backup configuration
cp /opt/apk-extractor/.env /backup/config/

# Backup AVD (Phase 1)
tar -czvf avd-backup.tar.gz ~/.android/avd/
```

---

## Scaling

### Horizontal Scaling (More Containers)

```yaml
# docker-compose.override.yml
services:
  android-4:
    build: ./docker-android
    container_name: android-device-4
    privileged: true
    ports:
      - "5004:5001"
    environment:
      - DEVICE=emulator-5554
    volumes:
      - apk-storage:/app/pulls
    shm_size: 2gb

  android-5:
    build: ./docker-android
    # ... same configuration
```

Update orchestrator:
```bash
CONTAINER_URLS=http://android-1:5001,...,http://android-5:5001
```

### Vertical Scaling (More Resources)

```yaml
# docker-compose.override.yml
services:
  android-1:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
```

### Load Balancer (Multiple Orchestrators)

For very high scale, use external load balancer (HAProxy, Nginx) in front of multiple orchestrator instances.

---

## Monitoring

### Health Checks

```bash
# Script for monitoring
#!/bin/bash
curl -sf http://localhost:8000/api/health || alert "Web backend down"
curl -sf http://localhost:8001/health || alert "Orchestrator down"

# Check containers
docker ps --filter "health=unhealthy" --format "{{.Names}}" | while read name; do
    alert "Container unhealthy: $name"
done
```

### Logging

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f web-backend

# Log rotation (Docker daemon config)
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Metrics (Prometheus - Optional)

Add to each service for metrics export:
- `/metrics` endpoint with Prometheus format
- Use `prometheus_flask_exporter` library

### Alerts

Set up alerts for:
- Service health check failures
- High queue size (> 10 jobs)
- Low disk space (< 20% free)
- Container restarts
- Authentication failures

---

## Maintenance

### Updates

```bash
# Pull latest code
git pull

# Rebuild containers
docker compose build --no-cache

# Rolling restart
docker compose up -d --no-deps web-backend
docker compose up -d --no-deps orchestrator
# Restart Android containers one at a time
```

### Cleanup

```bash
# Remove old APKs (automated with cron)
./scripts/cleanup.sh --days 7

# Docker cleanup
docker system prune -f
docker volume prune -f
```

### Cron Jobs

```bash
# /etc/cron.d/apk-extractor
# Cleanup old files daily
0 3 * * * root /opt/apk-extractor/scripts/cleanup.sh --days 7

# Health check every 5 minutes
*/5 * * * * root /opt/apk-extractor/scripts/check_health.sh >> /var/log/apk-health.log 2>&1
```

