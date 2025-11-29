"""
APK Extractor - Device Agent
Manages APK extraction from Android device/emulator via ADB

This module provides REST API endpoints for:
- Extracting APKs from installed apps
- Health checking device connectivity
- Downloading extracted APK files
"""

from flask import Flask, request, jsonify, send_file
import subprocess
import os
import time
import hashlib
import re
import logging
from datetime import datetime
from functools import wraps

# ============================================
# CONFIGURATION
# ============================================

app = Flask(__name__)

# Directories
DATA_DIR = os.getenv("APK_STORAGE_PATH", "./pulls")
LOG_DIR = os.getenv("LOG_PATH", "./logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ADB Configuration
DEVICE_ID = os.getenv("DEVICE_ID", "emulator-5554")
ADB_TIMEOUT = int(os.getenv("ADB_TIMEOUT", "60"))
EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'device_agent.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('device_agent')

# Audit logger for compliance
audit_logger = logging.getLogger('audit')
audit_handler = logging.FileHandler(os.path.join(LOG_DIR, 'audit.log'))
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

# ============================================
# HELPER FUNCTIONS
# ============================================

def audit_log(action, package=None, result=None, details=None):
    """Log audit trail for compliance"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "package": package,
        "result": result,
        "details": details,
        "device": DEVICE_ID
    }
    audit_logger.info(str(log_entry))


def validate_package_name(package_name):
    """
    Validate Android package name format
    Valid: com.example.app, com.example.app123, org.test_app
    Invalid: anything with spaces, special chars, or invalid format
    """
    if not package_name:
        return False, "Package name is required"
    
    # Remove whitespace
    package_name = package_name.strip()
    
    # Check length
    if len(package_name) > 256:
        return False, "Package name too long (max 256 characters)"
    
    # Android package name pattern
    # Must start with letter, contain letters/numbers/underscores, separated by dots
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
    
    if not re.match(pattern, package_name):
        return False, "Invalid package name format. Expected: com.example.app"
    
    return True, package_name


def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal attacks"""
    # Remove any path separators and special characters
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Prevent path traversal
    sanitized = sanitized.replace('..', '_')
    return sanitized


def run_adb(command, timeout=None, retries=None):
    """
    Execute ADB command with retry logic
    
    Args:
        command: List of command arguments
        timeout: Command timeout in seconds
        retries: Number of retry attempts
    
    Returns:
        Command stdout on success
    
    Raises:
        Exception on failure after all retries
    """
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
                logger.warning(f"ADB command failed (attempt {attempt + 1}): {last_error}")
                
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise Exception(last_error)
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            last_error = f"ADB command timed out after {timeout}s"
            logger.warning(f"ADB timeout (attempt {attempt + 1}): {last_error}")
            
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"ADB error (attempt {attempt + 1}): {last_error}")
            
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
    
    raise Exception(last_error or "ADB command failed")


def wait_for_device(timeout=None):
    """Wait for device to be ready and fully booted"""
    if timeout is None:
        timeout = EXTRACTION_TIMEOUT
    
    logger.info(f"Waiting for device {DEVICE_ID}...")
    
    try:
        # Wait for device to appear
        subprocess.run(
            ["adb", "-s", DEVICE_ID, "wait-for-device"],
            timeout=timeout,
            check=True
        )
        
        # Wait for boot to complete
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                output = run_adb(["shell", "getprop", "sys.boot_completed"], timeout=10, retries=1)
                if "1" in output:
                    logger.info(f"Device {DEVICE_ID} is ready")
                    time.sleep(2)  # Additional stabilization
                    return True
            except Exception:
                pass
            time.sleep(3)
        
        raise Exception("Device boot timeout")
        
    except subprocess.TimeoutExpired:
        raise Exception(f"Device not ready after {timeout}s")


