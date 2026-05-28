# J.A.R.V.I.S. — Just A Rather Very Intelligent System

A modular, production-ready AI personal assistant with vision, hearing, speech, memory (Memory Palace), and action capabilities.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│ Orchestrator │────▶│    Memory    │
│  (React 3D)  │◀────│  (FastAPI)   │◀────│  (ChromaDB)  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │  Vision  │   │ Hearing  │   │  Speech  │
      │ (YOLOv8) │   │(Whisper) │   │(ElevenLabs)
      └──────────┘   └──────────┘   └──────────┘
                           │
                     ┌──────────┐
                     │ Actions  │
                     │ (MQTT++) │
                     └──────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- API keys (optional): OpenAI, ElevenLabs, SerpAPI

### Setup

```bash
git clone <repo>
cd jarvis

# Copy environment config
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker compose up -d

# Or run locally (services individually):
pip install -r requirements.txt
python -m backend.orchestrator.main &
python -m backend.vision.service &
python -m backend.hearing.service &
python -m backend.speech.service &
python -m backend.actions.service &

# Frontend
cd frontend && npm install && npm start
```

### CLI Usage

```bash
# Check status
python scripts/cli.py status

# Chat
python scripts/cli.py chat "Hello JARVIS"

# Memory
python scripts/cli.py memory query "what did I do yesterday"
python scripts/cli.py memory store "Meeting with John at 3pm" --room Work
python scripts/cli.py memory palace

# Test TTS
python scripts/cli.py speak "Hello world" --emotion happy

# Service status
python scripts/cli.py service orchestrator status
```

## Architecture Details

### Orchestrator
Central brain using LangChain-like agent with ReAct loop. Routes requests to sub-services via Redis Pub/Sub. Supports multiple LLM providers: OpenAI GPT-4, Anthropic Claude, DeepSeek, OpenRouter, local models.

### Vision Service
- Object detection: YOLOv8 nano
- Face recognition: face_recognition library
- QR/barcode: pyzbar
- Color detection: K-means clustering on frames
- Scene classification

### Hearing Service
- Always-on mic capture via PyAudio
- Voice activity detection: WebRTC VAD
- Speech-to-text: OpenAI Whisper (local or API)
- Wake word: "Jarvis" / "Hey Jarvis"

### Speech Service
- TTS: ElevenLabs (primary), Coqui TTS (fallback), gTTS (last resort)
- 8 emotions: neutral, happy, serious, excited, calm, angry, sad, whisper
- Human-like speech: filler words, varied pacing, natural pauses
- Viseme generation for avatar lip sync

### Memory Palace
- 20 themed rooms (Personal, Work, Technology, Health, etc.)
- ChromaDB vector storage
- Episodic, semantic, procedural, and spatial memory types
- Automatic memory consolidation and retrieval

### Actions
- Email (SMTP)
- Calendar (Google Calendar API)
- Smart Home (MQTT / Home Assistant REST API)
- Web search (SerpAPI / DuckDuckGo)
- System commands (open apps, screenshots)
- File system (read, write, search files)

## API Endpoints

| Service | Endpoint | Description |
|---------|----------|-------------|
| Orchestrator | POST /chat | Send message |
| Orchestrator | WS /ws | Bidirectional WebSocket |
| Memory | POST /store | Store memory |
| Memory | POST /query | Query memory |
| Memory | GET /palace | Memory palace map |
| Vision | POST /analyze | Analyze image |
| Hearing | POST /transcribe | Transcribe audio |
| Speech | POST /synthesize | Synthesize speech |
| Action | POST /send-email | Send email |

## License
MIT
