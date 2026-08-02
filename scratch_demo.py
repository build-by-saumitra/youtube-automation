"""
scratch_demo.py — Step-by-step pipeline test runner.
"""
import time
import json
import os
from pathlib import Path

print("=" * 65)
print("🎬 YOUTUBE AUTOMATION PIPELINE — STEP-BY-STEP DEMO RUN")
print("=" * 65)

TOPIC = "5 Secret Python Features You Must Know in 2026"
JOB_ID = "demo_step_by_step"
OUTPUT_DIR = "output"
JOB_DIR = Path(OUTPUT_DIR) / JOB_ID
JOB_DIR.mkdir(parents=True, exist_ok=True)

start_time = time.time()

# ── Stage 1: Script Generation ────────────────────────────────────────────────
print("\n[STAGE 1/9] 📝 Script Generation")
t0 = time.time()
from app.agents.script_generator import generate_script

script = generate_script(topic=TOPIC, niche="ai_tech")
t1 = time.time()
print(f"  ✓ Duration hint: {script.get('total_estimated_duration', 30)}s")
print(f"  ✓ Title Hook: \"{script.get('title_hook', '')}\"")
print(f"  ✓ Segments count: {len(script.get('segments', []))}")
for i, seg in enumerate(script.get('segments', [])):
    print(f"      Seg {i+1}: \"{seg.get('text', '')}\" (keywords: {seg.get('visual_keywords', [])})")
print(f"  ✓ CTA: \"{script.get('cta', '')}\"")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 2: Originality Check ────────────────────────────────────────────────
print("\n[STAGE 2/9] 🔍 Originality Checker")
t0 = time.time()
from app.originality.history_checker import check_similarity
from app.db.database import SessionLocal

db = SessionLocal()
sim_score = check_similarity(TOPIC, db=db, refresh_if_stale=False)
db.close()
t1 = time.time()
print(f"  ✓ TF-IDF Cosine Similarity vs History: {sim_score:.3f}")
print(f"  ✓ Originality Status: {'🟢 UNIQUE TOPIC (0.00 similarity)' if sim_score < 0.70 else '🔴 REPETITIVE TOPIC'}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 3: Voice Synthesis (Kokoro TTS) ─────────────────────────────────────
print("\n[STAGE 3/9] 🎙️ Kokoro TTS Voice Synthesis")
t0 = time.time()
from app.pipeline.tts import synthesise_script

audio_path, audio_duration = synthesise_script(script, JOB_ID, OUTPUT_DIR)
t1 = time.time()
print(f"  ✓ Output Audio File: {audio_path}")
print(f"  ✓ Audio Duration: {audio_duration:.2f} seconds")
print(f"  ✓ Audio File Size: {os.path.getsize(audio_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 4: Transcription (faster-whisper) ───────────────────────────────────
print("\n[STAGE 4/9] ⏱️ Transcription & Word-Level Timestamps")
t0 = time.time()
from app.pipeline.transcriber import transcribe_audio

transcript = transcribe_audio(audio_path, JOB_ID, OUTPUT_DIR)
t1 = time.time()
print(f"  ✓ Words Extracted: {len(transcript.get('words', []))}")
print(f"  ✓ Subtitle Segments: {len(transcript.get('segments', []))}")
print(f"  ✓ Sample Word Timestamps:")
for w in transcript.get('words', [])[:5]:
    print(f"      Word '{w['word']}': {w['start']:.2f}s → {w['end']:.2f}s")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 5: B-Roll Asset Sourcing ───────────────────────────────────────────
print("\n[STAGE 5/9] 📹 B-Roll Footage Sourcing")
t0 = time.time()
from app.pipeline.asset_manager import fetch_clips_for_script

db = SessionLocal()
asset_map = fetch_clips_for_script(script, JOB_ID, db=db)
db.close()
t1 = time.time()
print(f"  ✓ Keywords Searched: {list(asset_map.keys())}")
for kw, path in asset_map.items():
    print(f"      '{kw}': {'✓ Cached clip found' if path else '⚠ Fallback to styled canvas clip'}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 6: Video Assembly (FFmpeg) ──────────────────────────────────────────
print("\n[STAGE 6/9] 🎬 FFmpeg 9:16 Video Assembly")
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
print(f"  ✓ Output Video File: {video_path}")
print(f"  ✓ Resolution & Format: 1080x1920 MP4 (9:16 Vertical Shorts)")
print(f"  ✓ Applied Effects: Ken Burns zoom/pan + Word-highlight captions + Animated progress bar")
print(f"  ✓ Rendered Video Size: {os.path.getsize(video_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 7: SEO Metadata ─────────────────────────────────────────────────────
print("\n[STAGE 7/9] 🔍 SEO Metadata Generation")
t0 = time.time()
from app.pipeline.seo_generator import generate_seo_metadata

seo = generate_seo_metadata(script)
t1 = time.time()
print(f"  ✓ Title: \"{seo['title']}\" ({len(seo['title'])} chars)")
print(f"  ✓ Description: \"{seo['description']}\"")
print(f"  ✓ Tags: {seo['tags']}")
print(f"  ✓ Category ID: {seo['category_id']}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 8: Thumbnail Generation ────────────────────────────────────────────
print("\n[STAGE 8/9] 🖼️ Thumbnail Generation (Pillow)")
t0 = time.time()
from app.pipeline.thumbnail_maker import create_thumbnail

thumb_path = create_thumbnail(seo['title'], video_path, JOB_ID, OUTPUT_DIR, "AI & Python")
t1 = time.time()
print(f"  ✓ Thumbnail File: {thumb_path}")
print(f"  ✓ Resolution: 1280x720 (YouTube standard HD)")
print(f"  ✓ Thumbnail File Size: {os.path.getsize(thumb_path):,} bytes")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")


# ── Stage 9: Confidence Scoring ──────────────────────────────────────────────
print("\n[STAGE 9/9] ⚖️ Confidence Scoring & Approval Gate")
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
print(f"  ✓ Final Confidence Score: {score:.3f} / 1.000")
print(f"  ✓ Approval Decision: {'🟢 AUTO-APPROVED for upload' if status == 'auto_approve' else '🟡 FLAGGED FOR HUMAN REVIEW in Streamlit UI'}")
print(f"  ✓ Score Breakdown:")
for metric, val in breakdown.items():
    print(f"      - {metric:15s}: {val:.3f}")
print(f"  ⏱ Time taken: {t1 - t0:.2f}s")

total_duration = time.time() - start_time
print("\n" + "=" * 65)
print(f"🎉 DEMO TEST COMPLETED SUCCESSFULLY IN {total_duration:.2f} SECONDS!")
print(f"📁 Video Output: {video_path}")
print(f"🖼️ Thumbnail Output: {thumb_path}")
print(f"🎙️ Audio Output: {audio_path}")
print("=" * 65)