def check_app_installed(package_name):
    """Check if app is installed on device"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name])
        installed = f"package:{package_name}" in output
        logger.debug(f"Package {package_name} installed: {installed}")
        return installed
    except Exception as e:
        logger.warning(f"Failed to check if {package_name} is installed: {e}")
        return False


def get_apk_paths(package_name):
    """
    Get all APK file paths for a package
    Modern apps use split APKs (Android App Bundles)
    """
    output = run_adb(["shell", "pm", "path", package_name])
    paths = []
    
    for line in output.splitlines():
        if line.startswith("package:"):
            path = line.split(":", 1)[1].strip()
            if path:
                paths.append(path)
    
    logger.info(f"Found {len(paths)} APK file(s) for {package_name}")
    return paths


def calculate_hash(filepath):
    """Calculate SHA-256 hash of file for integrity verification"""
    sha256_hash = hashlib.sha256()
    
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def open_play_store(package_name):
    """
    Open Play Store page for an app
    Note: Actual installation requires user interaction or Appium automation
    """
    try:
        logger.info(f"Opening Play Store for {package_name}")
        run_adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"market://details?id={package_name}"
        ])
        time.sleep(5)
        return True
    except Exception as e:
        logger.error(f"Failed to open Play Store: {e}")
        return False


def get_device_info():
    """Get device information for health checks"""
    try:
        info = {}
        
        # Android version
        info['android_version'] = run_adb(
            ["shell", "getprop", "ro.build.version.release"]
        ).strip()
        
        # Device model
        info['model'] = run_adb(
            ["shell", "getprop", "ro.product.model"]
        ).strip()
        
        # Boot completed
        boot_output = run_adb(
            ["shell", "getprop", "sys.boot_completed"]
        ).strip()
        info['boot_completed'] = boot_output == "1"
        
        return info
    except Exception as e:
        logger.error(f"Failed to get device info: {e}")
        return {"error": str(e)}


# ============================================
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint
    Returns device status and connectivity information
    """
    try:
        # Check device connection
        output = run_adb(["devices"], retries=1, timeout=10)
        devices = [
            line for line in output.splitlines() 
            if "device" in line and "List" not in line
        ]
        
        # Get device info
        device_info = get_device_info()
        
        status = "healthy" if devices and device_info.get('boot_completed') else "unhealthy"
        
        return jsonify({
            "status": status,
            "device_id": DEVICE_ID,
            "devices_count": len(devices),
            "device_info": device_info,
            "timestamp": datetime.utcnow().isoformat()
        }), 200 if status == "healthy" else 503
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "device_id": DEVICE_ID,
            "timestamp": datetime.utcnow().isoformat()
        }), 503


@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    """
    Extract APK files for a given package
    
    Request Body:
        {"package": "com.example.app"}
    
    Returns:
        - 200: Extraction successful with file info
        - 400: Invalid request
        - 404: App not found/installed
        - 500: Extraction failed
    """
    # Get and validate package name
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    valid, result = validate_package_name(package)
    if not valid:
        audit_log("extract_attempt", package, "failed", f"Invalid package: {result}")
        return jsonify({"error": result}), 400
    
    package = result  # Sanitized package name
    
    logger.info(f"Extraction request for package: {package}")
    audit_log("extract_start", package, "in_progress")
    
    try:
        # Wait for device
        wait_for_device()
        
        # Check if app is installed
        if not check_app_installed(package):
            # Attempt to open Play Store (user must install manually)
            open_play_store(package)
            
            # Wait a moment and check again
            time.sleep(3)
            
            if not check_app_installed(package):
                audit_log("extract_attempt", package, "failed", "App not installed")
                return jsonify({
                    "error": "App not installed. Please install from Play Store first.",
                    "package": package,
                    "help": "Install the app manually, then retry extraction."
                }), 404
        
        # Get APK paths
        apk_paths = get_apk_paths(package)
        
        if not apk_paths:
            audit_log("extract_attempt", package, "failed", "No APK paths found")
            return jsonify({
                "error": "No APK files found for package",
                "package": package
            }), 404
        
        # Create package directory
        package_dir = os.path.join(DATA_DIR, sanitize_filename(package))
        os.makedirs(package_dir, exist_ok=True)
        
        file_info = []
        extraction_errors = []
        
        # Pull all APK files
        for i, apk_path in enumerate(apk_paths):
            try:
                # Generate filename
                if i == 0:
                    filename = "base.apk"
                else:
                    # Try to extract meaningful name from path
                    original_name = os.path.basename(apk_path)
                    if "split" in original_name or "config" in original_name:
                        filename = sanitize_filename(original_name)
                    else:
                        filename = f"split_{i}.apk"
                
                local_path = os.path.join(package_dir, filename)
                
                logger.info(f"Pulling {apk_path} -> {local_path}")
                
                # Pull APK with extended timeout for large files
                run_adb(
                    ["pull", apk_path, local_path],
                    timeout=EXTRACTION_TIMEOUT
                )
                
                # Verify file exists and has content
                if not os.path.exists(local_path):
                    raise Exception("Pull succeeded but file not found")
                
                file_size = os.path.getsize(local_path)
                if file_size == 0:
                    raise Exception("Pull succeeded but file is empty")
                
                # Calculate hash
                file_hash = calculate_hash(local_path)
                
                file_info.append({
                    "filename": filename,
                    "path": f"{package}/{filename}",
                    "size": file_size,
                    "size_human": format_bytes(file_size),
                    "hash": file_hash,
                    "hash_algorithm": "SHA-256"
                })
                
                logger.info(f"Successfully extracted {filename} ({format_bytes(file_size)})")
                
            except Exception as e:
                error_msg = f"Failed to extract {apk_path}: {str(e)}"
                logger.error(error_msg)
                extraction_errors.append(error_msg)
        
        if not file_info:
            audit_log("extract_attempt", package, "failed", "All extractions failed")
            return jsonify({
                "error": "Failed to extract any APK files",
                "errors": extraction_errors,
                "package": package
            }), 500
        
        result = {
            "status": "completed",
            "package": package,
            "files": file_info,
            "total_files": len(file_info),
            "total_size": sum(f["size"] for f in file_info),
            "total_size_human": format_bytes(sum(f["size"] for f in file_info)),
            "extraction_time": datetime.utcnow().isoformat(),
            "device": DEVICE_ID
        }
        
        if extraction_errors:
            result["warnings"] = extraction_errors
        
        audit_log("extract_complete", package, "success", f"{len(file_info)} files extracted")
        logger.info(f"Extraction complete for {package}: {len(file_info)} file(s)")
        
        return jsonify(result), 200
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Extraction failed for {package}: {error_msg}")
        audit_log("extract_attempt", package, "failed", error_msg)
        
        return jsonify({
            "error": error_msg,
            "package": package
        }), 500


