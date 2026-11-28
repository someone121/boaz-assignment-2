# 1. Use a standard slim image (NOT alpine) pinned to 3.11 for best ML compatibility
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 2. Upgrade pip and install build dependencies FIRST
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 3. Install necessary system dependencies for OpenCV, YOLO, media processing, and git cloning
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# 4. Install CPU-only PyTorch and Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# 5. Pre-cache YOLOv8n weights inside the image
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 6. Copy application source code (including app/ and static/) into /app
COPY . .

# 7. Ensure persistent runtime directories exist
RUN mkdir -p /app/data /app/uploads /app/reports

EXPOSE 8000

# Single worker preserves in-memory WebSocket & ByteTrack state
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
