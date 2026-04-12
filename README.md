# FRIDAY

FRIDAY is a local-first multi-agent AI operating system. All reasoning runs on local models through Ollama. Internet access is treated as a tool, not as a dependency for intelligence.

## What This Repo Contains

- `core/`: runtime config, Ollama client, hybrid intelligence router, voice session manager, orchestration, realtime presence state, and event bus
- `agents/`: planner, executor, debug, memory, web, system, vision, and voice agents
- `tools/`: shell, Python, filesystem, browser, web, image, voice, and system tool adapters
- `memory/`: Chroma-backed semantic memory with pluggable embeddings
- `web_agent/`: higher-level search, scrape, and summarize workflow
- `system_control/`: system action helpers
- `api/`: FastAPI REST and WebSocket entrypoints
- `frontend-3d-core/`: primary voice-first plasma core interface with backend-driven audio streaming
- `frontend-particles/`: alternate lightweight Three.js realtime particle presence interface
- `frontend-antigravity/`: alternate command-first frontend
- `logs/`: runtime logs and task history

## Core Characteristics

- Local intelligence only: Ollama for all LLM inference
- Multi-agent orchestration with structured JSON messages
- Async task queue with retry and debug flow
- Persistent memory through Chroma
- Web-aware execution through dedicated web tooling
- Permission-gated filesystem, shell, and app control
- Realtime presence state broadcast over WebSockets
- Dedicated voice session socket for PCM uplink and streamed TTS downlink
- Prompt evolution store that can promote higher-scoring prompt variants over time
- Triple frontend mode: 3d-core, particles, or antigravity

## Requirements

- Windows 10/11
- Python 3.11+
- Node.js 20+
- npm
- Ollama

Optional local model add-ons:

- Stable Diffusion weights for image generation
- Faster-Whisper models for speech-to-text
- `pyttsx3` or Piper-compatible local TTS setup

## One-Click Launch

Run:

```bat
launch_friday.bat
```

The launcher will:

- create or reuse `.venv`
- install backend Python dependencies
- install Playwright Chromium
- install frontend npm dependencies
- start Ollama if needed
- pull the configured local models
- launch the backend API
- launch the selected frontend

Default frontend mode is `3d-core`. To switch:

```env
FRIDAY_FRONTEND_MODE=antigravity
```

## Manual Setup

### 1. Backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev,embeddings,vision,voice]
playwright install chromium
```

### 2. Ollama models

```powershell
ollama serve
ollama pull deepseek-r1:8b
ollama pull mistral:7b
```

### 3. Frontend dependencies

```powershell
cd frontend-3d-core
npm install
cd ..
cd frontend-particles
npm install
cd ..\frontend-antigravity
npm install
cd ..
```

### 4. Configuration

```powershell
Copy-Item .env.example .env
```

Important variables:

- `FRIDAY_HOST` / `FRIDAY_PORT`
- `FRIDAY_FRONTEND_MODE`
- `FRIDAY_3D_CORE_HOST` / `FRIDAY_3D_CORE_PORT`
- `FRIDAY_PARTICLES_PORT`
- `FRIDAY_ANTIGRAVITY_PORT`
- `FRIDAY_PRIMARY_MODEL`
- `FRIDAY_FAST_MODEL`
- `FRIDAY_STABLE_DIFFUSION_MODEL_PATH`
- `FRIDAY_PIPER_MODEL_PATH`

### 5. Run backend

```powershell
friday-api
```

### 6. Run a frontend

3D core interface:

```powershell
cd frontend-3d-core
$env:VITE_FRIDAY_API_URL="http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1 --port 3001
```

Particle interface:

```powershell
cd frontend-particles
$env:VITE_FRIDAY_API_URL="http://127.0.0.1:8000"
npm run dev
```

Antigravity interface:

```powershell
cd frontend-antigravity
$env:VITE_FRIDAY_API_URL="http://127.0.0.1:8000"
npm run dev
```

## API and Realtime

- REST API: `http://127.0.0.1:8000/api`
- Health: `GET /api/health`
- Run objective immediately: `POST /api/objectives/run`
- Queue objective: `POST /api/objectives/submit`
- Presence state: `GET /api/state`
- WebSocket stream: `ws://127.0.0.1:8000/ws/presence`
- Voice session stream: `ws://127.0.0.1:8000/ws/session`

Example objective:

```bash
curl -X POST http://127.0.0.1:8000/api/objectives/run \
  -H "Content-Type: application/json" \
  -d "{\"objective\":\"Search for local OCR libraries, compare them, and summarize the best option for offline deployment.\"}"
```

## 3D Core Interface

The primary frontend is a full-screen voice-only plasma core. It includes:

- backend-owned voice sessions over WebSockets
- continuous microphone capture with client-side VAD and barge-in
- streamed local TTS playback from the backend
- GPU particle simulation, plasma shell, and orbiting wisps driven by AI state
- minimal HUD overlays for mode, transcript, and transport status

## Particle Interface

The alternate particle frontend remains available and includes:

- 6200 GPU-rendered particles
- shader-driven state transitions for idle, listening, thinking, responding, and error
- audio-reactive motion from the browser microphone
- subtle text-only interaction instead of dashboard controls
- WebSocket-driven realtime state and agent activity

## Antigravity Interface

The alternate frontend is a command-first surface intended for workflow steering and inspection while using the same backend runtime and WebSocket stream.

## Voice and Vision

### Voice

- STT: Faster-Whisper through the local voice tool
- TTS: `pyttsx3` by default

### Vision

Set `FRIDAY_STABLE_DIFFUSION_MODEL_PATH` to a local model folder. The vision tool supports prompt-to-image and image-to-image workflows.

## Security Model

- Internet access only through web tools and the web agent
- Filesystem access restricted to approved roots
- Destructive shell commands blocked by default
- Application launching disabled unless explicitly enabled
- All task runs and outcomes logged under `logs/`

## Notes

- FRIDAY is designed as a production-grade foundation, not a toy chatbot wrapper.
- Some optional subsystems still require local weights or runtime binaries to be present on the host machine.
- The particle frontend is meant to feel alive, while the antigravity frontend is meant to feel operational.
