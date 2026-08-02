# Project Memory & Architectural Decisions

## System Overview
- **Project Name:** YouTube Automation MVP (`youtube-automation`)
- **Primary Goal:** Fully automated faceless YouTube Shorts pipeline: Idea → Script → Voice → Footage → Assembly → SEO → Upload.
- **Target Platform:** YouTube Shorts (9:16, ≤60 sec) primary.
- **Deployment:** Oracle Cloud Free Tier — ARM Ampere A1 (4 OCPUs, 24GB RAM), Ubuntu 22.04.

## Tech Stack
- **Backend:** Python 3.11, FastAPI (REST API + background tasks), APScheduler (cron)
- **UI:** Streamlit (with nginx reverse proxy + Let's Encrypt SSL)
- **LLM:** Groq API / Llama 3.3 (primary), Gemini Flash (idea scoring), Ollama (fallback)
- **TTS:** Kokoro TTS (Apache 2.0, local, CPU-capable) — single narrator voice `af_heart`
- **Captions:** faster-whisper (word-level timestamps)
- **Footage:** Pexels API + Pixabay API (unified search, dual fallback)
- **Video:** MoviePy + FFmpeg (9:16, Ken Burns, word-highlight captions, progress bar, music)
- **Database:** SQLite + SQLAlchemy (jobs, trends, history, asset cache, quota)
- **Upload:** YouTube Data API v3 + `google-api-python-client` (OAuth 2.0)
- **Base Repo:** Fork of `harry0703/MoneyPrinterTurbo`

## Architectural Decision Records (ADRs)
- **ADR-001 (2026-08-02):** Adopt RPI Workflow with explicit approval gates.
- **ADR-002 (2026-08-02):** Use Kokoro TTS (Apache 2.0) over edge-tts (blocked by Microsoft) and ElevenLabs (paid). No cost, commercial OK, near-ElevenLabs quality.
- **ADR-003 (2026-08-02):** Multi-source Idea Explorer Agent (Google Trends RSS + YouTube Trending API + Reddit PRAW + HackerNews) → Gemini Flash scoring.
- **ADR-004 (2026-08-02):** Semi-dark-mode automation: confidence score ≥ 0.80 → auto-approve; else flag for human review in Streamlit UI.
- **ADR-005 (2026-08-02):** SQLite for all persistence (jobs, trends, history, asset cache, quota tracking) — simple, no separate DB service needed.
- **ADR-006 (2026-08-02):** Oracle Cloud Free Tier (ARM) as deployment target — 4 OCPUs + 24GB RAM, completely free, sufficient for Kokoro CPU inference + FFmpeg rendering.
- **ADR-007 (2026-08-02):** Originality loop via TF-IDF cosine similarity against published video history (YouTube API). Threshold: >70% similarity → reject topic.
