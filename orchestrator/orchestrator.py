from flask import Flask, request, jsonify
import requests
import threading
import queue
import time

app = Flask(__name__)

# Container pool configuration
CONTAINERS = [
    {"url": "http://localhost:5001", "id": "android-1", "busy": False},
    {"url": "http://localhost:5002", "id": "android-2", "busy": False},
    {"url": "http://localhost:5003", "id": "android-3", "busy": False},
]

# Job queue
job_queue = queue.Queue()
results_cache = {}

class ContainerPool:
    def __init__(self, containers):
        self.containers = containers
        self.lock = threading.Lock()
    
    def get_available_container(self):
        """Get an available container from the pool"""
        with self.lock:
            for container in self.containers:
                if not container["busy"]:
                    # Check health
                    try:
                        r = requests.get(f"{container['url']}/health", timeout=5)
                        if r.status_code == 200:
                            container["busy"] = True
                            return container
                    except:
                        continue
            return None
    
    def release_container(self, container_id):
        """Release a container back to the pool"""
        with self.lock:
            for container in self.containers:
                if container["id"] == container_id:
                    container["busy"] = False
                    break

pool = ContainerPool(CONTAINERS)

def worker():
    """Background worker to process job queue"""
    while True:
        try:
            job_id, package = job_queue.get()
            
            # Get available container
            container = None
            while container is None:
                container = pool.get_available_container()
                if container is None:
                    time.sleep(2)  # Wait for container
            
            # Process extraction
            try:
                r = requests.post(
                    f"{container['url']}/extract_apk",
                    json={"package": package},
                    timeout=120
                )
                
                results_cache[job_id] = {
                    "status": "completed" if r.status_code == 200 else "failed",
                    "data": r.json(),
                    "container": container["id"]
                }
            except Exception as e:
                results_cache[job_id] = {
                    "status": "failed",
                    "error": str(e)
                }
            finally:
                pool.release_container(container["id"])
                job_queue.task_done()
        
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(1)

# Start worker threads
for _ in range(3):
    t = threading.Thread(target=worker, daemon=True)
    t.start()

@app.route("/health", methods=["GET"])
def health():
    """Check orchestrator and container health"""
    container_status = []
    
    for container in CONTAINERS:
        try:
            r = requests.get(f"{container['url']}/health", timeout=3)
            status = r.json() if r.status_code == 200 else {"status": "unhealthy"}
        except:
            status = {"status": "unreachable"}
        
        container_status.append({
            "id": container["id"],
            "url": container["url"],
            "busy": container["busy"],
            **status
        })
    
    return jsonify({
        "orchestrator": "healthy",
        "containers": container_status,
        "queue_size": job_queue.qsize()
    }), 200

@app.route("/extract", methods=["POST"])
def extract():
    """Queue APK extraction job"""
    package = request.json.get("package")
    if not package:
        return jsonify({"error": "Missing package name"}), 400
    
    # Generate job ID
    job_id = f"{package}_{int(time.time())}"
    
    # Add to queue
    job_queue.put((job_id, package))
    
    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "queue_position": job_queue.qsize()
    }), 202

@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    """Check job status"""
    if job_id in results_cache:
        return jsonify(results_cache[job_id]), 200
    else:
        # Check if still in queue
        return jsonify({
            "status": "queued",
            "job_id": job_id
        }), 200

@app.route("/download/<package>/<filename>", methods=["GET"])
def download(package, filename):
    """Proxy download from any available container"""
    for container in CONTAINERS:
        try:
            r = requests.get(
                f"{container['url']}/download_apk/{package}/{filename}",
                stream=True,
                timeout=10
            )
            if r.status_code == 200:
                return r.content, 200, {
                    'Content-Type': 'application/vnd.android.package-archive',
                    'Content-Disposition': f'attachment; filename={filename}'
                }
        except:
            continue
    
    return jsonify({"error": "File not found in any container"}), 404

if __name__ == "__main__":
    print("Starting Orchestrator...")
    app.run(host="0.0.0.0", port=8001)
