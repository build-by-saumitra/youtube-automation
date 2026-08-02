# Feature Specification & Task Plan: YouTube Automation MVP

**Iteration:** v0.1.0-mvp  
**Status:** Draft - Pending User Review  
**Date:** 2026-08-02  

---

## 1. Overview

A fully automated, end-to-end YouTube Shorts production pipeline — from trending idea detection to YouTube upload — built on top of `harry0703/MoneyPrinterTurbo` (forked), deployed on Oracle Cloud Free Tier (ARM, always-on).

**Pipeline flow:**
```
Idea Explorer → Script → Kokoro TTS → faster-whisper → Pexels/Pixabay → FFmpeg Assembly → SEO Metadata → Pillow Thumbnail → [Semi-auto Review] → YouTube Upload
```

---

## 2. Technical Architecture & File Manifest

### Project Directory Structure

```
youtube-automation/
├── app/
│   ├── main.py                    # FastAPI app entrypoint + background task queue
│   ├── config.py                  # Env vars, API keys, niche/voice config
│   ├── scheduler.py               # APScheduler: cron jobs for idea explorer
│   │
│   ├── agents/
│   │   ├── idea_explorer.py       # [NEW] Multi-source trend aggregator + LLM scoring
│   │   └── script_generator.py   # [MODIFY] Groq/Ollama script gen with niche prompts
│   │
│   ├── pipeline/
│   │   ├── tts.py                 # [NEW] Kokoro TTS integration (replaces edge-tts)
│   │   ├── transcriber.py         # faster-whisper word-level timestamp extraction
│   │   ├── asset_manager.py       # Pexels + Pixabay unified search + local cache (SQLite)
│   │   ├── video_assembler.py     # [MODIFY] FFmpeg + MoviePy: 9:16, captions, music, fx
│   │   ├── seo_generator.py       # LLM-generated title, description, tags, chapters
│   │   ├── thumbnail_maker.py     # Pillow: text + stock image overlay thumbnail
│   │   └── uploader.py            # [NEW] YouTube Data API v3 upload + schedule
│   │
│   ├── originality/
│   │   └── history_checker.py     # [NEW] Fetch published video history, similarity check
│   │
│   ├── confidence/
│   │   └── scorer.py              # [NEW] Auto-approve logic (score → approve or flag)
│   │
│   └── db/
│       ├── models.py              # SQLAlchemy models: Job, Video, TrendCache, PublishedHistory
│       └── database.py            # SQLite setup + session management
│
├── ui/
│   └── streamlit_app.py           # [MODIFY] Streamlit UI: idea list, review, approve, status
│
├── music/
│   └── README.md                  # Store royalty-free .mp3 files here (CC0/public domain)
│
├── output/                        # Local rendered video output
├── cache/                         # Cached stock footage clips (SQLite manifest)
│
├── .env.example                   # Template for secrets
├── requirements.txt
├── Dockerfile                     # Optional Docker deployment
├── deploy/
│   ├── nginx.conf                 # Nginx reverse proxy config
│   └── setup_oracle.sh            # Oracle Cloud ARM setup script
│
└── .flow/                         # RPI workflow memory
    ├── MEMORY.md
    ├── SYSTEM.md
    ├── CHANGELOG.md
    └── iterations/v0.1.0-mvp/
        ├── RESEARCH.md
        ├── SPEC.md                ← this file
        └── SUMMARY.md             (created after implementation)
```

---

## 3. Module Specifications

### 3A. Module: `agents/idea_explorer.py` [NEW]

**Purpose:** Multi-source trend aggregator + LLM-powered idea scoring.

**Data Sources:**
- Google Trends RSS (`https://trends.google.com/trends/trendingsearches/daily/rss?geo=US`) — no auth
- YouTube Data API v3 `videos.list` — trending by category (28=Science&Tech, 27=Education)
- Reddit PRAW — r/artificial, r/MachineLearning, r/technology, r/investing (read-only, free)
- HackerNews Algolia API — `https://hn.algolia.com/api/v1/search?tags=front_page` — no auth

**LLM Scoring (Gemini Flash):**
```
Input: raw trend list (title + source + engagement signal)
Output: JSON array [{title, niche_relevance_score, virality_score, suggested_angle, format_recommendation}]
Ranked by: (niche_relevance * 0.4) + (virality * 0.6)
Top 5 presented to user / top 1 auto-queued if confidence > 0.85
```

