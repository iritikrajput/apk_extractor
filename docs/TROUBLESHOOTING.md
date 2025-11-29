# APK Extractor - Troubleshooting Guide

Solutions for common issues with APK Extractor.

## Table of Contents

1. [Emulator Issues](#emulator-issues)
2. [Play Store Issues](#play-store-issues)
3. [Extraction Issues](#extraction-issues)
4. [Docker Issues](#docker-issues)
5. [Performance Issues](#performance-issues)
6. [Authentication Issues](#authentication-issues)
7. [Network Issues](#network-issues)

---

## Emulator Issues

### Emulator Won't Start

**Symptoms:**
- `emulator: command not found`
- Emulator starts but crashes immediately

**Solutions:**

1. **Check Android SDK path:**
   ```bash
   echo $ANDROID_HOME
   # Should output path like /home/user/Android/Sdk
   
   # If not set:
   export ANDROID_HOME=~/Android/Sdk
   export PATH=$PATH:$ANDROID_HOME/emulator
   ```

2. **Check KVM support (Linux):**
   ```bash
   # Check if KVM is available
   ls -la /dev/kvm
   
   # If not found, enable KVM:
   sudo modprobe kvm
   sudo modprobe kvm_intel  # or kvm_amd for AMD
   
   # Check permissions
   sudo chmod 666 /dev/kvm
   ```

3. **Verify AVD exists:**
   ```bash
   avdmanager list avd
   
   # If no AVD, create one:
   ./emulator-setup/create_avd.sh
   ```

4. **Try with different GPU mode:**
   ```bash
   emulator -avd playstore_device -gpu swiftshader_indirect
   ```

### Emulator Very Slow

**Solutions:**

1. **Enable hardware acceleration:**
   ```bash
   emulator -avd playstore_device -gpu host
   ```

2. **Allocate more RAM:**
   ```bash
   emulator -avd playstore_device -memory 4096
   ```

3. **Use x86_64 image (not ARM):**
   ```bash
   # Check current image
   cat ~/.android/avd/playstore_device.avd/config.ini | grep image
   
   # Should show x86_64
   ```

### ADB Not Connecting

**Symptoms:**
- `adb devices` shows empty list
- "device offline" or "unauthorized"

**Solutions:**

1. **Restart ADB server:**
   ```bash
   adb kill-server
   adb start-server
   adb devices
   ```

2. **Check emulator is running:**
   ```bash
   ps aux | grep emulator
   ```

3. **Connect manually:**
   ```bash
   adb connect localhost:5554
   ```

---

## Play Store Issues

### Play Store Not Available

**Symptoms:**
- No Play Store app in emulator
- "Play Store not supported" error

**Solutions:**

1. **Use correct system image:**
   ```bash
   # Must use google_apis_playstore image
   sdkmanager "system-images;android-30;google_apis_playstore;x86_64"
   
   # Recreate AVD
   ./emulator-setup/create_avd.sh
   ```

2. **Verify image type:**
   ```bash
   cat ~/.android/avd/playstore_device.avd/config.ini | grep image
   # Should contain "google_apis_playstore"
   ```

### Can't Sign Into Play Store

**Solutions:**

1. **Check internet connectivity in emulator:**
   ```bash
   adb shell ping -c 3 google.com
   ```

2. **Clear Play Store data:**
   - Settings > Apps > Google Play Store > Clear Data
   - Settings > Apps > Google Play Services > Clear Data
   - Restart emulator

3. **Try different Google account**

4. **Disable 2FA temporarily** (or use app password)

### App Won't Install from Play Store

**Solutions:**

1. **Check available storage:**
   ```bash
   adb shell df -h
   ```

2. **Clear Play Store cache:**
   - Settings > Apps > Play Store > Clear Cache

3. **Some apps require device certification:**
   - Banking apps, some streaming apps may not work
   - Check SafetyNet status (may fail on emulator)

---

## Extraction Issues

### "App Not Installed" Error

**Symptoms:**
- Error: "App not installed. Please install from Play Store first."

**Solutions:**

1. **Install app manually first:**
   - Open Play Store in emulator
   - Search and install the app
   - Then retry extraction

2. **Verify installation:**
   ```bash
   adb shell pm list packages | grep com.example.app
   ```

3. **Some apps block emulators:**
   - Try different emulator configuration
   - Some apps detect emulator and refuse to run

### Extraction Timeout

**Symptoms:**
- Error: "Extraction timeout"
- Large apps fail

**Solutions:**

1. **Increase timeout:**
   ```bash
   export EXTRACTION_TIMEOUT=600  # 10 minutes
   ```

2. **Check device isn't busy:**
   ```bash
   adb shell top -n 1
   ```

3. **Try extracting smaller apps first**

### Missing Split APKs

**Symptoms:**
- Only base.apk extracted, splits missing

**Solutions:**

1. **Check for all paths:**
   ```bash
   adb shell pm path com.example.app
   # Should list all APK files
   ```

2. **Verify storage permissions:**
   ```bash
   ls -la device-agent/pulls/
   ```

### Hash Verification Failed

**Solutions:**

1. **Re-extract the APK:**
   ```bash
   # Delete existing files
   rm -rf device-agent/pulls/com.example.app/
   
   # Extract again
   ```

2. **Check for disk errors:**
   ```bash
   df -h
   dmesg | tail
   ```

---

## Docker Issues

### Docker Build Fails

**Symptoms:**
- `docker compose build` fails
- Missing dependencies

**Solutions:**

1. **Check Docker is running:**
   ```bash
   docker info
   ```

2. **Clean Docker cache:**
   ```bash
   docker system prune -f
   docker builder prune -f
   docker compose build --no-cache
   ```

3. **Check network connectivity:**
   ```bash
   docker run --rm alpine ping -c 3 google.com
   ```

### Containers Keep Restarting

**Solutions:**

1. **Check logs:**
   ```bash
   docker compose logs android-1
   ```

2. **Verify resources:**
   ```bash
   docker stats
   # Check memory isn't exhausted
   ```

3. **Increase shared memory:**
   ```yaml
   # docker-compose.yml
   services:
     android-1:
       shm_size: 4gb
   ```

### Android Container Won't Boot

**Solutions:**

1. **Check KVM in container:**
   ```bash
   docker exec android-device-1 ls -la /dev/kvm
   ```

2. **Run privileged:**
   ```yaml
   # docker-compose.yml
   services:
     android-1:
       privileged: true
   ```

3. **Check logs for specific error:**
   ```bash
   docker logs android-device-1 2>&1 | tail -50
   ```

---

## Performance Issues

### Slow Extraction

**Solutions:**

1. **Use SSD storage**

2. **Increase container resources:**
   ```yaml
   services:
     android-1:
       deploy:
         resources:
           limits:
             cpus: '4'
             memory: 4G
   ```

3. **Enable KVM acceleration**

### High Memory Usage

**Solutions:**

1. **Limit containers:**
   ```yaml
   services:
     android-1:
       mem_limit: 2g
   ```

2. **Reduce number of containers**

3. **Enable swap:**
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### Queue Building Up

**Solutions:**

1. **Add more workers:**
   ```bash
   export WORKER_THREADS=5
   ```

2. **Add more containers**

3. **Check for slow/stuck extractions**

---

## Authentication Issues

### Can't Login

**Solutions:**

1. **Check credentials:**
   ```bash
   grep ADMIN_PASSWORD .env
   ```

2. **Clear browser cookies**

3. **Reset password:**
   ```bash
   # Edit .env
   ADMIN_PASSWORD=new-password
   # Restart services
   ```

### Session Expired

**Solutions:**

1. **Increase session timeout:**
   ```bash
   SESSION_TIMEOUT=7200  # 2 hours
   ```

2. **Re-login**

### Rate Limited

**Solutions:**

1. **Wait for limit to reset** (default: 60 seconds)

2. **Increase limit:**
   ```bash
   RATE_LIMIT_REQUESTS=20
   RATE_LIMIT_WINDOW=60
   ```

---

## Network Issues

### Can't Reach Backend

**Solutions:**

1. **Check service is running:**
   ```bash
   curl http://localhost:8000/api/health
   ```

2. **Check firewall:**
   ```bash
   sudo ufw status
   sudo iptables -L
   ```

3. **Check port binding:**
   ```bash
   netstat -tlnp | grep 8000
   ```

### Container Network Issues

**Solutions:**

1. **Check Docker network:**
   ```bash
   docker network ls
   docker network inspect apk-extractor_default
   ```

2. **Recreate networks:**
   ```bash
   docker compose down
   docker network prune
   docker compose up -d
   ```

---

## Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   # All logs
   docker compose logs -f
   
   # Specific service
   tail -f device-agent/logs/device_agent.log
   tail -f web-backend/logs/audit.log
   ```

2. **Run health check:**
   ```bash
   ./scripts/check_health.sh
   ```

3. **Gather diagnostics:**
   ```bash
   # System info
   uname -a
   docker version
   python3 --version
   adb version
   
   # Docker status
   docker compose ps
   docker stats --no-stream
   
   # Disk space
   df -h
   ```

4. **Open GitHub issue** with:
   - Error message
   - Steps to reproduce
   - Environment info
   - Relevant logs

