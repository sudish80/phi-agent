<p align="center">
  <img src="architecture.svg" alt="PHI Agent Architecture" width="100%"/>
</p>

# PHI — J.A.R.V.I.S. AI Agent

Your personal AI assistant with voice, vision, memory, and 30+ built-in tools. Built with FastAPI + LLM, fully self-hosted.

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logo=chromadb&logoColor=white" alt="ChromaDB"/>
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/WebSocket-4A154B?style=for-the-badge&logo=websocket&logoColor=white" alt="WebSocket"/>
</p>

---

## Training & Deployment Pipeline

<p align="center">
  <img src="pipeline.svg" alt="Training Pipeline" width="100%"/>
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **Voice Input** | Whisper ASR with VAD, wake-word detection, speaker diarization (pyannote) |
| **Voice Output** | gTTS, Coqui TTS with emotion, auto language detection |
| **Vision** | OpenCV, YOLO object detection, face recognition (dlib), OCR (Tesseract/EasyOCR) |
| **Memory** | ChromaDB vector store, conversation history, long-term semantic recall |
| **Desktop Control** | pyautogui — click, type, screenshot, app management |
| **Web Tools** | Scrapy scraping, aiohttp downloads, browser automation (Selenium/Playwright) |
| **File Processing** | PDF (PyMuPDF), DOCX (python-docx), XLSX (openpyxl), CSV, ZIP |
| **Git Integration** | GitPython — commits, branches, status, diffs |
| **Music** | Spotify API integration (play, pause, search, playlists) |
| **Google APIs** | Gmail, Calendar, Drive |
| **Smart Home** | MQTT IoT control (lights, devices) |
| **Task Scheduler** | APScheduler — cron jobs, interval, one-shot tasks |
| **Web UI** | React-based dashboard |
| **Desktop App** | Electron wrapper |
| **WebSocket** | Real-time streaming responses |
| **Docker** | Full Docker Compose stack |
| **Prometheus** | Metrics and monitoring |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, uvicorn |
| LLM | OpenAI GPT-4, Anthropic Claude |
| Vector DB | ChromaDB (persistent) |
| Cache | Redis (pub/sub, session cache) |
| Speech | Whisper, gTTS, Coqui TTS |
| Vision | OpenCV, YOLO, dlib, Tesseract |
| Web | Scrapy, aiohttp, Selenium, Playwright |
| Desktop | pyautogui, Electron |
| Scheduler | APScheduler |
| Monitoring | Prometheus, structlog |
| Deploy | Docker Compose, Railway, local |

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
docker compose up -d
```

### Option 2: Local

```bash
# Backend
cd PHI
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run dev
```

Set environment variables:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_HOST=localhost
REDIS_HOST=localhost
```

---

## Project Structure

```
phi-agent/
├── PHI/                        # Core agent
│   ├── core/                   # Brain, memory, tools
│   ├── capabilities/           # Vision, hearing, speech
│   ├── integrations/           # Spotify, Google, MQTT
│   ├── api/                    # FastAPI routes
│   ├── web/                    # WebSocket server
│   ├── scheduler/              # Task scheduler
│   ├── monitor/                # Prometheus metrics
│   ├── utils/                  # Helpers
│   └── requirements.txt
├── frontend/                   # React Web UI
│   └── package.json
├── electron/                   # Desktop app
├── docker-compose.yml
└── README.md
```

---

## Tool Reference (30+ Built-in)

| Tool | Description |
|------|-------------|
| `web_search` | Search the internet |
| `web_scrape` | Scrape any website |
| `web_download` | Download files from URLs |
| `browser` | Selenium/Playwright automation |
| `pdf_read` | Extract text from PDFs |
| `docx_read` | Read Word documents |
| `xlsx_read` | Read Excel spreadsheets |
| `zip_extract` | Extract ZIP archives |
| `screenshot` | Capture screen |
| `ocr` | Text recognition from images |
| `face_detect` | Face detection & recognition |
| `object_detect` | YOLO object detection |
| `spotify` | Music playback control |
| `google_email` | Read/send Gmail |
| `google_calendar` | Manage calendar |
| `google_drive` | File management |
| `mqtt_publish` | IoT device control |
| `git_*` | Full git operations |
| `file_*` | File system operations |
| `code_execute` | Run Python code |
| `reminder` | Set reminders |
| `weather` | Weather lookup |
| `translate` | Language translation |
| `math` | Scientific calculations |