**Cron schedule:** Every 6 hours via APScheduler. Results cached in SQLite `TrendCache` table (TTL: 6 hrs).

**Originality check:** Before presenting ideas, cross-reference against `PublishedHistory` table — filter out topics with >70% cosine similarity to any past video title/description.

---

### 3B. Module: `agents/script_generator.py` [MODIFY]

**LLM:** Groq API (model: `llama-3.3-70b-versatile`). Fallback: Ollama (local).

**Output Schema:**
```json
{
  "title_hook": "...",          // first 5 seconds spoken text
  "segments": [
    {
      "text": "...",            // narration text for this segment
      "duration_hint_sec": 8,   // approximate speech duration
      "visual_keywords": ["AI chatbot", "laptop screen", "code editor"],
      "caption_style": "highlight"
    }
  ],
  "cta": "...",                 // closing call-to-action text
  "total_estimated_duration": 55
}
```

**Niche prompt templates** (Jinja2 templates per detected niche):
- `prompts/ai_tech.j2` — AI Tools & Tech
- `prompts/finance.j2` — Data Careers & Investing
- `prompts/general.j2` — Fallback general

---

### 3C. Module: `pipeline/tts.py` [NEW — replaces edge-tts]

**Engine:** Kokoro TTS (`pip install kokoro soundfile`)

**Configuration:**
```python
VOICE_ID = "af_heart"           # Consistent narrator voice (warm, clear EN-US female)
SAMPLE_RATE = 24000             # 24kHz output
SPEED = 1.05                    # Slightly faster pace for Shorts
```

**Output:** WAV file per segment → concatenated to final `narration.wav`

**Fallback chain:** Kokoro → ElevenLabs (if API key set) → gTTS (last resort, testing only)

---

### 3D. Module: `pipeline/transcriber.py`

**Engine:** `faster-whisper` (model: `base.en` on CPU, `medium.en` if GPU available)

**Output:** Word-level SRT + JSON timestamps used by video assembler for caption rendering.

---

### 3E. Module: `pipeline/asset_manager.py` [MODIFY]

**Sources:** Pexels API + Pixabay API (unified search, dual fallback)

**Logic:**
1. Extract `visual_keywords` from each script segment.
2. Search Pexels first (200 req/hr limit — preferred quality).
3. If no match or quota exhausted → fall back to Pixabay (5,000 req/hr).
4. Download clips, cache locally by keyword hash (SQLite manifest + file path).
5. Cache TTL: 30 days (clips reused across videos).

---

### 3F. Module: `pipeline/video_assembler.py` [MODIFY]

**Stack:** MoviePy + FFmpeg subprocess

**9:16 canvas (1080×1920px) composition:**

```
┌─────────────────────────┐
│  [Progress bar: top]    │  ← animated fill, color accent (red/orange)
│                         │
│   [B-roll footage]      │  ← Ken Burns zoom/pan applied
│   [Ken Burns effect]    │
│                         │
│  [Word-highlight caps]  │  ← bottom 30%, bold font, 1 word lights up at a time
│  [Background music]     │  ← ducked -12dB under voice
└─────────────────────────┘
```

**Visual element specs:**

| Element | Implementation |
|---|---|
| Progress bar | FFmpeg `drawbox` + `drawtext` overlay, animated over total duration |
| Ken Burns | MoviePy `resize` + `crop` with linear pan/zoom per clip |
| Word-highlight captions | FFmpeg `drawtext` filter per word timestamp, active word = accent color |
| Background music | Random pick from `music/` folder, fade in/out, ducked -12dB under voice |
| Output codec | `libx264`, `aac`, `yuv420p`, `crf=23`, target ~30MB max |

---

### 3G. Module: `pipeline/seo_generator.py`

**LLM:** Groq (Llama 3.3). Input: script + niche + trending topic signal.

**Output:**
```json
{
  "title": "...",              // ≤100 chars, includes keyword
  "description": "...",       // ≥150 chars, 3 hashtags, timestamps
  "tags": ["...", "..."],     // 10-15 tags
  "category_id": "28",        // Science & Technology
  "default_language": "en",
  "chapters": []               // empty for Shorts <60s
}
```

---

### 3H. Module: `pipeline/thumbnail_maker.py`

**Stack:** Pillow (PIL)

**Template:**
- Background: stock image (from Pexels, best frame extracted by FFmpeg)
- Bold title text overlay (top/center): white text + black stroke, font size ~80px
- Bottom strip: channel branding color bar + niche tag
- Output: 1280×720 JPEG

