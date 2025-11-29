"""
APK Extractor - Automated Device Agent
Fully automated APK extraction with auto-install and Google login

Features:
- Auto-login to Google Play Store
- Auto-install apps from Play Store (IMPROVED)
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

DATA_DIR = os.getenv("APK_STORAGE_PATH", "./pulls")
LOG_DIR = os.getenv("LOG_PATH", "./logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

DEVICE_ID = os.getenv("DEVICE_ID", "emulator-5554")
ADB_TIMEOUT = int(os.getenv("ADB_TIMEOUT", "60"))
EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "300"))
INSTALL_TIMEOUT = int(os.getenv("INSTALL_TIMEOUT", "180"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL", "")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "")

AUTO_CLEANUP = os.getenv("AUTO_CLEANUP", "true").lower() == "true"
CLEANUP_DELAY = int(os.getenv("CLEANUP_DELAY", "300"))

pending_cleanups = {}
cleanup_lock = threading.Lock()

# ============================================
# LOGGING
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
# ADB HELPERS
# ============================================

def run_adb(command, timeout=None, retries=3, check=True):
    """Execute ADB command"""
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
            last_error = f"Timeout after {timeout}s"
            if attempt < retries - 1:
                time.sleep(2)
        except Exception as e:
            if "ADB Error" not in str(e):
                last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2)
    
    if check:
        raise Exception(last_error or "ADB failed")
    return ""


def validate_package_name(package_name):
    if not package_name:
        return False, "Package name required"
    package_name = package_name.strip()
    if len(package_name) > 256:
        return False, "Package name too long"
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
    if not re.match(pattern, package_name):
        return False, "Invalid package format"
    return True, package_name


def sanitize_filename(filename):
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return sanitized.replace('..', '_')


def keep_device_awake():
    """Configure device for 24/7 operation"""
    try:
        run_adb(["shell", "settings", "put", "system", "screen_off_timeout", "2147483647"], check=False)
        run_adb(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "7"], check=False)
        run_adb(["shell", "svc", "power", "stayon", "true"], check=False)
        run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
        run_adb(["shell", "input", "swipe", "500", "1500", "500", "500"], check=False)
        logger.info("Device configured for 24/7")
        return True
    except:
        return False


def wake_device():
    """Wake up screen"""
    try:
        run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
        time.sleep(0.5)
        run_adb(["shell", "input", "swipe", "500", "1500", "500", "500"], check=False)
        time.sleep(0.5)
    except:
        pass


def wait_for_device(timeout=120):
    """Wait for device"""
    try:
        subprocess.run(["adb", "-s", DEVICE_ID, "wait-for-device"], timeout=timeout, check=True)
        start = time.time()
        while time.time() - start < timeout:
            try:
                output = run_adb(["shell", "pm", "list", "packages", "-s"], timeout=10, retries=1, check=False)
                if output and "package:" in output:
                    keep_device_awake()
                    return True
            except:
                pass
            time.sleep(3)
        return True
    except:
        return False


def check_app_installed(package_name):
    """Check if app installed"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name], check=False)
        return f"package:{package_name}" in output
    except:
        return False


def get_apk_paths(package_name):
    """Get APK paths"""
    output = run_adb(["shell", "pm", "path", package_name])
    paths = []
    for line in output.splitlines():
        if line.startswith("package:"):
            path = line.split(":", 1)[1].strip()
            if path:
                paths.append(path)
    return paths


def calculate_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest()


def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def uninstall_app(package_name):
    try:
        logger.info(f"Uninstalling {package_name}")
        run_adb(["shell", "pm", "uninstall", package_name], check=False)
        return True
    except:
        return False


def cleanup_package_files(package_name):
    try:
        import shutil
        pkg_dir = os.path.join(DATA_DIR, sanitize_filename(package_name))
        if os.path.exists(pkg_dir):
            shutil.rmtree(pkg_dir)
    except:
        pass


def schedule_cleanup(package_name, delay=None):
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
    threading.Thread(target=do_cleanup, daemon=True).start()


# ============================================
# UI AUTOMATION - IMPROVED
# ============================================

def tap(x, y, delay=0.5):
    """Tap screen"""
    run_adb(["shell", "input", "tap", str(int(x)), str(int(y))], check=False)
    time.sleep(delay)


def type_text(text, delay=0.3):
    """Type text"""
    escaped = text.replace(" ", "%s").replace("@", "\\@").replace("&", "\\&")
    run_adb(["shell", "input", "text", escaped], check=False)
    time.sleep(delay)