@app.route("/download_apk/<package>/<filename>")
def download_apk(package, filename):
    """
    Download a specific APK file
    
    URL Parameters:
        package: Package name
        filename: APK filename (base.apk, split_1.apk, etc.)
    
    Returns:
        - 200: APK file download
        - 400: Invalid parameters
        - 404: File not found
    """
    # Validate and sanitize inputs
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    filename = sanitize_filename(filename)
    
    # Ensure filename ends with .apk
    if not filename.endswith('.apk'):
        return jsonify({"error": "Invalid filename"}), 400
    
    full_path = os.path.join(DATA_DIR, package, filename)
    
    # Security: Ensure path is within DATA_DIR
    real_path = os.path.realpath(full_path)
    real_data_dir = os.path.realpath(DATA_DIR)
    
    if not real_path.startswith(real_data_dir):
        logger.warning(f"Path traversal attempt: {full_path}")
        return jsonify({"error": "Invalid path"}), 400
    
    if os.path.exists(full_path):
        audit_log("download", package, "success", filename)
        logger.info(f"Download: {package}/{filename}")
        
        return send_file(
            full_path,
            as_attachment=True,
            download_name=f"{package}_{filename}",
            mimetype='application/vnd.android.package-archive'
        )
    else:
        audit_log("download", package, "failed", f"File not found: {filename}")
        return jsonify({"error": "File not found"}), 404


@app.route("/list_packages", methods=["GET"])
def list_packages():
    """
    List all extracted packages available for download
    """
    packages = []
    
    if os.path.exists(DATA_DIR):
        for package_name in os.listdir(DATA_DIR):
            package_path = os.path.join(DATA_DIR, package_name)
            
            if os.path.isdir(package_path):
                files = []
                total_size = 0
                
                for filename in os.listdir(package_path):
                    if filename.endswith('.apk'):
                        file_path = os.path.join(package_path, filename)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        
                        files.append({
                            "filename": filename,
                            "size": file_size,
                            "size_human": format_bytes(file_size)
                        })
                
                if files:
                    packages.append({
                        "package": package_name,
                        "files": files,
                        "total_size": total_size,
                        "total_size_human": format_bytes(total_size)
                    })
    
    return jsonify({
        "packages": packages,
        "total_packages": len(packages)
    }), 200


@app.route("/delete_package/<package>", methods=["DELETE"])
def delete_package(package):
    """
    Delete extracted APK files for a package
    """
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    package_path = os.path.join(DATA_DIR, package)
    
    # Security check
    real_path = os.path.realpath(package_path)
    real_data_dir = os.path.realpath(DATA_DIR)
    
    if not real_path.startswith(real_data_dir):
        return jsonify({"error": "Invalid path"}), 400
    
    if os.path.exists(package_path):
        import shutil
        shutil.rmtree(package_path)
        audit_log("delete", package, "success")
        logger.info(f"Deleted package: {package}")
        return jsonify({"message": f"Package {package} deleted"}), 200
    else:
        return jsonify({"error": "Package not found"}), 404


def format_bytes(size):
    """Format bytes to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("APK Extractor - Device Agent")
    print("=" * 50)
    print(f"Device ID: {DEVICE_ID}")
    print(f"Storage: {DATA_DIR}")
    print(f"Logs: {LOG_DIR}")
    print("=" * 50)
    print("Checking device connection...")
    
    try:
        output = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(output.stdout)
    except Exception as e:
        print(f"Warning: Could not check ADB: {e}")
    
    print("Starting server on port 5001...")
    app.run(host="0.0.0.0", port=5001)
