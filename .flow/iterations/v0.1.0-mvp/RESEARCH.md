# Feature Research: YouTube Automation MVP (Faceless Content Pipeline)

**Iteration:** v0.1.0-mvp  
**Status:** Draft v2 - Pending User Review  
**Date:** 2026-08-02  

---

## 1. Problem Statement & User Value
- **Problem:** Creating high-quality faceless YouTube videos consistently requires multi-step manual labor — topic ideation, script writing, voice synthesis, footage sourcing, subtitle alignment, video rendering, SEO metadata. Fully manual: 6–10 hours per video.
- **Pipeline Goal:** Fully automated, **end-to-end** — from trending idea detection → script → voice → footage → edit → captions → SEO metadata → YouTube upload. Human reviews/approves only, not produces.
- **Target:** 2+ videos/week; YouTube Shorts first (9:16, ≤60 sec), then long-form. Niche: AI Tools & Tech / Data Careers.

---

## 2. Resource Cost Analysis: Free vs. Limited-Free vs. Paid

### 2A. LLM / Script Generation

| Tool | Cost | Limits | Verdict |
| :--- | :--- | :--- | :--- |
| **Groq API** (Llama 3.3 / Mixtral) | ✅ **Free** | ~30 RPM, daily caps | **Primary** — fastest, OpenAI-compatible, no card needed |
| **Google Gemini Flash 2.0** (AI Studio) | ✅ **Free** | Large context 1M tokens, project-specific RPM | **Secondary** — best for idea-explorer agent + trend scoring |
| **Ollama (local LLMs)** | ✅ **Free** | RAM/CPU bound | **Offline fallback** — Llama 3.2 / Phi-3, zero API cost |
| OpenAI GPT-4o | 💸 **Paid** ($5–15/MTok) | No free tier | Skip for MVP |
| Claude Sonnet | 💸 **Paid** | No free tier | Skip for MVP |

> **Decision:** Groq (Llama 3.3) as primary. Gemini Flash for idea-explorer. Ollama as local fallback.

---

### 2B. Voice Synthesis (TTS)

| Tool | Cost | Quality | Commercial OK? | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Kokoro TTS** (local) | ✅ **Free forever** | ⭐⭐⭐⭐½ | ✅ Apache 2.0 | 82M params, 54 voices, runs on CPU, top TTS Arena leaderboard 2025 |
| **Chatterbox** (Resemble AI) | ✅ **Free, self-hosted** | ⭐⭐⭐⭐ | ✅ MIT | Voice cloning capable, production-ready |
| edge-tts | ⚠️ **Unreliable (free)** | ⭐⭐⭐ | ❌ No commercial | Microsoft now rate-limits/blocks aggressively — avoid for prod |
| ElevenLabs | 🔶 **Limited-Free** (10k chars/mo) then $5/mo | ⭐⭐⭐⭐⭐ | Limited on free tier | Premium fallback only |
| gTTS | ✅ Free | ⭐⭐ | ❌ ToS issues | Robotic quality — avoid |
| XTTS v2 (Coqui) | ✅ Free self-hosted | ⭐⭐⭐⭐ | ❌ Non-commercial (CPML) | Company shut down 2024, no commercial license path |

> **Decision:** **Kokoro TTS** locally as primary (Apache 2.0, CPU, zero cost forever). ElevenLabs as premium paid fallback.

---

### 2C. Stock Footage / Visuals

| Tool | Cost | Limits | Notes |
| :--- | :--- | :--- | :--- |
| **Pexels API** | ✅ **Free** | 200 req/hr, 20k/month | High-quality cinematic footage, commercial use |
| **Pixabay API** | ✅ **Free** | 5,000 req/hr | Higher rate limit, broader variety |
| Unsplash API | ✅ Free | 50 req/hr demo | Images only, not video |
| Getty / Shutterstock | 💸 Paid | — | Avoid |
| **Flux (local image gen)** | ✅ **Free, self-hosted** | GPU recommended | AI-generated visuals/thumbnails — optional |
| Midjourney | 💸 $10/mo | — | Optional thumbnails only |

> **Decision:** Pexels + Pixabay in tandem (unified search layer). Zero cost, dual library. Flux for thumbnails optionally.

---

### 2D. Video Assembly / Rendering

| Tool | Cost | Notes |
| :--- | :--- | :--- |
| **FFmpeg** | ✅ **Free forever** | Industry standard, handles all encoding |
| **MoviePy** | ✅ **Free** | Python wrapper over FFmpeg |
| **OpenCV** | ✅ **Free** | Visual effects, transitions |

> **Decision:** FFmpeg + MoviePy. Zero cost.

---

### 2E. Captions / Transcription

