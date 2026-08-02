"""
scratch_live_prod.py — Production test runner with real Groq LLM + Pexels B-Roll.
"""
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv(override=True)

import time
import json
import os
from pathlib import Path
from app.db.database import SessionLocal, init_db
from app.db.models import VideoJob

print("=" * 70)
print("🚀 PRODUCTION PIPELINE RUN — REAL GROQ LLM + REAL PEXELS B-ROLL")
print("=" * 70)

init_db()

import argparse

parser = argparse.ArgumentParser(description="Run production pipeline.")
parser.add_argument(
    "--topic",
    type=str,
    default="5 Secret Python Features You Must Know in 2026",
    help="Topic for the video"
)
args = parser.parse_args()

TOPIC = args.topic
JOB_ID = "live_prod_demo"
OUTPUT_DIR = "output"

start_time = time.time()

# ── Stage 1: Script Generation via Groq Llama 3.3 70B ────────────────────────
print("\n[STAGE 1/9] 📝 Script Generation (Groq Llama 3.3 70B)")
t0 = time.time()
from app.agents.script_generator import generate_script

script = generate_script(topic=TOPIC, niche="ai_tech")
t1 = time.time()
print(f"  ✓ Title Hook: \"{script.get('title_hook', '')}\"")
print(f"  ✓ Estimated Duration: {script.get('total_estimated_duration', 50)}s")
print(f"  ✓ Segments count: {len(script.get('segments', []))}")
for i, seg in enumerate(script.get('segments', [])):
    print(f"      Seg {i+1} ({seg.get('duration_hint_sec', 10)}s): \"{seg.get('text', '')}\"")
    print(f"           Keywords: {seg.get('visual_keywords', [])}")
print(f"  ✓ CTA: \"{script.get('cta', '')}\"")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 2: Originality Check ────────────────────────────────────────────────
print("\n[STAGE 2/9] 🔍 Originality Checker (TF-IDF)")
t0 = time.time()
from app.originality.history_checker import check_similarity

