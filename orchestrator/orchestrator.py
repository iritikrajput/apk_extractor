"""
APK Extractor - Orchestrator
Load balancer and job queue manager for multi-container APK extraction

Features:
- Container pool management with health checks
- Job queue with priority support
- Result caching with expiration
- Load balancing across containers
- Comprehensive logging
"""

from flask import Flask, request, jsonify, send_file
import requests
import threading
import queue
import time
import os
import logging
from datetime import datetime, timedelta
from collections import OrderedDict
import re

# ============================================
# CONFIGURATION
# ============================================

app = Flask(__name__)

# Container configuration from environment
CONTAINER_URLS = os.getenv("CONTAINER_URLS", "http://localhost:5001,http://localhost:5002,http://localhost:5003")
CONTAINERS = []

for i, url in enumerate(CONTAINER_URLS.split(",")):
    url = url.strip()
    if url:
        CONTAINERS.append({
            "url": url,
            "id": f"android-{i+1}",
            "busy": False,
            "healthy": True,
            "last_health_check": None,
            "jobs_completed": 0,
            "jobs_failed": 0
        })

# Worker configuration
WORKER_THREADS = int(os.getenv("WORKER_THREADS", "3"))
EXTRACTION_TIMEOUT = int(os.getenv("EXTRACTION_TIMEOUT", "180"))
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))

# Result caching
RESULT_EXPIRATION = int(os.getenv("RESULT_EXPIRATION", "3600"))  # 1 hour default
MAX_CACHED_RESULTS = int(os.getenv("MAX_CACHED_RESULTS", "1000"))

# Logging
LOG_DIR = os.getenv("LOG_PATH", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'orchestrator.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('orchestrator')

# ============================================
# JOB QUEUE & RESULT CACHE
# ============================================

job_queue = queue.Queue()
results_cache = OrderedDict()  # LRU-like cache
results_lock = threading.Lock()

# ============================================
# CONTAINER POOL
# ============================================

class ContainerPool:
    """Thread-safe container pool manager"""
    
    def __init__(self, containers):
        self.containers = containers
        self.lock = threading.Lock()
        self.stats = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0
        }
    
    def get_available_container(self):
        """Get an available healthy container using round-robin"""
        with self.lock:
            for container in self.containers:
                if not container["busy"] and container["healthy"]:
                    # Quick health check
                    if self._check_container_health(container):
                        container["busy"] = True
                        logger.info(f"Assigned container: {container['id']}")
                        return container
            return None
    
    def release_container(self, container_id, success=True):
        """Release a container back to the pool"""
        with self.lock:
            for container in self.containers:
                if container["id"] == container_id:
                    container["busy"] = False
                    if success:
                        container["jobs_completed"] += 1
                        self.stats["successful_jobs"] += 1
                    else:
                        container["jobs_failed"] += 1
                        self.stats["failed_jobs"] += 1
                    self.stats["total_jobs"] += 1
                    logger.info(f"Released container: {container_id} (success={success})")
                    break
    
    def _check_container_health(self, container):
        """Quick health check for a container"""
        try:
            response = requests.get(
                f"{container['url']}/health",
                timeout=HEALTH_CHECK_TIMEOUT
            )
            healthy = response.status_code == 200
            container["healthy"] = healthy
            container["last_health_check"] = datetime.utcnow().isoformat()
            return healthy
        except Exception as e:
            logger.warning(f"Health check failed for {container['id']}: {e}")
            container["healthy"] = False
            return False
    
    def check_all_containers(self):
        """Check health of all containers"""
        with self.lock:
            for container in self.containers:
                self._check_container_health(container)
    
    def get_status(self):
        """Get status of all containers"""
        with self.lock:
            return [
                {
                    "id": c["id"],
                    "url": c["url"],
                    "busy": c["busy"],
                    "healthy": c["healthy"],
                    "jobs_completed": c["jobs_completed"],
                    "jobs_failed": c["jobs_failed"],
                    "last_health_check": c["last_health_check"]
                }
                for c in self.containers
            ]

pool = ContainerPool(CONTAINERS)

# ============================================
# RESULT CACHE MANAGEMENT
# ============================================

def cache_result(job_id, result):
    """Store result in cache with expiration"""
    with results_lock:
        # Add expiration timestamp
        result["_expires_at"] = (datetime.utcnow() + timedelta(seconds=RESULT_EXPIRATION)).isoformat()
        result["_cached_at"] = datetime.utcnow().isoformat()
        
        # Remove oldest entries if cache is full
        while len(results_cache) >= MAX_CACHED_RESULTS:
            results_cache.popitem(last=False)
        
        results_cache[job_id] = result
        logger.debug(f"Cached result for job: {job_id}")


