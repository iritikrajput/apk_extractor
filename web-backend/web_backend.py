"""
APK Extractor - Web Backend
Simple web interface for APK extraction from Play Store

User provides package name → Backend extracts APK → Frontend shows download
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
import requests
import os
import logging
import re
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

app = Flask(__name__)

# Mode configuration
USE_ORCHESTRATOR = os.getenv("USE_ORCHESTRATOR", "false").lower() == "true"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
DEVICE_AGENT_URL = os.getenv("DEVICE_AGENT_URL", "http://localhost:5001")

# Timeouts
EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "180"))
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))

# Logging
LOG_DIR = os.getenv("LOG_PATH", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'web_backend.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('web_backend')

# ============================================
# INPUT VALIDATION
# ============================================

def validate_package_name(package_name):
    """Validate Android package name format"""
    if not package_name:
        return False, "Package name is required"
    
    package_name = package_name.strip()
    
    # Extract from Play Store URL if provided
    url_match = re.search(r'id=([a-zA-Z0-9_.]+)', package_name)
    if url_match:
        package_name = url_match.group(1)
    
    # Check length
    if len(package_name) > 256:
        return False, "Package name too long"
    
    # Validate format
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
    if not re.match(pattern, package_name):
        return False, "Invalid package name format. Use format: com.example.app"
    
    return True, package_name


# ============================================
# ROUTES
# ============================================

@app.route("/", methods=["GET"])
def index():
    """Main page"""
    return render_template(
        "index.html",
        mode="orchestrator" if USE_ORCHESTRATOR else "single"
    )


@app.route("/api/health", methods=["GET"])
def health():
    """Check backend and device health"""
    backend_url = ORCHESTRATOR_URL if USE_ORCHESTRATOR else DEVICE_AGENT_URL
    
    try:
        r = requests.get(
            f"{backend_url}/health",
            timeout=HEALTH_CHECK_TIMEOUT
        )
        
        data = r.json()
        data['mode'] = "orchestrator" if USE_ORCHESTRATOR else "single"
        data['web_backend'] = "healthy"
        
        return jsonify(data), r.status_code
        
    except requests.Timeout:
        return jsonify({
            "status": "unhealthy",
            "error": "Backend timeout",
            "mode": "orchestrator" if USE_ORCHESTRATOR else "single"
        }), 503
    except requests.ConnectionError:
        return jsonify({
            "status": "unhealthy",
            "error": "Cannot connect to backend",
            "mode": "orchestrator" if USE_ORCHESTRATOR else "single"
        }), 503
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "mode": "orchestrator" if USE_ORCHESTRATOR else "single"
        }), 503


@app.route("/api/extract", methods=["POST"])
def extract():
    """Request APK extraction"""
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    # Validate package name
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": result}), 400
    
    package = result
    logger.info(f"Extraction request for {package}")
    
    if USE_ORCHESTRATOR:
        # Orchestrator mode - async with job queue
        try:
            r = requests.post(
                f"{ORCHESTRATOR_URL}/extract",
                json={"package": package},
                timeout=30
            )
            return jsonify(r.json()), r.status_code
            
        except requests.Timeout:
            return jsonify({"error": "Orchestrator timeout"}), 504
        except requests.ConnectionError:
            return jsonify({"error": "Cannot connect to orchestrator"}), 503
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        # Single device mode - synchronous
        try:
            r = requests.post(
                f"{DEVICE_AGENT_URL}/extract_apk",
                json={"package": package},
                timeout=EXTRACTION_TIMEOUT
            )
            return jsonify(r.json()), r.status_code
            
        except requests.Timeout:
            return jsonify({
                "error": "Extraction timeout. The app may be too large or the device is busy.",
                "package": package
            }), 504
        except requests.ConnectionError:
            return jsonify({"error": "Cannot connect to device agent"}), 503
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/status/<job_id>", methods=["GET"])
def status(job_id):
    """Check job status (orchestrator mode only)"""
    if not USE_ORCHESTRATOR:
        return jsonify({"error": "Status endpoint only available in orchestrator mode"}), 400
    
    try:
        r = requests.get(
            f"{ORCHESTRATOR_URL}/status/{job_id}",
            timeout=HEALTH_CHECK_TIMEOUT
        )
        return jsonify(r.json()), r.status_code
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<package>/<filename>")
def download(package, filename):
    """Download APK file"""
    # Validate inputs
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    package = result
    
    # Sanitize filename
    if not re.match(r'^[a-zA-Z0-9._-]+\.apk$', filename):
        return jsonify({"error": "Invalid filename"}), 400
    
    backend_url = ORCHESTRATOR_URL if USE_ORCHESTRATOR else DEVICE_AGENT_URL
    endpoint = "download" if USE_ORCHESTRATOR else "download_apk"
    
    try:
        r = requests.get(
            f"{backend_url}/{endpoint}/{package}/{filename}",
            stream=True,
            timeout=60
        )
        
        if r.status_code == 200:
            return Response(
                r.iter_content(chunk_size=8192),
                content_type='application/vnd.android.package-archive',
                headers={
                    'Content-Disposition': f'attachment; filename={package}_{filename}',
                    'Content-Length': r.headers.get('Content-Length', '')
                }
            )
        else:
            return jsonify({"error": "File not found"}), 404
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/packages", methods=["GET"])
def list_packages():
    """List all extracted packages"""
    backend_url = ORCHESTRATOR_URL if USE_ORCHESTRATOR else DEVICE_AGENT_URL
    endpoint = "packages" if USE_ORCHESTRATOR else "list_packages"
    
    try:
        r = requests.get(
            f"{backend_url}/{endpoint}",
            timeout=HEALTH_CHECK_TIMEOUT
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        logger.error(f"List packages error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("500.html"), 500


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("APK Extractor - Web Backend")
    print("=" * 60)
    print(f"Mode: {'Orchestrator' if USE_ORCHESTRATOR else 'Single Device'}")
    print(f"Backend URL: {ORCHESTRATOR_URL if USE_ORCHESTRATOR else DEVICE_AGENT_URL}")
    print("=" * 60)
    print("Starting server on port 8000...")
    
    app.run(host="0.0.0.0", port=8000, debug=os.getenv("DEBUG", "false").lower() == "true")
