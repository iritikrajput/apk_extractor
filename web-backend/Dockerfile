# APK Extractor - Web Backend Dockerfile

FROM python:3.11-slim

LABEL maintainer="APK Extractor Team"
LABEL description="Web backend for APK Extractor"

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY web_backend.py .
COPY templates/ templates/
COPY static/ static/

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_PATH=/app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run application
CMD ["python", "web_backend.py"]