def get_cached_result(job_id):
    """Get result from cache, checking expiration"""
    with results_lock:
        if job_id in results_cache:
            result = results_cache[job_id]
            
            # Check expiration
            expires_at = datetime.fromisoformat(result.get("_expires_at", datetime.utcnow().isoformat()))
            if datetime.utcnow() > expires_at:
                del results_cache[job_id]
                logger.debug(f"Result expired for job: {job_id}")
                return None
            
            # Move to end for LRU
            results_cache.move_to_end(job_id)
            return result
        return None


def cleanup_expired_results():
    """Remove expired results from cache"""
    with results_lock:
        now = datetime.utcnow()
        expired_keys = []
        
        for job_id, result in results_cache.items():
            expires_at = datetime.fromisoformat(result.get("_expires_at", now.isoformat()))
            if now > expires_at:
                expired_keys.append(job_id)
        
        for key in expired_keys:
            del results_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired results")


# ============================================
# INPUT VALIDATION
# ============================================

def validate_package_name(package_name):
    """Validate Android package name format"""
    if not package_name:
        return False, "Package name is required"
    
    package_name = package_name.strip()
    
    # Extract from URL if provided
    url_match = re.search(r'id=([a-zA-Z0-9_.]+)', package_name)
    if url_match:
        package_name = url_match.group(1)
    
    if len(package_name) > 256:
        return False, "Package name too long"
    
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
    if not re.match(pattern, package_name):
        return False, "Invalid package name format"
    
    return True, package_name


# ============================================
# WORKER THREAD
# ============================================

def worker():
    """Background worker to process job queue"""
    while True:
        try:
            job_id, package = job_queue.get()
            logger.info(f"Processing job: {job_id}")
            
            # Get available container
            container = None
            wait_count = 0
            max_wait = 60  # Max 60 attempts (2 minutes)
            
            while container is None and wait_count < max_wait:
                container = pool.get_available_container()
                if container is None:
                    wait_count += 1
                    time.sleep(2)
            
            if container is None:
                logger.error(f"No container available for job: {job_id}")
                cache_result(job_id, {
                    "status": "failed",
                    "error": "No container available after timeout"
                })
                job_queue.task_done()
                continue
            
            # Process extraction
            try:
                logger.info(f"Extracting {package} on {container['id']}")
                
                response = requests.post(
                    f"{container['url']}/extract_apk",
                    json={"package": package},
                    timeout=EXTRACTION_TIMEOUT
                )
                
                data = response.json()
                
                if response.status_code == 200:
                    cache_result(job_id, {
                        "status": "completed",
                        "data": data,
                        "container": container["id"]
                    })
                    pool.release_container(container["id"], success=True)
                    logger.info(f"Job completed: {job_id}")
                else:
                    cache_result(job_id, {
                        "status": "failed",
                        "error": data.get("error", "Unknown error"),
                        "container": container["id"]
                    })
                    pool.release_container(container["id"], success=False)
                    logger.warning(f"Job failed: {job_id} - {data.get('error')}")
                    
            except requests.Timeout:
                cache_result(job_id, {
                    "status": "failed",
                    "error": f"Extraction timeout ({EXTRACTION_TIMEOUT}s)",
                    "container": container["id"]
                })
                pool.release_container(container["id"], success=False)
                logger.error(f"Job timeout: {job_id}")
                
            except Exception as e:
                cache_result(job_id, {
                    "status": "failed",
                    "error": str(e),
                    "container": container["id"] if container else None
                })
                if container:
                    pool.release_container(container["id"], success=False)
                logger.error(f"Job error: {job_id} - {e}")
            
            finally:
                job_queue.task_done()
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(1)


def health_check_worker():
    """Background worker for periodic health checks"""
    while True:
        try:
            pool.check_all_containers()
            cleanup_expired_results()
        except Exception as e:
            logger.error(f"Health check worker error: {e}")
        time.sleep(HEALTH_CHECK_INTERVAL)


# Start worker threads
for i in range(WORKER_THREADS):
    t = threading.Thread(target=worker, daemon=True, name=f"Worker-{i+1}")
    t.start()
    logger.info(f"Started worker thread: {t.name}")

# Start health check thread
health_thread = threading.Thread(target=health_check_worker, daemon=True, name="HealthCheck")
health_thread.start()
logger.info("Started health check thread")

# ============================================
# API ENDPOINTS
# ============================================

