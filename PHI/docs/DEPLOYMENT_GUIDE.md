# J.A.R.V.I.S. Deployment Guide

## Prerequisites
- Docker 24+ and Docker Compose 2.20+
- 8GB+ RAM (16GB recommended for local LLM)
- NVIDIA GPU (optional, for GPU acceleration)

## Quick Start (Docker)

```bash
# Clone and enter directory
cd jarvis

# Configure
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker compose up -d

# Check logs
docker compose logs -f orchestrator

# Stop
docker compose down
```

## Manual Deployment

### Backend Services
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start each service in its own terminal
python -m backend.orchestrator.main
python -m backend.vision.service
python -m backend.hearing.service
python -m backend.speech.service
python -m backend.actions.service

# Start memory service (needs ChromaDB)
docker run -d -p 8000:8000 chromadb/chroma
python -m backend.memory.service
```

### Frontend
```bash
cd frontend
npm install

# Development
npm start

# Production build
npm run build
npx serve -s build
```

### Redis
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## API Keys Required

| Service | Key | Required? |
|---------|-----|-----------|
| OpenAI | OPENAI_API_KEY | For GPT-4 vision & Whisper API |
| ElevenLabs | ELEVENLABS_API_KEY | For premium TTS |
| SerpAPI | SERPAPI_API_KEY | For web search |
| Weather | WEATHER_API_KEY | For weather data |

## Scaling

### Horizontal Scaling
- Orchestrator: stateless, can run multiple instances behind load balancer
- Vision: GPU-enabled instances for real-time detection
- Memory: Single ChromaDB instance (can be clustered)

### Resource Requirements

| Service | CPU | RAM | GPU |
|---------|-----|-----|-----|
| Orchestrator | 1 core | 256MB | No |
| Vision | 2 cores | 2GB | Optional |
| Hearing | 2 cores | 2GB | No |
| Speech | 1 core | 1GB | No |
| Memory | 1 core | 1GB | No |
| Action | 1 core | 256MB | No |
| Frontend | 1 core | 512MB | No |
| Redis | 1 core | 256MB | No |
| ChromaDB | 1 core | 2GB | No |

## Monitoring

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health

# Logs
docker compose logs -f --tail=100

# Resource usage
docker stats
```