def press_key(keycode, delay=0.3):
    """Press key"""
    run_adb(["shell", "input", "keyevent", keycode], check=False)
    time.sleep(delay)


def press_enter():
    """Press Enter key"""
    press_key("66", delay=0.5)


def press_tab():
    """Press Tab key"""
    press_key("61", delay=0.3)


def press_back():
    """Press Back button"""
    press_key("KEYCODE_BACK", delay=0.5)


def press_home():
    """Press Home button"""
    press_key("KEYCODE_HOME", delay=0.5)


def get_screen_xml():
    """Get UI hierarchy"""
    try:
        # Dump to device then pull
        run_adb(["shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"], timeout=15, check=False)
        output = run_adb(["shell", "cat", "/sdcard/ui_dump.xml"], timeout=10, check=False)
        return output
    except:
        return ""


def get_screen_size():
    """Get screen resolution"""
    try:
        output = run_adb(["shell", "wm", "size"], check=False)
        match = re.search(r'(\d+)x(\d+)', output)
        if match:
            return int(match.group(1)), int(match.group(2))
    except:
        pass
    return 1080, 2280  # Default


def find_element(xml, text=None, resource_id=None, class_name=None, content_desc=None):
    """Find element bounds in UI XML"""
    if not xml:
        return None
    
    # Build pattern based on attributes
    patterns = []
    
    if text:
        # Exact match
        patterns.append(rf'text="{re.escape(text)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
        # Partial match
        patterns.append(rf'text="[^"]*{re.escape(text)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    
    if resource_id:
        patterns.append(rf'resource-id="[^"]*{re.escape(resource_id)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    
    if content_desc:
        patterns.append(rf'content-desc="[^"]*{re.escape(content_desc)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    
    if class_name:
        patterns.append(rf'class="{re.escape(class_name)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    
    for pattern in patterns:
        match = re.search(pattern, xml, re.IGNORECASE)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    return None


def click_element(text=None, resource_id=None, content_desc=None, class_name=None):
    """Find and click element"""
    xml = get_screen_xml()
    coords = find_element(xml, text=text, resource_id=resource_id, 
                         content_desc=content_desc, class_name=class_name)
    if coords:
        tap(coords[0], coords[1])
        return True
    return False


def scroll_down():
    """Scroll down"""
    width, height = get_screen_size()
    run_adb(["shell", "input", "swipe", 
             str(width // 2), str(int(height * 0.7)),
             str(width // 2), str(int(height * 0.3)), "300"], check=False)
    time.sleep(1)


# ============================================
# PLAY STORE AUTOMATION - IMPROVED
# ============================================

def open_play_store_app(package_name):
    """Open Play Store for app"""
    wake_device()
    logger.info(f"Opening Play Store for {package_name}")
    
    # Method 1: Direct market intent
    run_adb([
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", f"market://details?id={package_name}"
    ])
    time.sleep(4)
    
    return True


def find_install_button():
    """Find Install button coordinates using multiple methods"""
    xml = get_screen_xml()
    width, height = get_screen_size()
    
    # Method 1: Look for Install text
    install_texts = ["Install", "INSTALL", "Get", "GET", "Free", "FREE"]
    for text in install_texts:
        coords = find_element(xml, text=text)
        if coords:
            logger.info(f"Found '{text}' button at {coords}")
            return coords
    
    # Method 2: Look for button with install in resource-id
    coords = find_element(xml, resource_id="install")
    if coords:
        logger.info(f"Found install button by resource-id at {coords}")
        return coords
    
    # Method 3: Look for common Play Store button patterns
    button_patterns = [
        r'class="android\.widget\.Button"[^>]*text="Install"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        r'text="Install"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        r'content-desc="[^"]*[Ii]nstall[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
    ]
    
    for pattern in button_patterns:
        match = re.search(pattern, xml, re.IGNORECASE)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            coords = ((x1 + x2) // 2, (y1 + y2) // 2)
            logger.info(f"Found install button by pattern at {coords}")
            return coords
    
    # Method 4: Default positions for common screen sizes
    # Play Store typically has Install button on right side
    default_positions = [
        (width - 150, 550),   # Right side, upper area
        (width - 150, 600),   # Right side
        (width - 200, 550),
        (width - 200, 600),
        (width // 2 + 200, 550),
        (width // 2 + 200, 600),
    ]
    
    logger.info("Using default button positions")
    return default_positions[0]  # Return first default position


def click_install_button():
    """Click the Install button"""
    coords = find_install_button()
    if coords:
        logger.info(f"Clicking Install at {coords}")
        tap(coords[0], coords[1], delay=2)
        return True
    return False


def handle_install_prompts():
    """Handle any prompts after clicking Install"""
    time.sleep(2)
    xml = get_screen_xml()
    
    # Handle "Continue" prompt
    if click_element(text="Continue"):
        time.sleep(2)
        xml = get_screen_xml()
    
    # Handle account selection
    if "Choose an account" in xml or "account" in xml.lower():
        # Click first account
        tap(540, 400, delay=2)
    
    # Handle permissions
    permission_texts = ["Allow", "ALLOW", "Accept", "ACCEPT", "OK", "Continue", "CONTINUE"]
    for text in permission_texts:
        if click_element(text=text):
            time.sleep(1)


def wait_for_download_to_start():
    """Wait for download to begin"""
    logger.info("Waiting for download to start...")
    for _ in range(10):
        xml = get_screen_xml()
        if any(x in xml for x in ["Pending", "Downloading", "Installing", "Cancel", "Open", "Uninstall"]):
            logger.info("Download/Install in progress")
            return True
        time.sleep(2)
    return False


def wait_for_installation(package_name, timeout=None):
    """Wait for installation to complete"""
    if timeout is None:
        timeout = INSTALL_TIMEOUT
    
    logger.info(f"Waiting for {package_name} installation (max {timeout}s)...")
    start = time.time()
    last_status = ""
    
    while time.time() - start < timeout:
        # Check if installed via package manager (most reliable)
        if check_app_installed(package_name):
            logger.info(f"{package_name} installed successfully!")
            # Wait a bit more for system to fully register
            time.sleep(3)
            return True
        
        # Check UI for status
        xml = get_screen_xml()
        
        # If we see "Open" button, app is installed
        if "Open" in xml and "Uninstall" in xml:
            logger.info("Detected 'Open' and 'Uninstall' buttons - app installed")
            # Wait and verify with package manager
            time.sleep(3)
            if check_app_installed(package_name):
                return True
            # Give it more time
            time.sleep(5)
            return check_app_installed(package_name)
        
        # Track and log status
        current_status = ""
        if "Downloading" in xml:
            current_status = "Downloading"
        elif "Installing" in xml:
            current_status = "Installing"
        elif "Pending" in xml:
            current_status = "Pending"
        elif "%" in xml:
            current_status = "Downloading"
        
        if current_status and current_status != last_status:
            logger.info(f"Status: {current_status}...")
            last_status = current_status
        
        time.sleep(5)
    
    # Final check after timeout
    if check_app_installed(package_name):
        logger.info(f"{package_name} installed (detected after timeout)")
        return True
    
    logger.warning(f"Installation timeout for {package_name}")
    return False


def install_from_play_store(package_name):
    """
    IMPROVED: Install app from Play Store
    """
    # Check if already installed
    if check_app_installed(package_name):
        logger.info(f"{package_name} already installed")
        return "already_installed"
    
    logger.info(f"=== Installing {package_name} from Play Store ===")
    
    # Open Play Store
    open_play_store_app(package_name)
    time.sleep(4)
    
    # Check if app exists
    xml = get_screen_xml()
    not_found_texts = ["We couldn't find", "not found", "isn't available", "Item not found"]
    if any(text.lower() in xml.lower() for text in not_found_texts):
        logger.warning(f"App {package_name} not found on Play Store")
        press_home()
        return "not_found"
    
    # Try to click Install button multiple times with different methods
    for attempt in range(5):
        logger.info(f"Install attempt {attempt + 1}/5")
        
        # First check if already installed (Open button visible)
        xml = get_screen_xml()
        if "Open" in xml and "Uninstall" in xml:
            logger.info("App already installed (Open button detected)")
            press_home()
            time.sleep(2)
            return "installed"
        
        # Check if already installed via pm
        if check_app_installed(package_name):
            logger.info(f"{package_name} is now installed")
            press_home()
            time.sleep(2)
            return "installed"
        
        # Click Install
        click_install_button()
        time.sleep(3)
        
        # Handle any prompts
        handle_install_prompts()
        
        # Check if download started
        if wait_for_download_to_start():
            # Wait for installation
            if wait_for_installation(package_name):
                logger.info(f"Installation of {package_name} completed!")
                press_home()
                time.sleep(2)
                return "installed"
        
        # Check again if installed while we were waiting
        if check_app_installed(package_name):
            logger.info(f"{package_name} installed (detected after waiting)")
            press_home()
            time.sleep(2)
            return "installed"
        
        # If still on same page, try scrolling and clicking again
        xml = get_screen_xml()
        if "Install" in xml:
            scroll_down()
            time.sleep(1)
    
    # Final checks
    time.sleep(5)
    if check_app_installed(package_name):
        press_home()
        time.sleep(2)
        return "installed"
    
    # One more UI check
    xml = get_screen_xml()
    if "Open" in xml:
        press_home()
        time.sleep(2)
        if check_app_installed(package_name):
            return "installed"
    
    logger.warning(f"Failed to install {package_name}")
    press_home()
    return "failed"


# ============================================
# GOOGLE LOGIN
# ============================================

def check_play_store_signed_in():
    """Check if signed in"""
    try:
        run_adb(["shell", "am", "start", "-n", "com.android.vending/.AssetBrowserActivity"])
        time.sleep(4)
        xml = get_screen_xml()
        
        if any(x in xml for x in ["Sign in", "sign in", "Add account"]):
            return False
        if any(x in xml for x in ["Search", "account", "Avatar", "Apps", "Games"]):
            return True
        return True
    except:
        return False


def google_login(email, password):
    """Automate Google login"""
    if not email or not password:
        return False
    
    logger.info("Attempting Google login...")
    wake_device()
    
    try:
        run_adb(["shell", "am", "start", "-n", "com.android.vending/.AssetBrowserActivity"])
        time.sleep(4)
        
        # Click Sign in
        if not click_element(text="Sign in"):
            click_element(text="SIGN IN")
        time.sleep(3)
        
        # Enter email
        type_text(email, delay=1)
        press_enter()
        time.sleep(4)
        
        # Enter password
        type_text(password, delay=1)
        press_enter()
        time.sleep(5)
        
        # Handle prompts
        for _ in range(5):
            xml = get_screen_xml()
            for text in ["I agree", "Accept", "ACCEPT", "More", "SKIP", "Skip", "No thanks", "Not now"]:
                if click_element(text=text):
                    time.sleep(2)
                    break
            else:
                break
        
        press_home()
        time.sleep(2)
        
        return check_play_store_signed_in()
    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


def ensure_play_store_login():
    """Ensure signed in"""
    if check_play_store_signed_in():
        press_home()
        return True
    
    if GOOGLE_EMAIL and GOOGLE_PASSWORD:
        return google_login(GOOGLE_EMAIL, GOOGLE_PASSWORD)
    
    return False


# ============================================
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    try:
        output = run_adb(["devices"], retries=1, timeout=10, check=False)
        devices = [l for l in output.splitlines() if "device" in l and "List" not in l and "offline" not in l]
        ok = len(devices) > 0
        
        return jsonify({
            "status": "healthy" if ok else "no_device",
            "device_id": DEVICE_ID,
            "devices_count": len(devices),
            "auto_install": True,
            "auto_cleanup": AUTO_CLEANUP,
            "google_configured": bool(GOOGLE_EMAIL),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200 if ok else 503
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": result}), 400
    
    package = result
    logger.info(f"=== Extraction request: {package} ===")
    
    try:
        wait_for_device()
        
        # Auto-install if needed
        if not check_app_installed(package):
            logger.info(f"{package} not installed, auto-installing...")
            
            result = install_from_play_store(package)
            
            if result == "not_found":
                return jsonify({
                    "error": "App not found on Play Store",
                    "package": package
                }), 404
            
            if result == "failed":
                return jsonify({
                    "error": "Failed to install app. Try again or install manually.",
                    "package": package
                }), 500
            
            # IMPORTANT: Wait after installation for system to settle
            logger.info("Installation complete, waiting for system to settle...")
            press_home()
            time.sleep(5)
            
            # Verify installation with retries
            for verify_attempt in range(5):
                if check_app_installed(package):
                    logger.info(f"Verified: {package} is installed")
                    break
                logger.info(f"Waiting for installation to register... (attempt {verify_attempt + 1})")
                time.sleep(3)
            else:
                # One final check
                if not check_app_installed(package):
                    return jsonify({
                        "error": "App installed but not detected. Please try again.",
                        "package": package
                    }), 500
        
        # Go home and wait before extraction
        press_home()
        time.sleep(2)
        
        # Get APK paths with retries
        apk_paths = None
        for path_attempt in range(3):
            apk_paths = get_apk_paths(package)
            if apk_paths:
                break
            logger.info(f"Retrying APK path lookup... (attempt {path_attempt + 1})")
            time.sleep(2)
        
        if not apk_paths:
            return jsonify({"error": "No APK found. App may still be installing.", "package": package}), 404
        
        # Extract
        pkg_dir = os.path.join(DATA_DIR, sanitize_filename(package))
        os.makedirs(pkg_dir, exist_ok=True)
        
        files = []
        for i, path in enumerate(apk_paths):
            try:
                fname = "base.apk" if i == 0 else f"split_{i}.apk"
                if i > 0:
                    orig = os.path.basename(path)
                    if "split" in orig or "config" in orig:
                        fname = sanitize_filename(orig)
                
                local = os.path.join(pkg_dir, fname)
                run_adb(["pull", path, local], timeout=EXTRACTION_TIMEOUT)
                
                if os.path.exists(local):
                    size = os.path.getsize(local)
                    files.append({
                        "filename": fname,
                        "path": f"{package}/{fname}",
                        "size": size,
                        "size_human": format_bytes(size),
                        "hash": calculate_hash(local),
                        "hash_algorithm": "SHA-256"
                    })
            except Exception as e:
                logger.error(f"Pull failed: {e}")
        
        if not files:
            return jsonify({"error": "Extraction failed"}), 500
        
        if AUTO_CLEANUP:
            schedule_cleanup(package)
        
        return jsonify({
            "status": "completed",
            "package": package,
            "files": files,
            "total_files": len(files),
            "total_size": sum(f["size"] for f in files),
            "total_size_human": format_bytes(sum(f["size"] for f in files)),
            "auto_cleanup": AUTO_CLEANUP,
            "cleanup_delay": f"{CLEANUP_DELAY // 60} min"
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download_apk/<package>/<filename>")
def download_apk(package, filename):
    valid, package = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package"}), 400
    
    filename = sanitize_filename(filename)
    if not filename.endswith('.apk'):
        return jsonify({"error": "Invalid file"}), 400
    
    path = os.path.join(DATA_DIR, package, filename)
    real_path = os.path.realpath(path)
    
    if not real_path.startswith(os.path.realpath(DATA_DIR)):
        return jsonify({"error": "Invalid path"}), 400
    
    if os.path.exists(path):
        return send_file(path, as_attachment=True,
                        download_name=f"{package}_{filename}",
                        mimetype='application/vnd.android.package-archive')
    return jsonify({"error": "Not found"}), 404


@app.route("/list_packages", methods=["GET"])
def list_packages():
    packages = []
    if os.path.exists(DATA_DIR):
        for name in os.listdir(DATA_DIR):
            pkg_path = os.path.join(DATA_DIR, name)
            if os.path.isdir(pkg_path):
                files = [f for f in os.listdir(pkg_path) if f.endswith('.apk')]
                if files:
                    total = sum(os.path.getsize(os.path.join(pkg_path, f)) for f in files)
                    packages.append({"package": name, "files": files, "total_size": total})
    return jsonify({"packages": packages}), 200


@app.route("/login_google", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = data.get("email", GOOGLE_EMAIL)
    password = data.get("password", GOOGLE_PASSWORD)
    
    if not email or not password:
        return jsonify({"error": "Credentials required"}), 400
    
    ok = google_login(email, password)
    return jsonify({"success": ok}), 200 if ok else 500


@app.route("/check_login", methods=["GET"])
def api_check_login():
    signed_in = check_play_store_signed_in()
    press_home()
    return jsonify({"signed_in": signed_in}), 200


@app.route("/cleanup/<package>", methods=["POST"])
def manual_cleanup(package):
    valid, package = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package"}), 400
    uninstall_app(package)
    cleanup_package_files(package)
    return jsonify({"message": f"Cleaned {package}"}), 200


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("APK Extractor - Device Agent")
    print("=" * 60)
    print(f"Device: {DEVICE_ID}")
    print(f"Auto-Install: Enabled (IMPROVED)")
    print(f"Auto-Cleanup: {AUTO_CLEANUP} ({CLEANUP_DELAY}s)")
    print(f"Google: {'Configured' if GOOGLE_EMAIL else 'Not set'}")
    print("=" * 60)
    
    try:
        subprocess.run(["adb", "devices"], capture_output=True, timeout=10)
        keep_device_awake()
    except:
        pass
    
    print("Starting on port 5001...")
    app.run(host="0.0.0.0", port=5001)