---

### 3I. Module: `pipeline/uploader.py` [NEW]

**SDK:** `google-api-python-client` + OAuth 2.0

**Upload parameters:**
```python
{
  "snippet": {title, description, tags, categoryId, defaultLanguage},
  "status": {
    "privacyStatus": "private",   # always upload as private first
    "publishAt": "<scheduled_time>"  # set to next optimal slot
  }
}
```

**Upload flow:**
1. Upload as `private` with `publishAt` scheduled time.
2. Set thumbnail via `thumbnails.set` API call.
3. Store video ID + metadata in SQLite `Video` table.
4. Notify user (console log / webhook).

**Quota management:** Track daily quota usage in SQLite. Throttle uploads if approaching 8,000 units/day.

---

### 3J. Module: `confidence/scorer.py` [NEW]

**Purpose:** Decide auto-approve vs. flag for human review.

**Scoring criteria:**

| Check | Weight | Pass Condition |
|---|---|---|
| Script length OK (30–58 sec estimate) | 20% | Within range |
| No repeated topic (originality check) | 25% | Similarity < 70% |
| Visual keywords found in stock footage | 20% | ≥80% segments have clips |
| SEO title quality (keyword present, length ok) | 15% | Title has keyword, 50–100 chars |
| Audio quality check (Kokoro generated cleanly) | 20% | No empty segments, file > 0 bytes |

**Decision:** Score ≥ 0.80 → auto-queue for upload. Score < 0.80 → flag in Streamlit UI for review.

---

### 3K. Module: `originality/history_checker.py` [NEW]

**Source:** YouTube Data API v3 `channels.list` + `playlistItems.list` → fetch all published video titles + descriptions.

**Method:** TF-IDF vectorizer + cosine similarity. Cache in SQLite. Refresh every 24 hrs.

**Threshold:** > 70% similarity → reject topic, add to "recently covered" list.

---

### 3L. UI: `ui/streamlit_app.py` [MODIFY]

**Pages / Tabs:**
1. **💡 Idea Explorer** — Shows ranked trending ideas with virality scores. User can pick, regenerate, or skip ideas.
2. **🎬 Video Queue** — Job list with status (Generating / Review Needed / Approved / Uploaded). Progress bars per stage.
3. **📝 Review** — For flagged videos: preview video player, editable metadata, approve/reject/regenerate buttons.
4. **📊 Analytics** — Upload history, YouTube analytics summary (views, CTR from YouTube API).
5. **⚙️ Settings** — API keys, voice selection, niche config, scheduling preferences.

---

## 4. API Contracts

### Internal REST API (FastAPI)

```
POST   /api/pipeline/run          # Trigger full pipeline for a given topic
GET    /api/pipeline/status/{id}  # Get pipeline job status
POST   /api/ideas/refresh         # Manually trigger idea explorer
GET    /api/ideas                 # Get latest ranked ideas
POST   /api/video/{id}/approve    # Approve video for upload
POST   /api/video/{id}/reject     # Reject / delete video job
GET    /api/videos                # List all videos (with status)
POST   /api/upload/{id}           # Trigger YouTube upload for approved video
GET    /api/history               # Get published video history (from YouTube)
```

### External APIs Used

| API | Auth | Free Tier |
|---|---|---|
| Groq API | Bearer token | ~30 RPM |
| Google Gemini AI Studio | API key | Project-specific |
| Pexels API | API key header | 200 req/hr |
| Pixabay API | `key` query param | 5,000 req/hr |
| YouTube Data API v3 | OAuth 2.0 | 10,000 units/day |
| Reddit PRAW | Client ID + secret (read-only) | Free |
| HackerNews Algolia | No auth | Free |
| Google Trends RSS | No auth | Free |

---

## 5. Database Schema (SQLite)

