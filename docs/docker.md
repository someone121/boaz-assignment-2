# Docker

How SmartClass AI is packaged and run with Docker and Docker Compose.

See also: [backend.md](backend.md) · [frontend.md](frontend.md) · [../README.md](../README.md)

---

## 1. Quick start

```bash
cp .env.example .env          # optional: add OPENAI_API_KEY, change SECRET_KEY
docker compose up --build -d
```

Open `http://localhost:8000/`. Log in as the default lecturer `111111111` / `admin123`, or as any student ID.

| Task | Command |
| :--- | :--- |
| Follow logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart (picks up code edits, see §4) | `docker compose restart` |
| Rebuild after changing `requirements.txt` or `Dockerfile` | `docker compose up --build -d` |
| Shell inside the container | `docker compose exec smartclass-app bash` |
| Run the tests inside the container | `docker compose exec smartclass-app python -m pytest -q` |
| Health check | `curl http://localhost:8000/api/health` |

The first build takes several minutes: it downloads CPU-only PyTorch, Ultralytics and the YOLO weights. Later builds reuse the cached layers unless `requirements.txt` changes.

---

## 2. The image ([Dockerfile](../Dockerfile))

| Step | What and why |
| :--- | :--- |
| `FROM python:3.11-slim` | Debian slim, **not** Alpine (PyTorch/OpenCV wheels need glibc). |
| `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app` | No `.pyc` files, logs appear immediately, `app` is importable. |
| `pip install --upgrade pip setuptools wheel` | Recent pip to install binary wheels. |
| `apt-get install libgl1 libglib2.0-0 ffmpeg git` | Libraries OpenCV, media handling, and `git clone` for homework review need. |
| `COPY requirements.txt` → install **CPU-only** `torch torchvision` → `pip install -r requirements.txt` | Installing CPU torch first stops Ultralytics from pulling the much larger CUDA build. Copying only `requirements.txt` first means code changes don't redo this step. |
| `python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` | Downloads the YOLOv8n weights into `/app` **at build time**, so the container starts offline. |
| `COPY . .` | App source, `static/`, `tests/`. Files listed in [.dockerignore](../.dockerignore) are skipped: venvs, caches, local DBs, uploads, reports, `.git`, `*.pt`, `.env`. |
| `mkdir -p /app/data /app/uploads /app/reports` | Mount points for the volumes. |
| `EXPOSE 8000` + `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000` | **One worker** (see §5). |

In the container, uploaded classroom **images** and **videos** are processed by real YOLOv8n + ByteTrack (videos are sampled via OpenCV every `VIDEO_SAMPLE_INTERVAL_SECONDS` seconds, reporting `detector_mode: "yolo_video"`). `ffmpeg` and `git` are installed for audio extraction and GitHub homework cloning. **Audio/video transcription in Docker requires `OPENAI_API_KEY`** (Whisper API), as `faster-whisper` is not bundled in `requirements.txt` to keep the image lean; `.vtt`/`.srt`/`.txt` transcripts work offline.

---

## 3. Compose ([docker-compose.yml](../docker-compose.yml))

One service, `smartclass-app` (container name `smartclass_ai`), on port **8000:8000**, with `restart: unless-stopped`.

### Environment

| Variable | Value in compose | Change it by |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./data/smartclass.db` (inside the `data` volume) | editing compose |
| `OPENAI_API_KEY` | `${OPENAI_API_KEY:-}` | setting it in `.env` (required in Docker for audio/video Whisper transcription & LLM reviews) |
| `SECRET_KEY` | `${SECRET_KEY:-supersecret_kiss_key}` | setting it in `.env` |
| `PUBLIC_BASE_URL` | `${PUBLIC_BASE_URL:-}` | setting it in `.env` (e.g. `http://192.168.1.42:8000`) so QRs use LAN IP while lecturer uses `localhost` for webcam |
| `DEMO_MODE` | *(unset / false)* | set `DEMO_MODE=true` to return preview numbers on empty session reports |
| `VIDEO_SAMPLE_INTERVAL_SECONDS` | `5` | OpenCV sampling interval for uploaded attendance videos |
| `DEFAULT_LECTURER_ID` / `_NAME` / `_PASSWORD` | `111111111` / `Default Lecturer` / `admin123` | **editing compose** (hard-coded there, so the values in `.env` are ignored) |