| Tool | Cost | Notes |
| :--- | :--- | :--- |
| **faster-whisper** (local) | ✅ **Free** | 4× faster than Whisper, word-level timestamps — ideal for dynamic captions |
| OpenAI Whisper (local) | ✅ **Free** | Solid baseline |
| AssemblyAI | 🔶 Free: 5hr/month | Hosted alternative |

> **Decision:** `faster-whisper` locally — zero cost, word-level alignment.

---

### 2F. Trending Topic Discovery (Idea Explorer Agent)

| Tool | Cost | Notes |
| :--- | :--- | :--- |
| pytrends | ❌ **Dead (archived April 2025)** | No longer works reliably |
| **Google Trends RSS** | ✅ **Free** | XML RSS feed, no API key — daily trending polls |
| **YouTube Data API v3** | ✅ **Free** (10k quota/day) | `videos.list` to fetch trending per category/region |
| **Reddit PRAW** | ✅ **Free** | Monitor r/MachineLearning, r/artificial, r/investing, r/technology |
| **HackerNews API** | ✅ **Free** | Algolia-powered, no auth needed |
| SerpApi | 🔶 Free: 100 searches/month | Reliable Google Trends scraper — fallback if RSS insufficient |
| X (Twitter) API | 🔶 Limited free (1500 reads/month) | Too restrictive, skip |

> **Decision:** Multi-source aggregator: Google Trends RSS + YouTube Trending API + Reddit PRAW + HackerNews → LLM (Gemini Flash) scores & ranks by niche relevance + virality potential → presents top 5 ideas.

---

### 2G. YouTube Upload (Distribution)

| Tool | Cost | Limits | Notes |
| :--- | :--- | :--- | :--- |
| **YouTube Data API v3** | ✅ **Free** | 10,000 quota/day; 1,600 units/upload → ~6 uploads/day | OAuth 2.0, resumable uploads. Cannot buy more quota (need approval form). |
| `google-api-python-client` | ✅ **Free** | — | Official Python SDK |

> **Decision:** YouTube Data API v3. 6 uploads/day far exceeds target of 2/week.

---

### 2H. Thumbnail Generation

| Tool | Cost | Notes |
| :--- | :--- | :--- |
| **Pillow (PIL)** | ✅ **Free** | Programmatic thumbnail composition (text + image overlay) |
| **Flux (self-hosted)** | ✅ **Free** | AI-generated visuals, GPU recommended |
| Canva API | 🔶 Limited free | Template-based, not ideal for automation |

> **Decision:** Pillow for MVP auto-thumbnails. Optionally add Flux later.

---

### 💰 Estimated Total Monthly Cost (MVP)

| Component | Cost |
| :--- | :--- |
| LLM (Groq + Gemini free tier) | **$0** |
| TTS (Kokoro local) | **$0** |
| Video footage (Pexels + Pixabay) | **$0** |
| Video rendering (FFmpeg/MoviePy) | **$0** |
| Captions (faster-whisper local) | **$0** |
| Trend detection (RSS + Reddit + YouTube API) | **$0** |
| YouTube upload (YouTube Data API) | **$0** |
| **Total MVP cost** | **$0/month** |

> Optional paid upgrades when scaling: ElevenLabs ($5/mo), SerpApi ($50/mo), GPT-4o premium scripts.

---

## 3. Existing GitHub Repos to Leverage (Don't Start from Scratch)

### 🥇 Primary Base: `harry0703/MoneyPrinterTurbo`
- **Stack:** Python 3.11+, Streamlit WebUI, FastAPI REST backend, FFmpeg, MoviePy, ImageMagick
- **Gives us:** Complete end-to-end pipeline (script → TTS → stock footage → captions → video assembly). Supports Groq/Gemini/Ollama + multiple TTS providers. Battle-tested.
- **What to add/modify on top:**
  - Swap edge-tts → **Kokoro TTS** (quality + commercial license)
  - Add **Idea Explorer Agent** module (multi-source trend aggregation)
  - Add **YouTube auto-upload** module (YouTube Data API v3)
  - Add niche-specific SEO metadata prompts
  - Custom editorial review/approval UI step before publish

### 🥈 Reference: `SaarD00/AI-Youtube-Shorts-Generator`
- Borrow: Visual split-screen logic, transition presets, mascot/brand injection.

### 🥉 Reference: `nils44344/FreeFaceless`
- Borrow: Full zero-cost stack pattern — Groq + Pexels + FFmpeg + YouTube upload flow. Reference architecture.

---

## 4. Proposed MVP Architecture (v0.1.0) — Full Pipeline

