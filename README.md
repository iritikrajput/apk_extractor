# 📦 APK Extractor

**Automated APK extraction from Google Play Store**

A fully automated system that downloads official APK files from Google Play Store. Users simply enter a package name in the web interface, and the system automatically installs the app, extracts the APK, and provides download links.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **Auto-Install** | Automatically installs apps from Play Store |
| 🔐 **Auto-Login** | Automatically signs into Google Play Store |
| 📱 **Official APKs** | Extracts authentic APKs directly from Play Store |
| 🧹 **Auto-Cleanup** | Automatically uninstalls apps after download to free memory |
| 🔒 **SHA-256 Verification** | Hash verification for all extracted files |
| 🌐 **Web Interface** | Beautiful, easy-to-use web UI |
| ⚡ **24/7 Operation** | Emulator runs continuously without restart |
| 📦 **Split APK Support** | Handles modern Android App Bundles |

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Web Browser   │  ← User enters package name
│   (Frontend)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Web Backend    │  ← Flask server (port 8000)
│  (Flask:8000)   │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Device Agent   │  ← Manages Android emulator
│  (Flask:5001)   │
└────────┬────────┘
         │ ADB
         ▼
┌─────────────────┐
│    Android      │  ← Headless emulator with Play Store
│   Emulator      │
│  (Play Store)   │
└─────────────────┘
```

---

## 📋 Requirements

### Hardware
- **CPU**: 4+ cores (x86_64 with virtualization support)
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 50GB free space
- **KVM**: Required for emulator performance (Linux)

### Software
- **OS**: Linux (Ubuntu 20.04+, Debian 11+, Kali)
- **Python**: 3.8+
- **Android SDK**: With emulator and Play Store image
- **ADB**: Android Debug Bridge

---

## 🚀 Installation

### Step 1: Install System Dependencies

```bash
# Ubuntu/Debian/Kali
sudo apt update
sudo apt install -y python3 python3-pip openjdk-11-jdk wget unzip curl adb

# Enable KVM (for emulator performance)
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd for AMD CPUs
```

### Step 2: Install Android SDK

```bash
# Create SDK directory
mkdir -p ~/Android/Sdk
cd ~/Android/Sdk

