"""
APK Extractor - Automated Device Agent
Fully automated APK extraction with auto-install and Google login

Features:
- Auto-login to Google Play Store
- Auto-install apps from Play Store
- Extract APK after installation
- Auto-uninstall after download
- 24/7 headless operation
"""

from flask import Flask, request, jsonify, send_file, after_this_request
import subprocess
import os
import time
import hashlib
import re
import logging
import threading
from datetime import datetime, timezone

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
INSTALL_TIMEOUT = int(os.getenv("INSTALL_TIMEOUT", "180"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Google Account Credentials (set via environment variables)
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL", "")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "")

# Auto cleanup
AUTO_CLEANUP = os.getenv("AUTO_CLEANUP", "true").lower() == "true"
CLEANUP_DELAY = int(os.getenv("CLEANUP_DELAY", "300"))

# Track pending cleanups
pending_cleanups = {}
cleanup_lock = threading.Lock()

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
    """Sanitize filename"""
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return sanitized.replace('..', '_')


def run_adb(command, timeout=None, retries=3, check=True):
    """Execute ADB command with retry logic"""
    if timeout is None:
        timeout = ADB_TIMEOUT
    
    cmd = ["adb", "-s", DEVICE_ID] + command
    last_error = None
    
    for attempt in range(retries):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode != 0 and check:
                last_error = f"ADB Error: {result.stderr.strip()}"
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                raise Exception(last_error)
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            last_error = f"ADB timeout after {timeout}s"
            if attempt < retries - 1:
                time.sleep(2)
                continue
        except Exception as e:
            if "ADB Error" not in str(e):
                last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2)
                continue
    
    if check:
        raise Exception(last_error or "ADB command failed")
    return ""


def keep_device_awake():
    """Configure device to stay awake 24/7"""
    try:
        logger.info("Configuring device for 24/7 operation...")
        
        # Disable screen timeout (set to maximum - never)
        run_adb(["shell", "settings", "put", "system", "screen_off_timeout", "2147483647"], check=False)
        
        # Keep screen on while charging (emulator is always "charging")
        run_adb(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "7"], check=False)
        
        # Disable lock screen
        run_adb(["shell", "settings", "put", "secure", "lockscreen.disabled", "1"], check=False)
        
        # Wake up device
        run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
        
        # Unlock (swipe up)
        run_adb(["shell", "input", "swipe", "500", "1500", "500", "500"], check=False)
        
        logger.info("Device configured for 24/7 operation")
        return True
    except Exception as e:
        logger.warning(f"Failed to configure 24/7 mode: {e}")
        return False


def wake_device():
    """Wake up the device screen"""
    try:
        run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
        time.sleep(0.3)
        run_adb(["shell", "input", "swipe", "500", "1500", "500", "500"], check=False)
        time.sleep(0.3)
    except Exception:
        pass


def wait_for_device(timeout=120):
    """Wait for device to be ready"""
    logger.info(f"Waiting for device {DEVICE_ID}...")
    
    try:
        subprocess.run(["adb", "-s", DEVICE_ID, "wait-for-device"], timeout=timeout, check=True)
        
        # Wait for package manager
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                output = run_adb(["shell", "pm", "list", "packages", "-s"], timeout=10, retries=1, check=False)
                if output and "package:" in output:
                    keep_device_awake()
                    return True
            except Exception:
                pass
            time.sleep(3)
        
        return True
    except Exception as e:
        logger.warning(f"Device wait issue: {e}")
        return False


