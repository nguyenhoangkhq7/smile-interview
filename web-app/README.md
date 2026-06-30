# Ditto — AI Mock Interview Platform Frontend

This is the frontend of the AI Mock Interview Platform built with Next.js (App Router, TypeScript) and styled with Vanilla CSS Modules. It connects with `matching-service` (Spring Boot) and `streaming-service` (Node.js/Socket.IO) to deliver an E2E interactive mock interview experience with a 3D avatar.

---

## 🚀 Quick Start: Running in Online Mode

To run the application with full real-time AI capabilities (ingestion, competency assessments, lipsync audio streaming, and voice transcriptions), follow these setup steps:

### 1. Start the Docker Infrastructure
Ensure the local PostgreSQL database, Redis cache, and services are running:
```bash
docker-compose up -d
```

### 2. Pull Ollama Embedding Weights
The Spring Boot `matching-service` requires embedding models to vectorize uploaded CVs and JDs:
```bash
# Pull the exact embedding model on your host system
ollama pull qwen3-embedding:4b
```

### 3. Ensure HuggingFace Model Access
The Speaches CPU container will automatically download Whisper and Piper TTS model weights. Ensure the docker host has stable internet access to complete these cache downloads:
*   **STT Model:** `Systran/faster-whisper-small`
*   **TTS Model:** `speaches-ai/piper-vi_VN-vais1000-medium`

---

## 🛠️ Local Development (Frontend)

### 1. Configuration
Create a `.env.local` file inside the `web-app` folder matching the `.env.example` setup:
```env
MATCHING_SERVICE_URL=http://localhost:8081
NEXT_PUBLIC_STREAMING_SERVICE_URL=http://localhost:8001
```

### 2. Run Dev Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to view the history dashboard (the landing redirect).

---

## 📁 Key Directories & Architecture
*   `src/app/`: Next.js App Router folders defining pages, layouts, and API proxy endpoints (such as `/api/matching/` to forward file uploads server-to-server).
*   `src/components/`: Reusable React components including the refactored controlled `DittoAvatarModule` and Three.js canvas-driving `DittoModel`.
*   `src/services/`: Isolated services layer. Includes `historyService.ts` (async browser history persistence), `cvJdMatching.ts` (API client), and `questionService.ts` (interviewer heuristic state machine).
