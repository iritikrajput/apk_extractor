"""
APK Extractor - Device Agent v3.0
Simplified and robust - no random clicking!
"""

from flask import Flask, request, jsonify, send_file
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
INSTALL_TIMEOUT = int(os.getenv("INSTALL_TIMEOUT", "300"))

AUTO_CLEANUP = os.getenv("AUTO_CLEANUP", "true").lower() == "true"
CLEANUP_DELAY = int(os.getenv("CLEANUP_DELAY", "300"))

pending_cleanups = {}
cleanup_lock = threading.Lock()

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'device_agent.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('device_agent')

# ============================================
# ADB HELPERS
# ============================================

def run_adb(command, timeout=None, check=True):
    """Execute ADB command"""
    if timeout is None:
        timeout = ADB_TIMEOUT
    
    cmd = ["adb", "-s", DEVICE_ID] + command
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and check:
            raise Exception(f"ADB Error: {result.stderr.strip()}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout after {timeout}s")


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
    return re.sub(r'[^a-zA-Z0-9._-]', '_', filename).replace('..', '_')


def check_app_installed(package_name):
    """Check if app is installed via package manager"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name], check=False)
        return f"package:{package_name}" in output
    except:
        return False


def get_apk_paths(package_name):
    """Get APK file paths for installed app"""
    try:
        output = run_adb(["shell", "pm", "path", package_name])
        paths = []
        for line in output.splitlines():
            if line.startswith("package:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    paths.append(path)
        return paths
    except:
        return []


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


def wait_for_device(timeout=120):
    """Wait for device to be ready"""
    try:
        subprocess.run(["adb", "-s", DEVICE_ID, "wait-for-device"], timeout=timeout, check=True)
        # Wait for package manager
        start = time.time()
        while time.time() - start < timeout:
            try:
                output = run_adb(["shell", "pm", "list", "packages", "-s"], timeout=10, check=False)
                if output and "package:" in output:
                    # Wake up screen
                    run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
                    run_adb(["shell", "input", "swipe", "500", "1500", "500", "500"], check=False)
                    return True
            except:
                pass
            time.sleep(3)
        return True
    except:
        return False


# ============================================
# SIMPLE UI AUTOMATION
# ============================================

def tap(x, y):
    """Tap at coordinates"""
    run_adb(["shell", "input", "tap", str(int(x)), str(int(y))], check=False)
    time.sleep(1)


def press_home():
    """Go to home screen"""
    run_adb(["shell", "input", "keyevent", "3"], check=False)
    time.sleep(1)


def press_back():
    """Press back button"""
    run_adb(["shell", "input", "keyevent", "4"], check=False)
    time.sleep(0.5)


def get_ui_xml():
    """Get current screen UI hierarchy"""
    try:
        run_adb(["shell", "rm", "-f", "/sdcard/ui.xml"], check=False)
        run_adb(["shell", "uiautomator", "dump", "/sdcard/ui.xml"], timeout=15, check=False)
        time.sleep(0.5)
        return run_adb(["shell", "cat", "/sdcard/ui.xml"], timeout=10, check=False)
    except:
        return ""


def find_button_coords(xml, button_text):
    """
    Find EXACT button by text - returns (x, y) or None
    Only matches buttons/clickable elements with EXACT text match
    """
    if not xml:
        return None
    
    # Look for exact text match with bounds
    # Pattern: text="Install" ... bounds="[x1,y1][x2,y2]"
    pattern = rf'text="{re.escape(button_text)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    match = re.search(pattern, xml)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    # Also try with bounds before text
    pattern = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="{re.escape(button_text)}"'
    match = re.search(pattern, xml)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    return None


def click_button(button_text, xml=None):
    """Click a button by its EXACT text"""
    if xml is None:
        xml = get_ui_xml()
    
    coords = find_button_coords(xml, button_text)
    if coords:
        logger.info(f"Clicking '{button_text}' at {coords}")
        tap(coords[0], coords[1])
        return True
    return False


# ============================================
# PLAY STORE INSTALLATION - SIMPLE & DIRECT
# ============================================

def install_from_play_store(package_name):
    """
    Install app from Play Store - SIMPLIFIED
    Only clicks Install button, nothing else
    """
    logger.info(f"=== Installing {package_name} from Play Store ===")
    
    # Check if already installed
    if check_app_installed(package_name):
        logger.info(f"{package_name} is already installed")
        return "already_installed"
    
    # Wake up and go home first
    run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], check=False)
    time.sleep(0.5)
    press_home()
    time.sleep(1)
    
    # Open Play Store page for this app
    logger.info(f"Opening Play Store for {package_name}")
    run_adb([
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", f"market://details?id={package_name}"
    ], check=False)
    
    # Wait for Play Store to load
    time.sleep(5)
    
    # Get current screen
    xml = get_ui_xml()
    
    # Check for "not found" error
    if "couldn't find" in xml.lower() or "not found" in xml.lower() or "isn't available" in xml.lower():
        logger.warning(f"App {package_name} not found on Play Store")
        press_home()
        return "not_found"
    
    # Check if already installed (has "Open" button)
    if find_button_coords(xml, "Open") and find_button_coords(xml, "Uninstall"):
        logger.info(f"{package_name} is already installed (Open button visible)")
        press_home()
        return "already_installed"
    
    # Find and click Install button
    install_clicked = False
    for attempt in range(5):
        xml = get_ui_xml()
        
        # Check if already installed now
        if check_app_installed(package_name):
            logger.info(f"{package_name} installed!")
            press_home()
            return "installed"
        
        # Check for Open button (means installed)
        if find_button_coords(xml, "Open"):
            logger.info(f"{package_name} installed (Open button visible)")
            press_home()
            return "installed"
        
        # Try to click Install button
        if click_button("Install", xml):
            logger.info("Clicked Install button")
            install_clicked = True
            time.sleep(3)
            break
        
        logger.warning(f"Install button not found (attempt {attempt + 1}/5)")
        time.sleep(2)
    
    if not install_clicked:
        logger.error("Could not find Install button")
        press_home()
        return "failed"
    
    # Wait for installation to complete
    logger.info(f"Waiting for installation (max {INSTALL_TIMEOUT}s)...")
    start_time = time.time()
    
    while time.time() - start_time < INSTALL_TIMEOUT:
        # Check via package manager (most reliable)
        if check_app_installed(package_name):
            logger.info(f"✓ {package_name} installed successfully!")
            press_home()
            return "installed"
        
        # Check UI for completion
        xml = get_ui_xml()
        if find_button_coords(xml, "Open") and find_button_coords(xml, "Uninstall"):
            logger.info(f"✓ {package_name} installed (Open button visible)")
            time.sleep(3)  # Wait for system to register
            press_home()
            return "installed"
        
        # Log progress
        if "Pending" in xml:
            logger.info("Status: Pending...")
        elif "Downloading" in xml or "%" in xml:
            logger.info("Status: Downloading...")
        elif "Installing" in xml:
            logger.info("Status: Installing...")
        
        time.sleep(5)
    
    # Final check
    if check_app_installed(package_name):
        press_home()
        return "installed"
    
    logger.error(f"Installation timed out for {package_name}")
    press_home()
    return "failed"


# ============================================
# CLEANUP
# ============================================

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
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    try:
        output = run_adb(["devices"], timeout=10, check=False)
        devices = [l for l in output.splitlines() if "device" in l and "List" not in l and "offline" not in l]
        ok = len(devices) > 0
        
        return jsonify({
            "status": "healthy" if ok else "no_device",
            "device_id": DEVICE_ID,
            "devices_count": len(devices),
            "auto_install": True,
            "auto_cleanup": AUTO_CLEANUP,
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
    logger.info(f"========== EXTRACTION REQUEST: {package} ==========")
    
    try:
        wait_for_device()
        
        # Auto-install if not installed
        if not check_app_installed(package):
            logger.info(f"{package} not installed, starting installation...")
            
            install_result = install_from_play_store(package)
            
            if install_result == "not_found":
                return jsonify({
                    "error": "App not found on Google Play Store",
                    "package": package
                }), 404
            
            if install_result == "failed":
                return jsonify({
                    "error": "Installation failed. Make sure Play Store is signed in.",
                    "package": package,
                    "hint": "Run ./setup_google_login.sh to sign in"
                }), 500
            
            # Wait for system to settle
            logger.info("Installation complete, waiting for system...")
            time.sleep(5)
            
            # Verify
            for i in range(10):
                if check_app_installed(package):
                    logger.info(f"✓ Verified: {package} is installed")
                    break
                time.sleep(2)
            else:
                return jsonify({
                    "error": "App installed but not detected. Try again.",
                    "package": package
                }), 500
        
        # Make sure we're at home screen
        press_home()
        time.sleep(1)
        
        # Get APK paths
        apk_paths = None
        for _ in range(5):
            apk_paths = get_apk_paths(package)
            if apk_paths:
                break
            time.sleep(2)
        
        if not apk_paths:
            return jsonify({
                "error": "Could not find APK files",
                "package": package
            }), 404
        
        # Extract APKs
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
                logger.info(f"Pulling {path}")
                run_adb(["pull", path, local], timeout=300)
                
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
                    logger.info(f"✓ Extracted {fname} ({format_bytes(size)})")
            except Exception as e:
                logger.error(f"Failed to pull: {e}")
        
        if not files:
            return jsonify({"error": "Failed to extract APK files"}), 500
        
        # Schedule cleanup
        if AUTO_CLEANUP:
            schedule_cleanup(package)
        
        logger.info(f"========== EXTRACTION COMPLETE: {package} ==========")
        
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
        logger.error(f"Extraction error: {e}")
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


@app.route("/cleanup/<package>", methods=["POST"])
def manual_cleanup(package):
    valid, package = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package"}), 400
    uninstall_app(package)
    cleanup_package_files(package)
    return jsonify({"message": f"Cleaned {package}"}), 200


@app.route("/debug_screen", methods=["GET"])
def debug_screen():
    """Debug endpoint to see current screen"""
    xml = get_ui_xml()
    texts = []
    for match in re.finditer(r'text="([^"]+)"', xml):
        t = match.group(1).strip()
        if t:
            texts.append(t)
    return jsonify({
        "screen_texts": texts[:30],
        "xml_length": len(xml)
    })


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    
    print("=" * 60)
    print("APK Extractor - Device Agent v3.0 (Simplified)")
    print("=" * 60)
    print(f"Device: {DEVICE_ID}")
    print(f"Auto-Install: Enabled")
    print(f"Auto-Cleanup: {AUTO_CLEANUP}")
    print("=" * 60)
    print("Starting on port 5001...")
    
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