def check_app_installed(package_name):
    """Check if app is installed"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name], check=False)
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
    
    return paths


def calculate_hash(filepath):
    """Calculate SHA-256 hash"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def format_bytes(size):
    """Format bytes to human-readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def uninstall_app(package_name):
    """Uninstall an app to free memory"""
    try:
        logger.info(f"Uninstalling {package_name}...")
        run_adb(["shell", "pm", "uninstall", package_name], check=False)
        return True
    except Exception as e:
        logger.warning(f"Failed to uninstall {package_name}: {e}")
        return False


def cleanup_package_files(package_name):
    """Delete extracted APK files"""
    try:
        package_dir = os.path.join(DATA_DIR, sanitize_filename(package_name))
        if os.path.exists(package_dir):
            import shutil
            shutil.rmtree(package_dir)
            logger.info(f"Cleaned up files for {package_name}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {package_name}: {e}")


def schedule_cleanup(package_name, delay=None):
    """Schedule cleanup after delay"""
    if delay is None:
        delay = CLEANUP_DELAY
    
    def do_cleanup():
        time.sleep(delay)
        with cleanup_lock:
            if package_name in pending_cleanups:
                uninstall_app(package_name)
                cleanup_package_files(package_name)
                del pending_cleanups[package_name]
    
    with cleanup_lock:
        pending_cleanups[package_name] = True
    
    thread = threading.Thread(target=do_cleanup, daemon=True)
    thread.start()


# ============================================
# UI AUTOMATION HELPERS
# ============================================

def tap(x, y, delay=0.5):
    """Tap at coordinates"""
    run_adb(["shell", "input", "tap", str(x), str(y)], check=False)
    time.sleep(delay)


def type_text(text, delay=0.3):
    """Type text using ADB"""
    # Escape special characters
    escaped = text.replace(" ", "%s").replace("@", "\\@").replace("&", "\\&")
    run_adb(["shell", "input", "text", escaped], check=False)
    time.sleep(delay)


def press_key(keycode, delay=0.3):
    """Press a key"""
    run_adb(["shell", "input", "keyevent", keycode], check=False)
    time.sleep(delay)


def get_screen_xml():
    """Get UI hierarchy XML"""
    try:
        output = run_adb(["shell", "uiautomator", "dump", "/dev/tty"], timeout=15, check=False)
        return output
    except Exception:
        return ""


def find_element_bounds(xml, text=None, resource_id=None, content_desc=None):
    """Find element bounds from UI XML"""
    patterns = []
    
    if text:
        patterns.append(f'text="{text}".*?bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"')
    if resource_id:
        patterns.append(f'resource-id="{resource_id}".*?bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"')
    if content_desc:
        patterns.append(f'content-desc="{content_desc}".*?bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"')
    
    for pattern in patterns:
        match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    return None


def click_element(text=None, resource_id=None, content_desc=None, xml=None):
    """Find and click an element"""
    if xml is None:
        xml = get_screen_xml()
    
    coords = find_element_bounds(xml, text=text, resource_id=resource_id, content_desc=content_desc)
    if coords:
        tap(coords[0], coords[1])
        return True
    return False


# ============================================
# GOOGLE LOGIN AUTOMATION
# ============================================

def check_play_store_signed_in():
    """Check if Play Store is signed in"""
    try:
        # Open Play Store
        run_adb(["shell", "am", "start", "-n", "com.android.vending/.AssetBrowserActivity"])
        time.sleep(3)
        
        xml = get_screen_xml()
        
        # If we see "Sign in" button, not signed in
        if "Sign in" in xml or "sign in" in xml.lower():
            return False
        
        # If we see account icon or search, likely signed in
        if "Search" in xml or "account" in xml.lower() or "Avatar" in xml:
            return True
        
        return True  # Assume signed in if unclear
        
    except Exception as e:
        logger.warning(f"Error checking Play Store login: {e}")
        return False


def google_login(email, password):
    """
    Automate Google login on Play Store
    
    This is a best-effort automation - Google's UI changes frequently
    """
    if not email or not password:
        logger.warning("Google credentials not provided")
        return False
    
    logger.info("Attempting Google login...")
    wake_device()
    
    try:
        # Open Play Store
        run_adb(["shell", "am", "start", "-n", "com.android.vending/.AssetBrowserActivity"])
        time.sleep(4)
        
        xml = get_screen_xml()
        
        # Look for Sign in button
        if click_element(text="Sign in", xml=xml):
            time.sleep(3)
        elif click_element(text="SIGN IN", xml=xml):
            time.sleep(3)
        else:
            # Try tapping common position for sign in
            tap(540, 1700, delay=3)
        
        # Now we should be on Google sign-in page
        xml = get_screen_xml()
        
        # Enter email
        logger.info("Entering email...")
        
        # Click email field
        if click_element(resource_id="identifierId", xml=xml):
            time.sleep(1)
        else:
            # Try clicking on "Email or phone" text
            click_element(text="Email or phone", xml=xml)
            time.sleep(1)
        
        # Type email
        type_text(email, delay=1)
        
        # Click Next
        time.sleep(1)
        xml = get_screen_xml()
        if not click_element(text="Next", xml=xml):
            click_element(resource_id="identifierNext", xml=xml)
        
        time.sleep(4)
        
        # Enter password
        logger.info("Entering password...")
        xml = get_screen_xml()
        
        # Click password field
        if click_element(text="Enter your password", xml=xml):
            time.sleep(1)
        elif "password" in xml.lower():
            # Find password field
            tap(540, 600, delay=1)
        
        # Type password
        type_text(password, delay=1)
        
        # Click Next
        time.sleep(1)
        xml = get_screen_xml()
        if not click_element(text="Next", xml=xml):
            click_element(resource_id="passwordNext", xml=xml)
        
        time.sleep(5)
        
        # Handle any "I agree" / "Accept" prompts
        for _ in range(3):
            xml = get_screen_xml()
            if click_element(text="I agree", xml=xml):
                time.sleep(2)
            elif click_element(text="Accept", xml=xml):
                time.sleep(2)
            elif click_element(text="ACCEPT", xml=xml):
                time.sleep(2)
            elif click_element(text="More", xml=xml):
                time.sleep(2)
            elif click_element(text="SKIP", xml=xml):
                time.sleep(2)
            elif click_element(text="Skip", xml=xml):
                time.sleep(2)
            elif click_element(text="No thanks", xml=xml):
                time.sleep(2)
            else:
                break
        
        # Press Home
        press_key("KEYCODE_HOME")
        
        # Verify login
        time.sleep(2)
        if check_play_store_signed_in():
            logger.info("Google login successful!")
            return True
        else:
            logger.warning("Google login may have failed")
            return False
        
    except Exception as e:
        logger.error(f"Google login error: {e}")
        return False


def ensure_play_store_login():
    """Ensure Play Store is signed in"""
    if check_play_store_signed_in():
        logger.info("Play Store already signed in")
        press_key("KEYCODE_HOME")
        return True
    
    if GOOGLE_EMAIL and GOOGLE_PASSWORD:
        return google_login(GOOGLE_EMAIL, GOOGLE_PASSWORD)
    
    logger.warning("Play Store not signed in and no credentials provided")
    return False


# ============================================
# PLAY STORE AUTOMATION
# ============================================

def open_play_store(package_name):
    """Open Play Store page for an app"""
    try:
        wake_device()
        logger.info(f"Opening Play Store for {package_name}...")
        run_adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"market://details?id={package_name}"
        ])
        time.sleep(4)
        return True
    except Exception as e:
        logger.error(f"Failed to open Play Store: {e}")
        return False


def click_install_button():
    """Find and click Install button"""
    try:
        xml = get_screen_xml()
        
        # Try various Install button patterns
        install_patterns = [
            ("text", "Install"),
            ("text", "INSTALL"),
            ("text", "GET"),
            ("text", "Update"),
            ("text", "UPDATE"),
            ("content_desc", "Install"),
        ]
        
        for attr, value in install_patterns:
            if attr == "text":
                if click_element(text=value, xml=xml):
                    logger.info(f"Clicked '{value}' button")
                    return True
            elif attr == "content_desc":
                if click_element(content_desc=value, xml=xml):
                    logger.info(f"Clicked '{value}' button")
                    return True
        
        # Try common coordinates for Install button
        common_positions = [
            (900, 600), (540, 600), (900, 650), (540, 650),
            (800, 550), (650, 600), (750, 600)
        ]
        
        for x, y in common_positions:
            tap(x, y, delay=2)
            xml = get_screen_xml()
            if "Installing" in xml or "Pending" in xml or "Open" in xml:
                return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Install button click failed: {e}")
        return False


def wait_for_installation(package_name, timeout=None):
    """Wait for app installation to complete"""
    if timeout is None:
        timeout = INSTALL_TIMEOUT
    
    logger.info(f"Waiting for {package_name} installation...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if check_app_installed(package_name):
            logger.info(f"{package_name} installed!")
            return True
        
        # Check UI for progress
        xml = get_screen_xml()
        if "Open" in xml and check_app_installed(package_name):
            return True
        
        time.sleep(5)
    
    return False


def install_from_play_store(package_name):
    """Install app from Play Store automatically"""
    # Check if already installed
    if check_app_installed(package_name):
        logger.info(f"{package_name} already installed")
        return "already_installed"
    
    logger.info(f"Installing {package_name} from Play Store...")
    
    # Ensure signed in
    ensure_play_store_login()
    
    # Open Play Store page
    if not open_play_store(package_name):
        return "failed"
    
    time.sleep(3)
    
    # Check if app exists
    xml = get_screen_xml()
    if "We couldn't find" in xml or "not found" in xml.lower() or "isn't available" in xml:
        logger.warning(f"App {package_name} not found on Play Store")
        press_key("KEYCODE_HOME")
        return "not_found"
    
    # Click Install
    if click_install_button():
        # Wait for installation
        if wait_for_installation(package_name):
            press_key("KEYCODE_HOME")
            return "installed"
    
    # Final check
    time.sleep(5)
    if check_app_installed(package_name):
        press_key("KEYCODE_HOME")
        return "installed"
    
    press_key("KEYCODE_HOME")
    return "failed"


# ============================================
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    try:
        output = run_adb(["devices"], retries=1, timeout=10, check=False)
        devices = [
            line for line in output.splitlines()
            if "device" in line and "List" not in line
        ]
        
        device_ready = len(devices) > 0
        
        return jsonify({
            "status": "healthy" if device_ready else "no_device",
            "device_id": DEVICE_ID,
            "devices_count": len(devices),
            "auto_install": True,
            "auto_cleanup": AUTO_CLEANUP,
            "google_configured": bool(GOOGLE_EMAIL),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200 if device_ready else 503
        
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/login_google", methods=["POST"])
def api_login_google():
    """Trigger Google login"""
    data = request.get_json() or {}
    email = data.get("email", GOOGLE_EMAIL)
    password = data.get("password", GOOGLE_PASSWORD)
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    success = google_login(email, password)
    
    return jsonify({
        "success": success,
        "message": "Login successful" if success else "Login may have failed"
    }), 200 if success else 500


@app.route("/check_login", methods=["GET"])
def api_check_login():
    """Check if Play Store is signed in"""
    signed_in = check_play_store_signed_in()
    press_key("KEYCODE_HOME")
    
    return jsonify({
        "signed_in": signed_in
    }), 200


@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    """Extract APK with auto-install"""
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    # Validate
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": result}), 400
    
    package = result
    logger.info(f"Extraction request for {package}")
    
    try:
        # Wait for device
        wait_for_device()
        
        # Check/install app
        if not check_app_installed(package):
            logger.info(f"{package} not installed, auto-installing...")
            
            install_result = install_from_play_store(package)
            
            if install_result == "not_found":
                return jsonify({
                    "error": "App not found on Play Store",
                    "package": package
                }), 404
            
            elif install_result == "failed":
                return jsonify({
                    "error": "Failed to install app",
                    "package": package,
                    "hint": "Play Store may require sign-in"
                }), 500
        
        # Get APK paths
        apk_paths = get_apk_paths(package)
        
        if not apk_paths:
            return jsonify({
                "error": "No APK files found",
                "package": package
            }), 404
        
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
        
        # Schedule cleanup
        if AUTO_CLEANUP:
            schedule_cleanup(package)
        
        return jsonify({
            "status": "completed",
            "package": package,
            "files": file_info,
            "total_files": len(file_info),
            "total_size": sum(f["size"] for f in file_info),
            "total_size_human": format_bytes(sum(f["size"] for f in file_info)),
            "auto_cleanup": AUTO_CLEANUP,
            "cleanup_delay": f"{CLEANUP_DELAY // 60} minutes" if AUTO_CLEANUP else "disabled"
        }), 200
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download_apk/<package>/<filename>")
def download_apk(package, filename):
    """Download APK"""
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    filename = sanitize_filename(filename)
    
    if not filename.endswith('.apk'):
        return jsonify({"error": "Invalid filename"}), 400
    
    full_path = os.path.join(DATA_DIR, package, filename)
    
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
                        "total_size": total_size
                    })
    
    return jsonify({"packages": packages, "total_packages": len(packages)}), 200


@app.route("/cleanup/<package>", methods=["POST"])
def manual_cleanup(package):
    """Manually cleanup a package"""
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    uninstall_app(package)
    cleanup_package_files(package)
    
    return jsonify({"message": f"Cleaned up {package}"}), 200


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("APK Extractor - Automated Device Agent")
    print("=" * 60)
    print(f"Device ID: {DEVICE_ID}")
    print(f"Auto-Install: Enabled")
    print(f"Auto-Cleanup: {AUTO_CLEANUP} ({CLEANUP_DELAY}s delay)")
    print(f"Google Account: {'Configured' if GOOGLE_EMAIL else 'Not configured'}")
    print("=" * 60)
    
    # Check device
    try:
        output = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        print(output.stdout)
        
        # Configure device for 24/7 operation
        keep_device_awake()
        
    except Exception as e:
        print(f"Warning: {e}")
    
    print("Starting server on port 5001...")
    app.run(host="0.0.0.0", port=5001)
