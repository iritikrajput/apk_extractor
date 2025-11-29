from flask import Flask, request, jsonify, send_file
import subprocess
import os
import time
import hashlib

app = Flask(__name__)
DATA_DIR = "./pulls"
os.makedirs(DATA_DIR, exist_ok=True)

def run_adb(command):
    """Execute adb command and return output"""
    cmd = ["adb"] + command
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"ADB Error: {result.stderr}")
    return result.stdout

def wait_for_device():
    """Wait for emulator to be ready"""
    subprocess.run(["adb", "wait-for-device"], check=True)
    time.sleep(2)  # Additional wait for system to stabilize

def install_from_play(package_name):
    """
    Install app from Play Store using intent
    Note: Requires Play Store to be setup with account
    """
    try:
        # Open Play Store page for the app
        run_adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"market://details?id={package_name}"
        ])
        
        # Wait for user to install (or automate with Appium in future)
        # For now, we assume app is already installed or user installs manually
        time.sleep(5)
        
        return True
    except Exception as e:
        print(f"Install error: {e}")
        return False

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

@app.route("/health", methods=["GET"])
def health():
    """Check if device is connected"""
    try:
        output = run_adb(["devices"])
        devices = [line for line in output.splitlines() if "device" in line and "List" not in line]
        return jsonify({"status": "healthy", "devices": len(devices)}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route("/extract_apk", methods=["POST"])
def extract_apk():
    package = request.json.get("package")
    if not package:
        return jsonify({"error": "Missing package name"}), 400

    try:
        wait_for_device()
        
        # Check if app is installed
        if not check_app_installed(package):
            # Attempt to trigger install
            install_from_play(package)
            
            # Check again
            if not check_app_installed(package):
                return jsonify({
                    "error": "App not installed. Please install manually from Play Store first.",
                    "package": package
                }), 404

        # Get APK path(s)
        apk_paths = get_apk_paths(package)
        
        if not apk_paths:
            return jsonify({"error": "No APK found for package"}), 404

        # Create package directory
        package_dir = os.path.join(DATA_DIR, package)
        os.makedirs(package_dir, exist_ok=True)
        
        local_files = []
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
            
            local_files.append(filename)
            file_info.append({
                "filename": filename,
                "path": f"{package}/{filename}",
                "size": file_size,
                "hash": file_hash
            })
        
        return jsonify({
            "package": package,
            "files": file_info,
            "total_files": len(local_files)
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

@app.route("/list_packages", methods=["GET"])
def list_packages():
    """List all extracted packages"""
    packages = []
    if os.path.exists(DATA_DIR):
        packages = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    return jsonify({"packages": packages}), 200

if __name__ == "__main__":
    print("Starting Device Agent...")
    print("Make sure emulator is running: adb devices")
    app.run(host="0.0.0.0", port=5001)