```
[Stage 0: Idea Explorer Agent]           ← NEW module
  ↓ Aggregates: Google Trends RSS + YouTube Trending + Reddit + HackerNews
  ↓ LLM (Gemini Flash) scores by niche relevance + virality score
  ↓ Presents ranked top 5 ideas → user picks (or auto-queues top 1)

[Stage 1: Script Generation]
  ↓ Groq (Llama 3.3) → structured script:
     Hook (0–5s) + Main Body + CTA
     + visual keyword extraction per segment

[Stage 2: Voice Synthesis]
  ↓ Kokoro TTS (local, Apache 2.0) → audio file
  ↓ faster-whisper → word-level timestamps for captions

[Stage 3: Asset Sourcing]
  ↓ Pexels + Pixabay (unified search) → download B-roll per visual keyword
  ↓ Cache locally (SQLite manifest)

[Stage 4: Video Assembly]
  ↓ MoviePy + FFmpeg → 9:16 MP4
     - B-roll timed to audio segments
     - Burnt-in dynamic word-highlight captions
     - Background music overlay (royalty-free local lib)

[Stage 5: SEO Metadata + Thumbnail]
  ↓ LLM → Title, Description, Tags, Chapters
  ↓ Pillow → auto-thumbnail (text + stock image overlay)

[Stage 6: Human Review]                  ← Streamlit UI
  ↓ Preview video + metadata
  ↓ Edit script / regenerate voice / approve → proceeds to upload

[Stage 7: YouTube Upload]                ← NEW module
  ↓ YouTube Data API v3 (google-api-python-client)
  ↓ Upload with full metadata + thumbnail
  ↓ Schedule as Shorts (<60s) or long-form
```

---

## 5. Open Design Questions (for Grilling)

1. **Niche lock-in:** Single niche (e.g. "AI Tools") or multi-niche from day 1? Each niche needs different prompt templates and SEO patterns.
2. **Format priority:** Shorts only first → then long-form, or both from day 1?
3. **Human-in-the-loop level:** Always approve before upload? Or fully dark-mode (auto-select + auto-upload with just a notification)?
4. **Deployment:** Local Mac only vs. always-on server (VPS/cloud) for scheduled runs? Critical for cron-based auto-publishing.
5. **Voice identity:** Single consistent narrator voice (brand identity) vs. varying voices per video type?
6. **Thumbnail strategy:** Auto-template (Pillow) vs. AI-generated (Flux local) for premium look?
7. **Content originality loop:** Should the pipeline pull your past video history to avoid repeating topics/angles?

---

## 6. Risk Assessment & Mitigations
- **YouTube Policy (Repetitive Content):** Mandatory human review + LLM variation prompting + unique visual keyword selection.
- **Rendering Performance:** Async FFmpeg subprocess with Streamlit progress tracking.
- **API Rate Limits:** Exponential backoff + local SQLite caching for all external APIs.
- **TTS Quality:** Kokoro benchmarks near ElevenLabs for EN — validate before committing.
- **Trend staleness:** Idea Explorer runs on cron (every 6 hrs), results cached in SQLite.

---

## 7. User Design Decisions (Grilling Output — Locked In)

| Decision Area | Answer |
| :--- | :--- |
| **Niche strategy** | No lock-in — Idea Explorer Agent surfaces trending topics organically; user picks niche per batch |
| **Format priority** | YouTube Shorts first (≤60 sec, 9:16 vertical) |
| **Human-in-the-loop** | Semi-dark mode — auto-approve if confidence score is high; notify for edge cases only |
| **Deployment** | Oracle Cloud Free Tier (ARM, 4 OCPUs + 24GB RAM) — always-on server, cron-scheduled |
| **Voice identity** | Single consistent narrator voice (strong brand identity) |
| **Thumbnail strategy** | Auto-template via Pillow (bold text + stock image overlay) |
| **Content originality loop** | Yes — pipeline fetches published video history to avoid repeating topics/angles |
| **Visual elements (MVP)** | ✅ Word-highlight captions, ✅ Background music overlay, ✅ Zoom/pan Ken Burns effect, ✅ Progress bar timer at top |

### Deployment Notes (Oracle Cloud Free Tier)
- **Specs:** 4 ARM OCPUs (Ampere A1) + 24GB RAM + 200GB storage — completely free forever.
- **Kokoro TTS:** Runs well on ARM CPU — 82M param model, real-time synthesis on 4 OCPUs.
- **FFmpeg rendering:** Excellent on ARM Linux (Ubuntu 22.04 recommended).
- **Scheduling:** Use system cron or APScheduler inside FastAPI backend.
- **Access:** Streamlit UI exposed via nginx reverse proxy + SSL (Let's Encrypt).
- **Setup required:** Python 3.11, FFmpeg, ImageMagick, espeak-ng (for Kokoro), Docker optional.