@app.route("/health", methods=["GET"])
def health():
    """Get orchestrator and container health status"""
    container_status = pool.get_status()
    
    healthy_count = sum(1 for c in container_status if c["healthy"])
    available_count = sum(1 for c in container_status if c["healthy"] and not c["busy"])
    
    return jsonify({
        "orchestrator": "healthy",
        "containers": container_status,
        "healthy_containers": healthy_count,
        "available_containers": available_count,
        "total_containers": len(container_status),
        "queue_size": job_queue.qsize(),
        "cached_results": len(results_cache),
        "stats": pool.stats,
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@app.route("/extract", methods=["POST"])
def extract():
    """Queue APK extraction job"""
    data = request.get_json() or {}
    package = data.get("package", "").strip()
    
    # Validate package name
    valid, result = validate_package_name(package)
    if not valid:
        return jsonify({"error": result}), 400
    
    package = result
    
    # Generate unique job ID
    job_id = f"{package}_{int(time.time() * 1000)}"
    
    # Check if already in cache (deduplication)
    for cached_job_id, cached_result in results_cache.items():
        if cached_job_id.startswith(package + "_"):
            if cached_result.get("status") == "completed":
                # Return cached result
                logger.info(f"Returning cached result for {package}")
                return jsonify({
                    "job_id": cached_job_id,
                    "status": "completed",
                    "cached": True,
                    **cached_result.get("data", {})
                }), 200
    
    # Add to queue
    job_queue.put((job_id, package))
    logger.info(f"Queued job: {job_id} (queue size: {job_queue.qsize()})")
    
    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "queue_position": job_queue.qsize(),
        "package": package
    }), 202


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    """Check job status"""
    result = get_cached_result(job_id)
    
    if result:
        # Return cached result
        response = {
            "job_id": job_id,
            **result
        }
        # Remove internal fields
        response.pop("_expires_at", None)
        response.pop("_cached_at", None)
        return jsonify(response), 200
    
    # Check if job is in queue
    # Note: We can't directly check queue contents, assume it's still processing
    return jsonify({
        "job_id": job_id,
        "status": "processing",
        "queue_size": job_queue.qsize()
    }), 200


@app.route("/download/<package>/<filename>", methods=["GET"])
def download(package, filename):
    """Download APK from any container that has it"""
    # Sanitize inputs
    valid, package = validate_package_name(package)
    if not valid:
        return jsonify({"error": "Invalid package name"}), 400
    
    if not re.match(r'^[a-zA-Z0-9._-]+\.apk$', filename):
        return jsonify({"error": "Invalid filename"}), 400
    
    # Try each container
    for container in CONTAINERS:
        if not container["healthy"]:
            continue
            
        try:
            response = requests.get(
                f"{container['url']}/download_apk/{package}/{filename}",
                stream=True,
                timeout=60
            )
            
            if response.status_code == 200:
                logger.info(f"Download from {container['id']}: {package}/{filename}")
                return response.content, 200, {
                    'Content-Type': 'application/vnd.android.package-archive',
                    'Content-Disposition': f'attachment; filename={package}_{filename}'
                }
        except Exception as e:
            logger.warning(f"Download failed from {container['id']}: {e}")
            continue
    
    return jsonify({"error": "File not found in any container"}), 404


@app.route("/packages", methods=["GET"])
def list_packages():
    """List packages from all containers"""
    all_packages = {}
    
    for container in CONTAINERS:
        if not container["healthy"]:
            continue
            
        try:
            response = requests.get(
                f"{container['url']}/list_packages",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                for pkg in data.get("packages", []):
                    pkg_name = pkg if isinstance(pkg, str) else pkg.get("package", "")
                    if pkg_name and pkg_name not in all_packages:
                        all_packages[pkg_name] = pkg
        except Exception as e:
            logger.warning(f"List packages failed from {container['id']}: {e}")
            continue
    
    return jsonify({
        "packages": list(all_packages.values()),
        "total_packages": len(all_packages)
    }), 200


@app.route("/stats", methods=["GET"])
def stats():
    """Get orchestrator statistics"""
    return jsonify({
        "queue_size": job_queue.qsize(),
        "cached_results": len(results_cache),
        "containers": pool.get_status(),
        "jobs": pool.stats,
        "config": {
            "worker_threads": WORKER_THREADS,
            "extraction_timeout": EXTRACTION_TIMEOUT,
            "result_expiration": RESULT_EXPIRATION,
            "max_cached_results": MAX_CACHED_RESULTS
        }
    }), 200


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("APK Extractor - Orchestrator")
    print("=" * 60)
    print(f"Containers: {len(CONTAINERS)}")
    for c in CONTAINERS:
        print(f"  - {c['id']}: {c['url']}")
    print(f"Worker Threads: {WORKER_THREADS}")
    print(f"Extraction Timeout: {EXTRACTION_TIMEOUT}s")
    print(f"Result Expiration: {RESULT_EXPIRATION}s")
    print("=" * 60)
    print("Starting server on port 8001...")
    
    app.run(host="0.0.0.0", port=8001, debug=os.getenv("DEBUG", "false").lower() == "true")
