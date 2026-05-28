# J.A.R.V.I.S. API Reference

## Orchestrator Service (Port 8000)

### POST /chat
Send a text message to J.A.R.V.I.S.

**Request:**
```json
{
  "message": "Hello JARVIS",
  "session_id": "default",
  "emotion": "neutral",
  "image": null
}
```

**Response:**
```json
{
  "reply": "Hello! How can I help you today?",
  "session_id": "default",
  "emotion": "happy",
  "audio_url": null,
  "visemes": [],
  "actions_taken": [],
  "memory_updated": true,
  "processing_time_ms": 1234.56
}
```

### WS /ws
Bidirectional WebSocket connection.

**Message Types:**
- `chat` - text conversation
- `audio` - base64 audio for transcription
- `image` - base64 image for vision
- `command` - system commands
- `ping` / `pong` - keepalive

### GET /health
Service health check.

### GET /status
Full system status including token usage and active sessions.

## Memory Service (Port 8001)

### POST /store
Store a memory.

### POST /query
Query memories by semantic similarity.

### GET /palace
Get Memory Palace room map.

### GET /recent?limit=10
Get recent conversation history.

## Vision Service (Port 8002)

### POST /analyze
Analyze a base64 image. Returns objects, colors, faces, QR codes.

### GET /stream
WebSocket for live video stream analysis.

## Hearing Service (Port 8003)

### POST /transcribe
Transcribe base64 audio to text.

### GET /is-speaking
Check if speech is currently detected.

## Speech Service (Port 8004)

### POST /synthesize
Convert text to speech with emotion.

### POST /interrupt
Interrupt current TTS playback.

## Action Service (Port 8005)

### POST /send-email
### POST /create-event
### POST /web-search
### POST /control-light
### POST /set-temperature
### POST /open-app
### GET /system-info