```sql
-- Trend cache from Idea Explorer
CREATE TABLE trend_cache (
  id INTEGER PRIMARY KEY,
  source TEXT,              -- 'google_trends', 'youtube', 'reddit', 'hn'
  raw_title TEXT,
  niche_score REAL,
  virality_score REAL,
  suggested_angle TEXT,
  fetched_at DATETIME,
  expires_at DATETIME
);

-- Video production jobs
CREATE TABLE video_job (
  id TEXT PRIMARY KEY,       -- UUID
  topic TEXT,
  niche TEXT,
  status TEXT,               -- queued, generating, review, approved, uploading, done, failed
  confidence_score REAL,
  script_json TEXT,          -- full script JSON
  audio_path TEXT,
  video_path TEXT,
  thumbnail_path TEXT,
  seo_json TEXT,
  youtube_video_id TEXT,
  created_at DATETIME,
  updated_at DATETIME
);

-- YouTube published history (for originality checking)
CREATE TABLE published_history (
  youtube_video_id TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  published_at DATETIME,
  tfidf_vector BLOB          -- cached vector for fast similarity
);

-- Asset cache manifest
CREATE TABLE asset_cache (
  keyword_hash TEXT PRIMARY KEY,
  keyword TEXT,
  source TEXT,               -- 'pexels' or 'pixabay'
  file_path TEXT,
  cached_at DATETIME
);

-- Daily API quota tracker
CREATE TABLE quota_usage (
  date TEXT PRIMARY KEY,
  youtube_units_used INTEGER DEFAULT 0,
  groq_requests INTEGER DEFAULT 0,
  pexels_requests INTEGER DEFAULT 0
);
```

---

## 6. Deployment Architecture (Oracle Cloud Free Tier)

```
Oracle Cloud ARM VM (Ubuntu 22.04)
├── nginx (port 80/443)
│   └── Proxy → Streamlit :8501  (UI)
│   └── Proxy → FastAPI :8000    (API)
│
├── FastAPI app (uvicorn, systemd service)
│   └── APScheduler (idea explorer cron: every 6h)
│   └── Background tasks (pipeline execution)
│
├── Streamlit app (systemd service)
│
└── SQLite database (single file, /app/data/db.sqlite3)
```

**SSL:** Let's Encrypt via certbot.  
**Process management:** systemd services for FastAPI + Streamlit.  
**Monitoring:** Simple `/health` endpoint + optional UptimeRobot free tier.

---

## 7. Implementation Task Breakdown

### Phase A: Project Setup & Base Fork

- [ ] **Task A1:** Fork `harry0703/MoneyPrinterTurbo`, clean up unnecessary code, set up project structure per manifest above.
- [ ] **Task A2:** Create `.env.example` with all required keys. Set up `config.py` with pydantic-settings.
- [ ] **Task A3:** Set up SQLite + SQLAlchemy models (`db/models.py`, `db/database.py`).
- [ ] **Task A4:** Write Oracle Cloud setup script (`deploy/setup_oracle.sh`) — Python 3.11, FFmpeg, ImageMagick, espeak-ng, nginx, certbot.
- [ ] **Task A5:** Set up systemd service files for FastAPI + Streamlit.

---

### Phase B: Idea Explorer Agent

- [ ] **Task B1:** Implement Google Trends RSS parser (`idea_explorer.py` — no auth, poll every 6h).
- [ ] **Task B2:** Implement YouTube Trending fetcher (YouTube Data API v3, categories 28 + 27).
- [ ] **Task B3:** Implement Reddit PRAW reader (r/artificial, r/MachineLearning, r/technology, r/investing).
- [ ] **Task B4:** Implement HackerNews Algolia reader.
- [ ] **Task B5:** Implement Gemini Flash LLM scoring (niche relevance + virality → ranked JSON).
- [ ] **Task B6:** Implement SQLite caching for trend results (TTL 6h).
- [ ] **Task B7:** Implement originality check (`history_checker.py`) — TF-IDF cosine similarity vs. published history.
- [ ] **Task B8:** Wire APScheduler cron trigger into FastAPI app.

---

### Phase C: Script Generation

- [ ] **Task C1:** Implement Groq API client (`script_generator.py`) with Llama 3.3.
- [ ] **Task C2:** Write Jinja2 niche prompt templates (`prompts/ai_tech.j2`, `prompts/general.j2`).
- [ ] **Task C3:** Implement Ollama local fallback for offline use.
- [ ] **Task C4:** Validate script output schema (segment count, duration estimate, visual keywords).

---

### Phase D: Voice Synthesis (Kokoro TTS)

- [ ] **Task D1:** Install and configure Kokoro TTS + espeak-ng on Oracle ARM server. Validate on CPU.
- [ ] **Task D2:** Implement `tts.py` — segment-by-segment audio generation → concatenated WAV.
- [ ] **Task D3:** Implement `transcriber.py` — faster-whisper word-level timestamps → SRT + JSON.
- [ ] **Task D4:** Implement ElevenLabs fallback path (optional, behind env flag).