db = SessionLocal()
sim_score = check_similarity(TOPIC, db=db, refresh_if_stale=False)
db.close()
t1 = time.time()
print(f"  ✓ Similarity vs Channel History: {sim_score:.3f}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 3: Voice Synthesis (Kokoro TTS 82M) ─────────────────────────────────
print("\n[STAGE 3/9] 🎙️ Voice Synthesis (Kokoro TTS - Voice: af_heart)")
t0 = time.time()
from app.pipeline.tts import synthesise_script

audio_path, audio_duration = synthesise_script(script, JOB_ID, OUTPUT_DIR)
t1 = time.time()
print(f"  ✓ Audio Output: {audio_path}")
print(f"  ✓ Narration Length: {audio_duration:.2f}s")
print(f"  ✓ File Size: {os.path.getsize(audio_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 4: Word Timestamps (faster-whisper) ─────────────────────────────────
print("\n[STAGE 4/9] ⏱️ Transcription & Word Timestamps (faster-whisper)")
t0 = time.time()
from app.pipeline.transcriber import transcribe_audio

transcript = transcribe_audio(audio_path, JOB_ID, OUTPUT_DIR)
t1 = time.time()
words = transcript.get("words", [])
print(f"  ✓ Words Extracted: {len(words)}")
print(f"  ✓ Sample Word Timing: '{words[0]['word']}' ({words[0]['start']:.2f}s -> {words[0]['end']:.2f}s)")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 5: Real B-Roll Stock Footage (Pexels HD Portrait Videos) ───────────
print("\n[STAGE 5/9] 📹 Downloading Real HD B-Roll Clips (Pexels API)")
t0 = time.time()
from app.pipeline.asset_manager import fetch_clips_for_script

db = SessionLocal()
asset_map = fetch_clips_for_script(script, JOB_ID, db=db)
db.close()
t1 = time.time()
print(f"  ✓ Keywords Searched: {list(asset_map.keys())}")
for kw, path in asset_map.items():
    if path and os.path.exists(path):
        print(f"      '{{kw}}': ✓ Downloaded HD video clip ({os.path.getsize(path):,} bytes) -> {path}")
    else:
        print(f"      '{{kw}}': ⚠ Fallback clip")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 6: Video Assembly (FFmpeg 9:16 Vertical Render) ─────────────────────
print("\n[STAGE 6/9] 🎬 Render 9:16 Shorts Video (FFmpeg Ken Burns + Captions)")
t0 = time.time()
from app.pipeline.video_assembler import assemble_video

video_path = assemble_video(
    script=script,
    audio_path=audio_path,
    words=transcript["words"],
    asset_map=asset_map,
    job_id=JOB_ID,
    output_dir=OUTPUT_DIR,
    total_audio_duration=audio_duration,
)
t1 = time.time()
print(f"  ✓ Output Video: {video_path}")
print(f"  ✓ Format: 1080x1920 60FPS vertical Shorts MP4")
print(f"  ✓ Rendered Video Size: {os.path.getsize(video_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 7: SEO Metadata (Groq Llama 3.3 70B) ────────────────────────────────
print("\n[STAGE 7/9] 🔍 SEO Metadata (Groq Llama 3.3 70B)")
t0 = time.time()
from app.pipeline.seo_generator import generate_seo_metadata

seo = generate_seo_metadata(script)
t1 = time.time()
print(f"  ✓ Title: \"{seo['title']}\"")
print(f"  ✓ Description: \"{seo['description']}\"")
print(f"  ✓ Tags: {seo['tags']}")
print(f"  ✓ Category ID: {seo['category_id']}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 8: HD Thumbnail Generation (Pillow) ─────────────────────────────────
print("\n[STAGE 8/9] 🖼️ HD Thumbnail Creation (Pillow 1280x720)")
t0 = time.time()
from app.pipeline.thumbnail_maker import create_thumbnail

thumb_path = create_thumbnail(seo['title'], video_path, JOB_ID, OUTPUT_DIR, "Python & AI")
t1 = time.time()
print(f"  ✓ Thumbnail Output: {thumb_path}")
print(f"  ✓ Size: {os.path.getsize(thumb_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 9: Confidence Scoring & DB Record ──────────────────────────────────
print("\n[STAGE 9/9] ⚖️ Confidence Scoring & Database Registration")
t0 = time.time()
from app.confidence.scorer import compute_confidence_score

score, breakdown = compute_confidence_score(
    script=script,
    seo=seo,
    audio_path=audio_path,
    audio_duration=audio_duration,
    asset_map=asset_map,
    similarity_score=sim_score,
)
t1 = time.time()
status = "auto_approve" if score >= 0.80 else "review"

db = SessionLocal()
job = db.get(VideoJob, JOB_ID)
if not job:
    job = VideoJob(id=JOB_ID, topic=TOPIC, niche="ai_tech")
    db.add(job)

job.status = status
job.confidence_score = score
job.current_stage = "done"
job.audio_path = os.path.abspath(audio_path)
job.video_path = os.path.abspath(video_path)
job.thumbnail_path = os.path.abspath(thumb_path)
job.script_json = json.dumps(script)
job.seo_json = json.dumps(seo)
db.commit()
db.close()

print(f"  ✓ Composite Score: {score:.3f} / 1.000")
print(f"  ✓ Final Status: {'🟢 AUTO-APPROVED' if status == 'auto_approve' else '🟡 REVIEW QUEUE'}")
print(f"  ✓ Breakdown: {json.dumps(breakdown)}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")

total_dur = time.time() - start_time
print("\n" + "=" * 70)
print(f"🎉 PRODUCTION RUN COMPLETED SUCCESSFULLY IN {total_dur:.2f} SECONDS!")
print(f"📁 Video: {video_path}")
print(f"🖼️ Thumbnail: {thumb_path}")
print(f"🎙️ Audio: {audio_path}")
print("=" * 70)
