# APK Extractor - API Documentation

Complete REST API reference for APK Extractor.

## Base URLs

| Service | URL | Description |
|---------|-----|-------------|
| Web Backend | `http://localhost:8000` | Main API endpoint |
| Orchestrator | `http://localhost:8001` | Direct orchestrator access |
| Device Agent | `http://localhost:5001` | Direct device agent access |

## Authentication

All API endpoints require authentication (when `AUTH_ENABLED=true`).

### Basic Authentication

```bash
curl -u username:password http://localhost:8000/api/extract
```

### Session Authentication

Login via web interface creates session cookie.

---

## Web Backend API

### Health Check

Check system health and device status.

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "device_id": "emulator-5554",
  "devices_count": 1,
  "mode": "single",
  "web_backend": "healthy",
  "device_info": {
    "android_version": "11",
    "model": "sdk_gphone_x86_64",
    "boot_completed": true
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Orchestrator Mode Response:**
```json
{
  "orchestrator": "healthy",
  "containers": [
    {
      "id": "android-1",
      "url": "http://localhost:5001",
      "busy": false,
      "healthy": true
    }
  ],
  "healthy_containers": 3,
  "available_containers": 2,
  "queue_size": 1,
  "mode": "orchestrator"
}
```

---

### Extract APK

Request APK extraction for a package.

**Endpoint:** `POST /api/extract`

**Request Body:**
```json
{
  "package": "com.whatsapp"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| package | string | Yes | Android package name or Play Store URL |

**Success Response (Single Device Mode):**

`HTTP 200 OK`
```json
{
  "status": "completed",
  "package": "com.whatsapp",
  "files": [
    {
      "filename": "base.apk",
      "path": "com.whatsapp/base.apk",
      "size": 45678901,
      "size_human": "43.56 MB",
      "hash": "a1b2c3d4e5f6...",
      "hash_algorithm": "SHA-256"
    },
    {
      "filename": "split_config.xxhdpi.apk",
      "path": "com.whatsapp/split_config.xxhdpi.apk",
      "size": 1234567,
      "size_human": "1.18 MB",
      "hash": "f6e5d4c3b2a1...",
      "hash_algorithm": "SHA-256"
    }
  ],
  "total_files": 2,
  "total_size": 46913468,
  "total_size_human": "44.74 MB",
  "extraction_time": "2024-01-15T10:31:45.000Z",
  "device": "emulator-5554"
}
```

**Success Response (Orchestrator Mode):**

`HTTP 202 Accepted`
```json
{
  "job_id": "com.whatsapp_1705312345678",
  "status": "queued",
  "queue_position": 2,
  "package": "com.whatsapp"
}
```

**Error Responses:**

`HTTP 400 Bad Request`
```json
{
  "error": "Invalid package name format"
}
```

`HTTP 404 Not Found`
```json
{
  "error": "App not installed. Please install from Play Store first.",
  "package": "com.example.notinstalled",
  "help": "Install the app manually, then retry extraction."
}
```

`HTTP 429 Too Many Requests`
```json
{
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 60
}
```

`HTTP 504 Gateway Timeout`
```json
{
  "error": "Extraction timeout. The app may be too large or the device is busy.",
  "package": "com.example.largeapp"
}
```

---

### Check Job Status

Check status of queued extraction job (orchestrator mode only).

**Endpoint:** `GET /api/status/{job_id}`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| job_id | string | Job ID from extract response |

**Queued Response:**
```json
{
  "job_id": "com.whatsapp_1705312345678",
  "status": "queued",
  "queue_size": 3
}
```

**Processing Response:**
```json
{
  "job_id": "com.whatsapp_1705312345678",
  "status": "processing"
}
```

**Completed Response:**
```json
{
  "job_id": "com.whatsapp_1705312345678",
  "status": "completed",
  "data": {
    "package": "com.whatsapp",
    "files": [...],
    "total_files": 2
  },
  "container": "android-1"
}
```

**Failed Response:**
```json
{
  "job_id": "com.whatsapp_1705312345678",
  "status": "failed",
  "error": "App not installed",
  "container": "android-1"
}
```

---

### Download APK

Download an extracted APK file.

**Endpoint:** `GET /api/download/{package}/{filename}`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| package | string | Package name |
| filename | string | APK filename (base.apk, split_1.apk, etc.) |

**Success Response:**

`HTTP 200 OK`
- Content-Type: `application/vnd.android.package-archive`
- Content-Disposition: `attachment; filename=com.whatsapp_base.apk`

**Error Response:**

`HTTP 404 Not Found`
```json
{
  "error": "File not found"
}
```

---

### List Packages

List all extracted packages.

**Endpoint:** `GET /api/packages`

**Response:**
```json
{
  "packages": [
    {
      "package": "com.whatsapp",
      "files": [
        {
          "filename": "base.apk",
          "size": 45678901,
          "size_human": "43.56 MB"
        }
      ],
      "total_size": 45678901,
      "total_size_human": "43.56 MB"
    }
  ],
  "total_packages": 1
}
```

---

## Device Agent API

Direct access to device agent (typically internal use only).

### Health Check

**Endpoint:** `GET /health`

### Extract APK

**Endpoint:** `POST /extract_apk`

### Download APK

**Endpoint:** `GET /download_apk/{package}/{filename}`

### List Packages

**Endpoint:** `GET /list_packages`

### Delete Package

**Endpoint:** `DELETE /delete_package/{package}`

---

## Orchestrator API

Direct access to orchestrator (typically internal use only).

### Health Check

**Endpoint:** `GET /health`

### Extract (Queue Job)

**Endpoint:** `POST /extract`

### Check Status

**Endpoint:** `GET /status/{job_id}`

### Download

**Endpoint:** `GET /download/{package}/{filename}`

### List Packages

**Endpoint:** `GET /packages`

### Statistics

**Endpoint:** `GET /stats`

**Response:**
```json
{
  "queue_size": 2,
  "cached_results": 15,
  "containers": [...],
  "jobs": {
    "total_jobs": 100,
    "successful_jobs": 95,
    "failed_jobs": 5
  },
  "config": {
    "worker_threads": 3,
    "extraction_timeout": 180,
    "result_expiration": 3600,
    "max_cached_results": 1000
  }
}
```

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 202 | Accepted (job queued) |
| 400 | Bad request (invalid input) |
| 401 | Authentication required |
| 404 | Not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable |
| 504 | Gateway timeout |

---

## Rate Limiting

Default limits (configurable via environment variables):
- 10 requests per 60 seconds per IP
- Headers included in response when limit approached

---

## Examples

### cURL Examples

```bash
# Health check
curl -u admin:apkextractor http://localhost:8000/api/health

# Extract APK
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -u admin:apkextractor \
  -d '{"package": "com.whatsapp"}'

# Download APK
curl -u admin:apkextractor \
  -o whatsapp_base.apk \
  http://localhost:8000/api/download/com.whatsapp/base.apk

# Check job status (orchestrator mode)
curl -u admin:apkextractor \
  http://localhost:8000/api/status/com.whatsapp_1705312345678
```

### Python Examples

```python
import requests

BASE_URL = "http://localhost:8000"
AUTH = ("admin", "apkextractor")

# Extract APK
response = requests.post(
    f"{BASE_URL}/api/extract",
    json={"package": "com.whatsapp"},
    auth=AUTH
)

if response.status_code == 200:
    data = response.json()
    for file in data["files"]:
        print(f"Downloading {file['filename']}...")
        
        # Download file
        dl_response = requests.get(
            f"{BASE_URL}/api/download/{data['package']}/{file['filename']}",
            auth=AUTH
        )
        
        with open(file["filename"], "wb") as f:
            f.write(dl_response.content)
        
        print(f"  Size: {file['size_human']}")
        print(f"  Hash: {file['hash']}")
```

### JavaScript Examples

```javascript
const BASE_URL = 'http://localhost:8000';
const headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Basic ' + btoa('admin:apkextractor')
};

// Extract APK
async function extractAPK(packageName) {
  const response = await fetch(`${BASE_URL}/api/extract`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ package: packageName })
  });
  
  return await response.json();
}

// Poll for status (orchestrator mode)
async function pollStatus(jobId) {
  while (true) {
    const response = await fetch(`${BASE_URL}/api/status/${jobId}`, { headers });
    const data = await response.json();
    
    if (data.status === 'completed' || data.status === 'failed') {
      return data;
    }
    
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
}
```