---

### Phase E: Asset Sourcing

- [ ] **Task E1:** Implement unified Pexels + Pixabay search in `asset_manager.py`.
- [ ] **Task E2:** Implement local file cache with SQLite manifest (hash by keyword).
- [ ] **Task E3:** Implement exponential backoff + quota tracking for both APIs.

---

### Phase F: Video Assembly

- [ ] **Task F1:** Implement 9:16 canvas composition in `video_assembler.py` (MoviePy base layer).
- [ ] **Task F2:** Implement Ken Burns zoom/pan effect on each B-roll clip.
- [ ] **Task F3:** Implement word-highlight caption overlay (FFmpeg `drawtext` per word timestamp).
- [ ] **Task F4:** Implement progress bar timer overlay (FFmpeg `drawbox` animated fill).
- [ ] **Task F5:** Implement background music selection + ducking (-12dB under voice).
- [ ] **Task F6:** Final FFmpeg render pass — `libx264`, `aac`, `crf=23`, max 30MB.

---

### Phase G: SEO + Thumbnail

- [ ] **Task G1:** Implement `seo_generator.py` — Groq LLM → title, description, tags JSON.
- [ ] **Task G2:** Implement `thumbnail_maker.py` — Pillow: stock frame + bold text overlay + branding strip.

---

### Phase H: Confidence Scoring + Review

- [ ] **Task H1:** Implement `confidence/scorer.py` — 5-criteria scoring → auto-approve or flag.
- [ ] **Task H2:** Wire confidence score into pipeline job status logic.

---

### Phase I: YouTube Upload

- [ ] **Task I1:** Set up Google OAuth 2.0 credentials + token refresh flow.
- [ ] **Task I2:** Implement `uploader.py` — resumable upload, private + scheduled publish, thumbnail set.
- [ ] **Task I3:** Implement quota tracker (SQLite `quota_usage` table). Block if >8k units/day.
- [ ] **Task I4:** Store YouTube video ID in `video_job` table on success.

---

### Phase J: Streamlit UI

- [ ] **Task J1:** Build **💡 Idea Explorer** tab — ranked ideas table, pick/skip buttons, trigger pipeline.
- [ ] **Task J2:** Build **🎬 Video Queue** tab — job list, per-stage progress bars.
- [ ] **Task J3:** Build **📝 Review** tab — video player preview, editable metadata, approve/reject.
- [ ] **Task J4:** Build **⚙️ Settings** tab — API keys, voice config, scheduling toggle.
- [ ] **Task J5:** Build **📊 Analytics** tab — upload history table, YouTube view counts.

---

### Phase K: Deployment

- [ ] **Task K1:** Run `deploy/setup_oracle.sh` on Oracle ARM VM.
- [ ] **Task K2:** Set up nginx reverse proxy for Streamlit + FastAPI.
- [ ] **Task K3:** Set up Let's Encrypt SSL (certbot).
- [ ] **Task K4:** Configure systemd services + auto-restart on failure.
- [ ] **Task K5:** End-to-end smoke test: run full pipeline once manually, verify upload to YouTube (as private).

---

## 8. Verification Plan

### Automated Tests
```bash
pytest tests/test_idea_explorer.py        # Mock RSS + Reddit + HN responses
pytest tests/test_script_generator.py    # Mock Groq API, validate output schema
pytest tests/test_tts.py                  # Kokoro generates non-empty WAV file
pytest tests/test_asset_manager.py       # Mock Pexels/Pixabay, validate cache
pytest tests/test_video_assembler.py     # Render a 10-sec test video, validate output
pytest tests/test_seo_generator.py       # Validate SEO JSON schema
pytest tests/test_confidence_scorer.py   # Test all 5 scoring criteria
pytest tests/test_uploader.py            # Mock YouTube API, validate upload payload
```

### Manual Verification
1. SSH into Oracle Cloud VM — verify all services running (`systemctl status`).
2. Open Streamlit UI in browser (via nginx + SSL).
3. Trigger Idea Explorer manually → confirm top 5 ideas appear.
4. Pick a topic → run full pipeline → watch progress in Video Queue tab.
5. Review flagged video in Review tab → approve.
6. Confirm video appears in YouTube Studio as `private` / scheduled.
7. Validate thumbnail, title, description, tags are correctly set.