# Download command-line tools
wget https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip
unzip commandlinetools-linux-*.zip
mkdir -p cmdline-tools/latest
mv cmdline-tools/* cmdline-tools/latest/ 2>/dev/null || true

# Set environment variables (add to ~/.bashrc or ~/.zshrc)
echo 'export ANDROID_HOME=~/Android/Sdk' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/emulator' >> ~/.bashrc
source ~/.bashrc

# Accept licenses
yes | sdkmanager --licenses

# Install required packages
sdkmanager "platform-tools" "emulator"
sdkmanager "system-images;android-34;google_apis_playstore;x86_64"
```

### Step 3: Create Android Virtual Device (AVD)

```bash
# Create AVD with Play Store
avdmanager create avd \
    -n playstore_device \
    -k "system-images;android-34;google_apis_playstore;x86_64" \
    -d "pixel_3a" \
    --force

# Verify AVD created
avdmanager list avd
```

### Step 4: Clone APK Extractor

```bash
# Clone repository
git clone https://github.com/your-repo/apk-extractor.git
cd apk-extractor

# Install Python dependencies
pip3 install -r device-agent/requirements.txt
pip3 install -r web-backend/requirements.txt
```

### Step 5: Configure Google Account

```bash
# Copy example config
cp env.example .env

# Edit with your Google credentials
nano .env
```

**Edit `.env` file:**
```ini
# Google Account for Play Store auto-login
GOOGLE_EMAIL=your-email@gmail.com
GOOGLE_PASSWORD=your-app-password

# Settings
AUTO_CLEANUP=true
CLEANUP_DELAY=300
```

> ⚠️ **Important**: If you have 2-Factor Authentication enabled on your Google account:
> 1. Go to https://myaccount.google.com/apppasswords
> 2. Create an "App Password"
> 3. Use that password in the `.env` file

### Step 6: First-Time Play Store Setup

The first time, you need to sign into Play Store manually:

```bash
# Start emulator with GUI
emulator -avd playstore_device

# In the emulator window:
# 1. Open Play Store app
# 2. Sign in with your Google account
# 3. Accept terms and conditions
# 4. Close the emulator
```

### Step 7: Start the Server

```bash
# Make start script executable
chmod +x start_server.sh

# Start all services
./start_server.sh
```

---

## 🖥️ Usage

### Access Web Interface

Open in your browser:
- **Local**: http://localhost:8000
- **Network**: http://YOUR-SERVER-IP:8000

### Extract an APK

1. Enter the **package name** (e.g., `com.whatsapp`)
2. Click **"Extract APK"**
3. Wait for automatic installation and extraction
4. Click **"Download"** to get the APK files

### Find Package Names

Package names can be found:
- In Play Store URL: `https://play.google.com/store/apps/details?id=com.whatsapp`
- The package name is: `com.whatsapp`

### Example Package Names

| App | Package Name |
|-----|--------------|
| WhatsApp | `com.whatsapp` |
| Instagram | `com.instagram.android` |
| Twitter/X | `com.twitter.android` |
| Spotify | `com.spotify.music` |
| Netflix | `com.netflix.mediaclient` |
| TikTok | `com.zhiliaoapp.musically` |

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_EMAIL` | - | Google account email |
| `GOOGLE_PASSWORD` | - | Google account password (or app password) |
| `AUTO_CLEANUP` | `true` | Auto-uninstall apps after download |
| `CLEANUP_DELAY` | `300` | Seconds before auto-cleanup (5 min) |
| `DEVICE_ID` | `emulator-5554` | ADB device identifier |
| `EXTRACTION_TIMEOUT` | `300` | Max extraction time (seconds) |
| `INSTALL_TIMEOUT` | `180` | Max install time (seconds) |

### Files

| File | Purpose |
|------|---------|
| `.env` | Configuration (credentials, settings) |
| `start_server.sh` | Start all services |
| `device-agent/pulls/` | Extracted APK storage |
| `device-agent/logs/` | Device agent logs |
| `web-backend/logs/` | Web backend logs |

---

## 📁 Project Structure

```
apk-extractor/
├── device-agent/           # APK extraction service
│   ├── device_agent.py     # Main agent (port 5001)
│   ├── requirements.txt
│   ├── pulls/              # Extracted APKs
│   └── logs/
│
├── web-backend/            # Web interface
│   ├── web_backend.py      # Web server (port 8000)
│   ├── templates/
│   │   └── index.html      # Web UI
│   ├── requirements.txt
│   └── logs/
│
├── emulator-setup/         # Emulator configuration
│   ├── create_avd.sh
│   └── start_emulator.sh
│
├── scripts/                # Utility scripts
│   ├── install_dependencies.sh
│   ├── check_health.sh
│   └── cleanup.sh
│
├── start_server.sh         # Main startup script
├── .env                    # Configuration
├── env.example             # Example config
└── README.md
```

---

## 🔧 API Reference

### Health Check
```bash
GET /api/health
```

### Extract APK
```bash
POST /api/extract
Content-Type: application/json

{"package": "com.whatsapp"}
```

### Download APK
```bash
GET /api/download/{package}/{filename}
```

### List Extracted Packages
```bash
GET /api/packages
```

---

## 🛠️ Management

### Start Services
```bash
./start_server.sh
```

### Stop Services
```bash
pkill -f "device_agent.py"
pkill -f "web_backend.py"
```

### Stop Emulator
```bash
adb emu kill
```

### Check Status
```bash
./scripts/check_health.sh
```

### View Logs
```bash
# Device Agent
tail -f device-agent/logs/device_agent.log

# Web Backend
tail -f web-backend/logs/web_backend.log
```

### Manual Cleanup
```bash
./scripts/cleanup.sh
```

---

## 🐛 Troubleshooting

### Emulator Won't Start

```bash
# Check KVM support
ls -la /dev/kvm

# If not found, enable KVM:
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Check permissions
sudo chmod 666 /dev/kvm
```

### Play Store Not Signed In

1. Start emulator with GUI:
   ```bash
   emulator -avd playstore_device
   ```
2. Open Play Store and sign in manually
3. Restart the server

### "App Not Found" Error

- Verify the package name is correct
- Check if the app is available in your region
- Some apps are not available on emulators

### Extraction Timeout

```bash
# Increase timeout in .env
EXTRACTION_TIMEOUT=600
INSTALL_TIMEOUT=300
```

### Services Not Starting

```bash
# Check if ports are in use
netstat -tlnp | grep -E "5001|8000"

# Kill existing processes
pkill -f "device_agent.py"
pkill -f "web_backend.py"

# Restart
./start_server.sh
```

### ADB Connection Issues

```bash
# Restart ADB
adb kill-server
adb start-server
adb devices
```

---

## 🔒 Security Notes

1. **Use dedicated Google account** - Don't use your personal account
2. **App passwords** - Use app-specific passwords with 2FA
3. **Network security** - Don't expose ports 5001/8000 to public internet without authentication
4. **Firewall** - Restrict access to trusted IPs only
5. **Legal** - Only extract APKs for apps you have rights to analyze

---

## 🌐 Production Deployment

### Using Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name apk.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

### Running as Systemd Service

```bash
# /etc/systemd/system/apk-extractor.service
[Unit]
Description=APK Extractor
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/apk-extractor
ExecStart=/path/to/apk-extractor/start_server.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable apk-extractor
sudo systemctl start apk-extractor
```

---

## 📊 How It Works (Flow)

```
1. User enters: com.whatsapp
          ↓
2. Web Backend receives request
          ↓
3. Device Agent checks if app installed
          ↓
4. If not installed:
   - Opens Play Store on emulator
   - Clicks "Install" button automatically
   - Waits for installation to complete
          ↓
5. Extracts APK files using ADB:
   adb shell pm path com.whatsapp
   adb pull /data/app/.../base.apk
          ↓
6. Calculates SHA-256 hash
          ↓
7. Returns download links to user
          ↓
8. User downloads APK files
          ↓
9. After 5 minutes: Auto-cleanup
   - Uninstalls app from emulator
   - Deletes extracted files
```

---

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## ⚠️ Disclaimer

This tool is intended for **legitimate security research** and **authorized application analysis** only. 

- Only extract APKs for apps you have legal rights to analyze
- Respect application licenses and terms of service
- Comply with your jurisdiction's laws
- This tool does not bypass DRM or copy protection

---

## 📞 Support

- **Issues**: Open a GitHub issue
- **Documentation**: See `/docs` folder
- **Logs**: Check `logs/` directories for debugging
