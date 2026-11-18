# Docker & Cloud Deployment Specification

**Project:** SmartClass AI  
**Goal:** Package the FastAPI backend, YOLOv8/OpenCV vision pipeline, SQLite database, and static frontend into a portable, production-ready Docker container for cloud hosting (Render, Railway, AWS EC2, or DigitalOcean).

---

## 1. Containerization Requirements
1. **System Dependencies (Linux):** OpenCV (`opencv-python-headless`) and Ultralytics YOLOv8 require OS-level shared libraries (`libgl1`, `libglib2.0-0`) inside the container.
2. **CPU-Optimized PyTorch:** To keep the Docker image lightweight (< 1.5 GB) and fast to deploy on standard cloud VMs without GPUs, install the CPU-only wheel of PyTorch before installing `ultralytics`.
3. **Model Caching:** Pre-download `yolov8n.pt` during the `docker build` phase so the container starts immediately without downloading weights at runtime.
4. **Data Persistence:** Mount external Docker volumes for SQLite (`smartclass.db`) and uploaded media/reports (`uploads/`, `reports/`) so data survives container restarts.

---

## 2. `Dockerfile` Blueprint
```dockerfile
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by OpenCV & media processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to minimize image size
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache YOLOv8n weights inside the image
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copy application source code and static frontend
COPY . .

# Create directories for persistent volumes
RUN mkdir -p /app/data /app/uploads /app/reports

EXPOSE 8000

# Run FastAPI with Uvicorn (single worker to preserve in-memory WebSocket & YOLO track state)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. `docker-compose.yml` Blueprint
```yaml
version: "3.9"

services:
  smartclass-app:
    build: .
    container_name: smartclass_ai
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/smartclass.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SECRET_KEY=${SECRET_KEY:-supersecret_kiss_key}
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
      - ./reports:/app/reports
    restart: unless-stopped
```

---

## 4. Important Cloud & Deployment Considerations
1. **Single Worker Mandate (`--workers 1`):** Because `AttendanceManager` holds active `ByteTrack` trajectories in memory and `ConnectionManager` manages active WebSocket sockets in memory, Uvicorn must run with a single worker process (`workers=1`).
2. **Webcam vs. Video/Image Upload in the Cloud:** When deployed to a remote cloud server, the container has no physical USB webcam attached (`/dev/video0` does not exist). Therefore, the `/api/attendance/frame` endpoint must accept uploaded video files (`.mp4`), sample classroom images (`.jpg`), or WebRTC/Canvas base64 frames streamed from the lecturer's browser webcam.
3. **HTTPS & Secure WebSockets (`wss://`):** When hosted behind a cloud reverse proxy (Nginx, Caddy, Render, Railway), the frontend `ws.js` must dynamically detect `window.location.protocol === 'https:'` and switch from `ws://` to `wss://` automatically.