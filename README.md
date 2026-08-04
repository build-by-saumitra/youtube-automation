---
title: YouTube Automation
emoji: 🎬
colorFrom: red
colorTo: gray
sdk: streamlit
sdk_version: 1.38.0
app_file: ui/streamlit_app.py
pinned: false
---
# 🎬 YouTube Automation Pipeline

**Fully automated, end-to-end YouTube Shorts pipeline — $0/month to run.**

> Trending Idea → Script → Voice → Footage → Video Assembly → SEO → Upload

---

## ✨ Features

- **💡 Idea Explorer Agent** — Aggregates Google Trends RSS, YouTube Trending, Reddit & HackerNews. Scored by Gemini Flash AI.
- **📝 Script Generator** — Groq (Llama 3.3) with niche-specific Jinja2 prompt templates.
- **🎙️ Kokoro TTS** — Local, Apache 2.0, near-ElevenLabs quality. Zero cost forever.
- **📹 Automated Video Assembly** — FFmpeg: Ken Burns effects, word-highlight captions, progress bar timer, background music.
- **🔍 Originality Checker** — TF-IDF cosine similarity vs. your published video history.
- **🤖 Semi-dark-mode Automation** — Confidence scorer auto-approves high-quality videos; flags edge cases for review.
- **📤 YouTube Auto-Upload** — YouTube Data API v3 with OAuth 2.0, private + scheduled publish.
- **🖥️ Streamlit Dashboard** — 5-tab UI: Idea Explorer, Queue, Review, Analytics, Settings.

## 💰 Cost

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq (Llama 3.3) + Gemini Flash | **Free** |
| TTS | Kokoro TTS (local) | **Free** |
| Stock Footage | Pexels + Pixabay | **Free** |
| Video Render | FFmpeg + MoviePy | **Free** |
| Captions | faster-whisper (local) | **Free** |
| Trend Detection | RSS + Reddit + HN + YouTube API | **Free** |
| Upload | YouTube Data API v3 | **Free** |
| Server | Oracle Cloud Free Tier (4 OCPU + 24GB ARM) | **Free** |
| **Total** | | **$0/month** |

## 🚀 Quick Start

### Local Setup

```bash
# Clone and install
git clone <your-repo>
cd youtube-automation
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Start API
uvicorn app.main:app --reload --port 8000

# Start UI (new terminal)
streamlit run ui/streamlit_app.py
```

### Oracle Cloud Deployment

```bash
# On your Oracle Cloud ARM VM (Ubuntu 22.04)
bash deploy/setup_oracle.sh

# Add your .env file
nano /opt/youtube-automation/.env

# Set up YouTube OAuth (one-time, on local machine)
python -c "from app.pipeline.uploader import _get_credentials; _get_credentials()"
# Copy token.json to server

# Start services
sudo systemctl start yt-api yt-ui
```

## 🔑 Required API Keys

| Key | Get it here | Cost |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Free |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) | Free |
| `PIXABAY_API_KEY` | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | Free |
| `REDDIT_CLIENT_ID/SECRET` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps/) | Free |
| YouTube OAuth | Google Cloud Console | Free |

## 📁 Project Structure

```
youtube-automation/
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # Settings (pydantic-settings)
│   ├── scheduler.py         # APScheduler cron jobs
│   ├── agents/
│   │   ├── idea_explorer.py    # Multi-source trend agent
│   │   └── script_generator.py # Groq script gen
│   ├── pipeline/
│   │   ├── tts.py              # Kokoro TTS
│   │   ├── transcriber.py      # faster-whisper captions
│   │   ├── asset_manager.py    # Pexels + Pixabay
│   │   ├── video_assembler.py  # FFmpeg assembly
│   │   ├── seo_generator.py    # YouTube metadata
│   │   ├── thumbnail_maker.py  # Pillow thumbnail
│   │   └── uploader.py         # YouTube Data API v3
│   ├── confidence/
│   │   └── scorer.py           # 5-criteria auto-approve
│   ├── originality/
│   │   └── history_checker.py  # TF-IDF similarity
│   └── db/
│       ├── models.py           # SQLAlchemy models
│       └── database.py         # SQLite setup
├── ui/
│   └── streamlit_app.py     # 5-tab dashboard
├── prompts/                 # Jinja2 niche templates
├── music/                   # Royalty-free .mp3/.wav tracks
├── deploy/
│   ├── setup_oracle.sh      # Oracle ARM setup script
│   └── nginx.conf           # Nginx reverse proxy
├── tests/                   # pytest test suite
├── .env.example
├── requirements.txt
└── Dockerfile
```

## 🧪 Tests

```bash
pytest tests/ -v
```

## 📖 Pipeline Flow

```
[Stage 0] Idea Explorer → trending ideas ranked by virality + niche relevance
[Stage 1] Script Generation → structured JSON with visual keywords
[Stage 2] Kokoro TTS → narration.wav
[Stage 3] faster-whisper → word-level timestamps for captions
[Stage 4] Pexels + Pixabay → B-roll clips per segment
[Stage 5] FFmpeg Assembly → 9:16 MP4 with captions, Ken Burns, music, progress bar
[Stage 6] SEO + Pillow Thumbnail → title, description, tags, 1280×720 thumbnail
[Stage 7] Confidence Scoring → auto-approve ≥0.80 or flag for review
[Stage 8] YouTube Upload → private + scheduled, with thumbnail set
```

## ⚠️ YouTube Policy Compliance

This pipeline includes mandatory safeguards against YouTube's 2026 repetitive content policy:
- Human review step for any video below 80% confidence
- TF-IDF originality checker prevents repeating covered topics
- LLM prompt variation instructions for unique scripts
- Diverse visual keywords ensure different footage per video

---

Built with ❤️ using Python, FastAPI, Streamlit, FFmpeg, Kokoro TTS, and Oracle Cloud Free Tier.
