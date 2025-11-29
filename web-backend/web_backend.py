from flask import Flask, render_template, request, jsonify, send_file
import requests
import os
import time

app = Flask(__name__)

# Configuration: Choose mode
USE_ORCHESTRATOR = os.getenv("USE_ORCHESTRATOR", "false").lower() == "true"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
DEVICE_AGENT_URL = os.getenv("DEVICE_AGENT_URL", "http://localhost:5001")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", mode="orchestrator" if USE_ORCHESTRATOR else "single")

@app.route("/api/health", methods=["GET"])
def health():
    """Check backend health"""
    if USE_ORCHESTRATOR:
        try:
            r = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=5)
            return r.json(), r.status_code
        except Exception as e:
            return jsonify({"status": "orchestrator_unreachable", "error": str(e)}), 503
    else:
        try:
            r = requests.get(f"{DEVICE_AGENT_URL}/health", timeout=5)
            return r.json(), r.status_code
        except Exception as e:
            return jsonify({"status": "agent_unreachable", "error": str(e)}), 503

@app.route("/api/extract", methods=["POST"])
def extract():
    """Request APK extraction"""
    data = request.get_json()
    package = data.get("package", "").strip()
    
    if not package:
        return jsonify({"error": "Package name required"}), 400
    
    if USE_ORCHESTRATOR:
        # Use orchestrator (async with job queue)
        try:
            r = requests.post(
                f"{ORCHESTRATOR_URL}/extract",
                json={"package": package},
                timeout=10
            )
            return r.json(), r.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        # Direct to device agent (synchronous)
        try:
            r = requests.post(
                f"{DEVICE_AGENT_URL}/extract_apk",
                json={"package": package},
                timeout=120
            )
            return r.json(), r.status_code
        except requests.Timeout:
            return jsonify({"error": "Extraction timeout"}), 504
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/status/<job_id>", methods=["GET"])
def status(job_id):
    """Check job status (orchestrator mode only)"""
    if USE_ORCHESTRATOR:
        try:
            r = requests.get(f"{ORCHESTRATOR_URL}/status/{job_id}")
            return r.json(), r.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Not available in single-device mode"}), 400

@app.route("/api/download/<package>/<filename>")
def download(package, filename):
    """Proxy download"""
    base_url = ORCHESTRATOR_URL if USE_ORCHESTRATOR else DEVICE_AGENT_URL
    
    try:
        r = requests.get(
            f"{base_url}/download{'_apk' if not USE_ORCHESTRATOR else ''}/{package}/{filename}",
            stream=True
        )
        if r.status_code == 200:
            return r.content, 200, {
                'Content-Type': 'application/vnd.android.package-archive',
                'Content-Disposition': f'attachment; filename={filename}'
            }
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    mode = "Orchestrator" if USE_ORCHESTRATOR else "Single Device"
    print(f"Starting Web Backend in {mode} mode...")
    app.run(port=8000, debug=True)
