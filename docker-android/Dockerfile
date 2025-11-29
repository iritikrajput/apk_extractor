FROM budtmo/docker-android:emulator_11.0

# Install Python and dependencies
USER root
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy device agent
COPY device_agent.py /app/
COPY requirements.txt /app/
COPY start.sh /app/

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Create pulls directory
RUN mkdir -p /app/pulls && chmod 777 /app/pulls

# Make startup script executable
RUN chmod +x /app/start.sh

# Expose device agent port
EXPOSE 5001

# Expose ADB port
EXPOSE 5555

# Set environment variables
ENV DEVICE="emulator-5554"
ENV APPIUM=false
ENV WEB_VNC=false

# Start script
CMD ["/app/start.sh"]
