from flask import Flask, request, jsonify, send_file
import subprocess
import os
import time
import hashlib

app = Flask(__name__)
DATA_DIR = "/app/pulls"
os.makedirs(DATA_DIR, exist_ok=True)

def run_adb(command):
    """Execute adb command and return output"""
    cmd = ["adb", "-s", os.getenv("DEVICE", "emulator-5554")] + command
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise Exception(f"ADB Error: {result.stderr}")
    return result.stdout

def wait_for_device():
    """Wait for emulator to be ready"""
    subprocess.run(["adb", "wait-for-device"], timeout=300, check=True)
    time.sleep(3)

def check_app_installed(package_name):
    """Check if app is installed"""
    try:
        output = run_adb(["shell", "pm", "list", "packages", package_name])
        return f"package:{package_name}" in output
    except:
        return False

def get_apk_paths(package_name):
    """Get all APK paths for a package"""
    output = run_adb(["shell", "pm", "path", package_name])
    paths = [line.split(":")[1].strip() for line in output.splitlines() if line.startswith("package:")]
    return paths

def calculate_hash(filepath):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def install_from_play(package_name):
    """Open Play Store for app installation"""
    try:
        run_adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"market://details?id={package_name}"
        ])
        time.sleep(10)  # Wait for potential auto-install
        return True
    except Exception as e:
        print(f"Install error: {e}")
        return False

@app.route("/health", methods=["GET"])
def health():
    """Check if device is connected and ready"""
    try:
        output = run_adb(["shell", "getprop", "sys.boot_completed"])
        boot_completed = "1" in output
        
        return jsonify({
            "status": "healthy" if boot_completed else "booting",
            "device": os.getenv("DEVICE", "emulator-5554"),
            "container_id": os.getenv("HOSTNAME", "unknown")
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    package = request.json.get("package")
    if not package:
        return jsonify({"error": "Missing package name"}), 400

    try:
        wait_for_device()
        
        # Check if app is installed
        if not check_app_installed(package):
            install_from_play(package)
            
            # Check again after install attempt
            if not check_app_installed(package):
                return jsonify({
                    "error": "App not installed. Manual installation required.",
                    "package": package
                }), 404

        # Get APK paths
        apk_paths = get_apk_paths(package)
        
        if not apk_paths:
            return jsonify({"error": "No APK found"}), 404

        # Create package directory
        package_dir = os.path.join(DATA_DIR, package)
        os.makedirs(package_dir, exist_ok=True)
        
        file_info = []
        
        # Pull all APK files
        for i, apk_path in enumerate(apk_paths):
            filename = f"base.apk" if i == 0 else f"split_{i}.apk"
            local_path = os.path.join(package_dir, filename)
            
            # Pull APK
            run_adb(["pull", apk_path, local_path])
            
            # Calculate hash
            file_hash = calculate_hash(local_path)
            file_size = os.path.getsize(local_path)
            
            file_info.append({
                "filename": filename,
                "path": f"{package}/{filename}",
                "size": file_size,
                "hash": file_hash
            })
        
        return jsonify({
            "package": package,
            "files": file_info,
            "total_files": len(file_info),
            "container": os.getenv("HOSTNAME", "unknown")
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download_apk/<package>/<filename>")
def download_apk(package, filename):
    """Download specific APK file"""
    full_path = os.path.join(DATA_DIR, package, filename)
    if os.path.exists(full_path):
        return send_file(full_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    print("Starting Docker Android Device Agent...")
    app.run(host="0.0.0.0", port=5001)
