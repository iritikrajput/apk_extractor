"""
APK Extractor - Docker Device Agent
Containerized APK extraction service

This is the containerized version of the device agent
optimized for running inside Docker Android containers.
"""

from flask import Flask, request, jsonify, send_file
import subprocess
import os
import time
import hashlib
import re
import logging
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

app = Flask(__name__)

# Directories
DATA_DIR = os.getenv("APK_STORAGE_PATH", "/app/pulls")
LOG_DIR = os.getenv("LOG_PATH", "/app/logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ADB Configuration
DEVICE_ID = os.getenv("DEVICE", "emulator-5554")
ADB_TIMEOUT = int(os.getenv("ADB_TIMEOUT", "60"))
EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# Container identification
CONTAINER_ID = os.getenv("HOSTNAME", "unknown")

# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f'device_agent_{CONTAINER_ID}.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('device_agent')

# ============================================
# HELPER FUNCTIONS
# ============================================

def validate_package_name(package_name):
    """Validate Android package name format"""
    if not package_name:
        return False, "Package name is required"
    
    package_name = package_name.strip()
    
    if len(package_name) > 256:
        return False, "Package name too long"
    
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
    if not re.match(pattern, package_name):
        return False, "Invalid package name format"
    
    return True, package_name


def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    sanitized = sanitized.replace('..', '_')
    return sanitized


def run_adb(command, timeout=None, retries=None):
    """Execute ADB command with retry logic"""
    if timeout is None:
        timeout = ADB_TIMEOUT
    if retries is None:
        retries = MAX_RETRIES
    
    cmd = ["adb", "-s", DEVICE_ID] + command
    last_error = None
    
    for attempt in range(retries):
        try:
            logger.debug(f"ADB command (attempt {attempt + 1}): {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                last_error = f"ADB Error: {result.stderr.strip()}"
                logger.warning(f"ADB failed (attempt {attempt + 1}): {last_error}")
                
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise Exception(last_error)
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            last_error = f"ADB timeout after {timeout}s"
            logger.warning(f"ADB timeout (attempt {attempt + 1})")
            
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
                
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
    
    raise Exception(last_error or "ADB command failed")


def wait_for_device(timeout=None):
    """Wait for device to be ready"""
    if timeout is None:
        timeout = EXTRACTION_TIMEOUT
    
    logger.info(f"Waiting for device {DEVICE_ID}...")
    
    try:
        subprocess.run(
            ["adb", "-s", DEVICE_ID, "wait-for-device"],
            timeout=timeout,
            check=True
        )
        
        # Wait for boot
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                output = run_adb(["shell", "getprop", "sys.boot_completed"], timeout=10, retries=1)
                if "1" in output:
                    logger.info(f"Device {DEVICE_ID} ready")
                    time.sleep(3)
                    return True
            except Exception:
                pass
            time.sleep(3)
        
        raise Exception("Device boot timeout")
        
    except subprocess.TimeoutExpired:
        raise Exception(f"Device not ready after {timeout}s")


def check_app_installed(package_name):
    """Check if app is installed"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name])
        return f"package:{package_name}" in output
    except Exception:
        return False


def get_apk_paths(package_name):
    """Get all APK paths for a package"""
    output = run_adb(["shell", "pm", "path", package_name])
    paths = []
    
    for line in output.splitlines():
        if line.startswith("package:"):
            path = line.split(":", 1)[1].strip()
            if path:
                paths.append(path)
    
    logger.info(f"Found {len(paths)} APK(s) for {package_name}")
    return paths


def calculate_hash(filepath):
    """Calculate SHA-256 hash"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def format_bytes(size):
    """Format bytes to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def open_play_store(package_name):
    """Open Play Store for app"""
    try:
        run_adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"market://details?id={package_name}"
        ])
        time.sleep(10)
        return True
    except Exception as e:
        logger.error(f"Play Store error: {e}")
        return False


# ============================================
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    try:
        output = run_adb(["shell", "getprop", "sys.boot_completed"], retries=1, timeout=10)
        boot_completed = "1" in output
        
        return jsonify({
            "status": "healthy" if boot_completed else "booting",
            "device": DEVICE_ID,
            "container_id": CONTAINER_ID,
            "timestamp": datetime.utcnow().isoformat()
        }), 200 if boot_completed else 503
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "container_id": CONTAINER_ID
        }), 503


@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    """Extract APK files"""
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": result}), 400
    
    package = result
    logger.info(f"Extraction request: {package}")
    
    try:
        wait_for_device()
        
        # Check if installed
        if not check_app_installed(package):
            open_play_store(package)
            time.sleep(3)
            
            if not check_app_installed(package):
                return jsonify({
                    "error": "App not installed. Manual installation required.",
                    "package": package
                }), 404
        
        # Get APK paths
        apk_paths = get_apk_paths(package)
        if not apk_paths:
            return jsonify({"error": "No APK found"}), 404
        
        # Create directory
        package_dir = os.path.join(DATA_DIR, sanitize_filename(package))
        os.makedirs(package_dir, exist_ok=True)
        
        file_info = []
        
        # Pull APKs
        for i, apk_path in enumerate(apk_paths):
            try:
                if i == 0:
                    filename = "base.apk"
                else:
                    original_name = os.path.basename(apk_path)
                    if "split" in original_name or "config" in original_name:
                        filename = sanitize_filename(original_name)
                    else:
                        filename = f"split_{i}.apk"
                
                local_path = os.path.join(package_dir, filename)
                
                logger.info(f"Pulling {apk_path}")
                run_adb(["pull", apk_path, local_path], timeout=EXTRACTION_TIMEOUT)
                
                if os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                    file_hash = calculate_hash(local_path)
                    
                    file_info.append({
                        "filename": filename,
                        "path": f"{package}/{filename}",
                        "size": file_size,
                        "size_human": format_bytes(file_size),
                        "hash": file_hash,
                        "hash_algorithm": "SHA-256"
                    })
                    
            except Exception as e:
                logger.error(f"Failed to pull {apk_path}: {e}")
        
        if not file_info:
            return jsonify({"error": "Failed to extract APKs"}), 500
        
        return jsonify({
            "status": "completed",
            "package": package,
            "files": file_info,
            "total_files": len(file_info),
            "total_size": sum(f["size"] for f in file_info),
            "total_size_human": format_bytes(sum(f["size"] for f in file_info)),
            "container": CONTAINER_ID
        }), 200
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download_apk/<package>/<filename>")
def download_apk(package, filename):
    """Download APK file"""
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    filename = sanitize_filename(filename)
    
    if not filename.endswith('.apk'):
        return jsonify({"error": "Invalid filename"}), 400
    
    full_path = os.path.join(DATA_DIR, package, filename)
    
    # Security check
    real_path = os.path.realpath(full_path)
    real_data_dir = os.path.realpath(DATA_DIR)
    
    if not real_path.startswith(real_data_dir):
        return jsonify({"error": "Invalid path"}), 400
    
    if os.path.exists(full_path):
        return send_file(
            full_path,
            as_attachment=True,
            download_name=f"{package}_{filename}",
            mimetype='application/vnd.android.package-archive'
        )
    else:
        return jsonify({"error": "File not found"}), 404


@app.route("/list_packages", methods=["GET"])
def list_packages():
    """List extracted packages"""
    packages = []
    
    if os.path.exists(DATA_DIR):
        for pkg_name in os.listdir(DATA_DIR):
            pkg_path = os.path.join(DATA_DIR, pkg_name)
            
            if os.path.isdir(pkg_path):
                files = []
                total_size = 0
                
                for filename in os.listdir(pkg_path):
                    if filename.endswith('.apk'):
                        file_path = os.path.join(pkg_path, filename)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        files.append({
                            "filename": filename,
                            "size": file_size,
                            "size_human": format_bytes(file_size)
                        })
                
                if files:
                    packages.append({
                        "package": pkg_name,
                        "files": files,
                        "total_size": total_size,
                        "total_size_human": format_bytes(total_size)
                    })
    
    return jsonify({"packages": packages, "total_packages": len(packages)}), 200


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("APK Extractor - Docker Device Agent")
    print("=" * 50)
    print(f"Container: {CONTAINER_ID}")
    print(f"Device: {DEVICE_ID}")
    print(f"Storage: {DATA_DIR}")
    print("=" * 50)
    print("Starting server on port 5001...")
    
    app.run(host="0.0.0.0", port=5001)