Compose reads `.env` only to fill in `${...}` placeholders. It is not passed to the container as a whole. `APP_HOST` / `APP_PORT` in `.env.example` are not used.

Notes on the default lecturer:

- It is created only if that ID doesn't exist yet. Changing the password later does not update an existing account.
- To start over, delete the database (§6).

### Volumes

| Host | Container | Contents |
| :--- | :--- | :--- |
| `./data` | `/app/data` | SQLite database (`smartclass.db` + `-wal` / `-shm`) |
| `./uploads` | `/app/uploads` | Uploaded Excel banks and lecture files |
| `./reports` | `/app/reports` | Exported attendance CSVs |
| `./app` | `/app/app` | **Source code** (development mount) |
| `./static` | `/app/static` | **Frontend** (development mount) |

These are bind mounts to folders in the project, so the data survives `docker compose down` and rebuilds.

---

## 4. Development vs. production

The compose file is set up for **development**: `./app` and `./static` are mounted over the code baked into the image.

- **Frontend edits** (`static/`) appear on the next browser reload.
- **Backend edits** (`app/`) need `docker compose restart`, because uvicorn runs without `--reload`.
- `tests/` is **not** mounted. Tests inside the container use the copy from the last build; run them on the host or rebuild.

For a **production / demo server**:

1. Remove the `./app` and `./static` volume lines so the container runs exactly what was built.
2. Set a strong `SECRET_KEY` in `.env`, and a new `DEFAULT_LECTURER_PASSWORD` in compose, **before the first start**. The password only applies when the account is created, and changing `SECRET_KEY` later breaks every existing lecturer password.
3. Put the app behind HTTPS (§5). The webcam (`getUserMedia`) only works on HTTPS or `localhost`.

---

## 5. Hosting notes

- **Single worker is required.**
  - WebSocket connections (`ConnectionManager`) and ByteTrack track state (`AttendanceManager`) live in process memory.
  - With several workers, a student's vote could be handled by a worker that doesn't hold the lecturer's socket.
  - Don't add `--workers N`, and don't run more than one replica.
- **HTTPS / WebSockets.** Behind a reverse proxy (Nginx, Caddy, Render, Railway…):
  - forward the WebSocket upgrade for `/ws/`;
  - the frontend switches to `wss://` automatically on HTTPS pages.
- **No camera in the cloud.** A server has no `/dev/video0`. Use the dashboard's **Start Webcam Stream** (the browser sends frames) or upload images.
- **QR codes & Webcam together (`PUBLIC_BASE_URL`):** `getUserMedia` (webcam) only works on `https://` or `localhost`, while student phones need the machine's LAN IP. Set `PUBLIC_BASE_URL=http://<LAN_IP>:8000` in `.env` so the lecturer can open `http://localhost:8000/lecturer_dashboard` (webcam works) while all generated QR codes point phones to `http://<LAN_IP>:8000/...`.
- **Image size** is a few GB, mostly PyTorch. The service runs fine on a small CPU-only VM.

---

## 6. Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| Port 8000 already in use | Stop the other process, or change the mapping to `"8080:8000"` and use port 8080. |
| Default lecturer password doesn't work | The account already existed with an older password, or `SECRET_KEY` changed. Reset the DB (below). |
| Start over with a clean database | `docker compose down`, delete `data/smartclass.db*`, `docker compose up -d`. It is recreated and re-seeded on start. |
| Code changes not visible | Frontend: hard-reload the browser. Backend: `docker compose restart`. Dependencies: `docker compose up --build -d`. |
| Phones can't open the QR link | Open the dashboard via the host's LAN IP, check the firewall allows port 8000, and make sure the phone is on the same network. |
| Permission errors on `data/` (Linux) | The container runs as root; `sudo chown -R $USER data uploads reports` to edit the files from the host. |
| Build fails while downloading torch / YOLO weights | Network issue during build; run `docker compose build` again. |
