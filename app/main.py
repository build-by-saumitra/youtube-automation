"""
app/main.py — FastAPI application entrypoint.

Exposes REST API for pipeline control + integrates APScheduler for background cron.
All pipeline jobs run as FastAPI background tasks.
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db, init_db
from app.db.models import VideoJob
from app.scheduler import start_scheduler, stop_scheduler


# ── Lifespan (startup/shutdown) ────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting YouTube Automation API...")
    init_db()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("API shutdown complete")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube Automation API",
    description="End-to-end YouTube Shorts automation pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.auth_routes import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class RunPipelineRequest(BaseModel):
    topic: str
    angle: str = ""
    niche: str | None = None


class VideoJobResponse(BaseModel):
    id: str
    topic: str
    status: str
    confidence_score: float
    auto_approved: bool
    current_stage: str
    stage_progress: float
    youtube_video_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Background pipeline runner ─────────────────────────────────────────────────

def _run_pipeline_task(job_id: str, topic: str, angle: str, niche: str | None):
    """Full pipeline execution — runs in background."""
    from app.db.database import SessionLocal
    from app.agents.script_generator import generate_script
    from app.pipeline.tts import synthesise_script
    from app.pipeline.transcriber import transcribe_audio
    from app.pipeline.asset_manager import fetch_clips_for_script
    from app.pipeline.video_assembler import assemble_video
    from app.pipeline.seo_generator import generate_seo_metadata
    from app.pipeline.thumbnail_maker import create_thumbnail
    from app.confidence.scorer import compute_confidence_score
    from app.originality.history_checker import check_similarity

    db = SessionLocal()
    try:
        def _update(stage: str, progress: float, status: str = "generating", **kwargs):
            job = db.get(VideoJob, job_id)
            if job:
                job.current_stage = stage
                job.stage_progress = progress
                job.status = status
                for k, v in kwargs.items():
                    setattr(job, k, v)
                job.updated_at = datetime.utcnow()
                db.commit()

        logger.info(f"[Pipeline] Starting job {job_id}: '{topic}'")

        # Stage 1: Script
        _update("script_generation", 0.1)
        script = generate_script(topic, angle, niche)

        # Stage 2: Originality check
        _update("originality_check", 0.18)
        similarity = check_similarity(topic, db)

        # Stage 3: TTS
        _update("voice_synthesis", 0.25)
        audio_path, audio_duration = synthesise_script(script, job_id, settings.output_dir)

        # Stage 4: Transcription
        _update("transcription", 0.40)
        transcript = transcribe_audio(audio_path, job_id, settings.output_dir)

        # Stage 5: Asset sourcing
        _update("asset_sourcing", 0.50)
        asset_map = fetch_clips_for_script(script, job_id, db)

        # Stage 6: Video assembly
        _update("video_assembly", 0.62)
        video_path = assemble_video(
            script=script,
            audio_path=audio_path,
            words=transcript["words"],
            asset_map=asset_map,
            job_id=job_id,
            output_dir=settings.output_dir,
            total_audio_duration=audio_duration,
        )

        # Stage 7: SEO + Thumbnail
        _update("seo_metadata", 0.78)
        seo = generate_seo_metadata(script)
        thumbnail_path = create_thumbnail(
            title=seo["title"],
            video_path=video_path,
            job_id=job_id,
            output_dir=settings.output_dir,
            niche=script.get("_niche", "AI & Tech"),
        )

        # Stage 8: Confidence scoring
        _update("scoring", 0.88)
        confidence, breakdown = compute_confidence_score(
            script=script,
            seo=seo,
            audio_path=audio_path,
            audio_duration=audio_duration,
            asset_map=asset_map,
            similarity_score=similarity,
        )

        auto_approved = confidence >= settings.auto_approve_threshold
        status = "approved" if auto_approved else "review"

        _update(
            "done",
            1.0,
            status=status,
            script_json=json.dumps(script),
            audio_path=audio_path,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            seo_json=json.dumps(seo),
            confidence_score=confidence,
            auto_approved=auto_approved,
        )

        logger.info(f"[Pipeline] Job {job_id} complete. Status={status}, Score={confidence:.3f}")

        # Auto-upload if approved
        if auto_approved and settings.enable_auto_queue:
            _auto_upload(job_id, video_path, thumbnail_path, seo, db)

    except Exception as e:
        logger.error(f"[Pipeline] Job {job_id} failed: {e}", exc_info=True)
        job = db.get(VideoJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def _auto_upload(job_id: str, video_path: str, thumbnail_path: str, seo: dict):
    """Auto-upload approved video to YouTube in background with fresh DB session."""
    from app.db.database import SessionLocal
    from app.pipeline.uploader import upload_video
    db = SessionLocal()
    try:
        job = db.get(VideoJob, job_id)
        if job:
            job.status = "uploading"
            db.commit()
        video_id = upload_video(video_path, thumbnail_path, seo, db)
        job = db.get(VideoJob, job_id)
        if job:
            job.status = "done"
            job.youtube_video_id = video_id
            job.published_at = datetime.utcnow()
            db.commit()
        logger.info(f"[Pipeline] Auto-uploaded job {job_id}: youtube.com/watch?v={video_id}")
    except Exception as e:
        logger.error(f"[Pipeline] Auto-upload failed for {job_id}: {e}")
        job = db.get(VideoJob, job_id)
        if job:
            job.status = "review"  # fall back to manual review
            job.error_message = f"Auto-upload failed: {e}"
            db.commit()
    finally:
        db.close()


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/pipeline/run")
def run_pipeline(
    req: RunPipelineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger a new video production job."""
    job_id = str(uuid.uuid4())
    job = VideoJob(
        id=job_id,
        topic=req.topic,
        niche=req.niche or "general",
        status="queued",
        current_stage="queued",
        stage_progress=0.0,
    )
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_pipeline_task, job_id, req.topic, req.angle, req.niche)
    logger.info(f"[API] Pipeline queued: job_id={job_id}, topic='{req.topic}'")
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/pipeline/status/{job_id}")
def get_pipeline_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "topic": job.topic,
        "status": job.status,
        "current_stage": job.current_stage,
        "stage_progress": job.stage_progress,
        "confidence_score": job.confidence_score,
        "auto_approved": job.auto_approved,
        "video_path": job.video_path,
        "audio_path": job.audio_path,
        "thumbnail_path": job.thumbnail_path,
        "script_json": job.script_json,
        "seo_json": job.seo_json,
        "youtube_video_id": job.youtube_video_id,
        "error_message": job.error_message,
    }


@app.get("/api/ideas")
def get_ideas(db: Session = Depends(get_db)):
    """Return latest scored trend ideas from cache."""
    from app.agents.idea_explorer import run_idea_explorer
    ideas = run_idea_explorer(db)
    return {"ideas": ideas, "count": len(ideas)}


@app.post("/api/ideas/refresh")
def refresh_ideas(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger idea explorer (clears cache first)."""
    from app.db.models import TrendCache
    db.query(TrendCache).delete()
    db.commit()
    background_tasks.add_task(_refresh_ideas_bg)
    return {"status": "refreshing"}


def _refresh_ideas_bg():
    from app.db.database import SessionLocal
    from app.agents.idea_explorer import run_idea_explorer
    db = SessionLocal()
    try:
        run_idea_explorer(db)
    finally:
        db.close()


@app.get("/api/videos")
def list_videos(db: Session = Depends(get_db), limit: int = 50):
    """List all video jobs, newest first."""
    jobs = db.query(VideoJob).order_by(VideoJob.created_at.desc()).limit(limit).all()
    return {"videos": [
        {
            "id": j.id,
            "topic": j.topic,
            "status": j.status,
            "confidence_score": j.confidence_score,
            "auto_approved": j.auto_approved,
            "youtube_video_id": j.youtube_video_id,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]}


@app.post("/api/video/{job_id}/approve")
def approve_video(job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually approve a video for upload."""
    job = db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("review",):
        raise HTTPException(status_code=400, detail=f"Cannot approve job with status '{job.status}'")

    seo = json.loads(job.seo_json) if job.seo_json else {}
    job.status = "uploading"
    db.commit()

    background_tasks.add_task(
        _auto_upload, job_id, job.video_path, job.thumbnail_path, seo
    )
    return {"status": "uploading", "job_id": job_id}


@app.post("/api/video/{job_id}/reject")
def reject_video(job_id: str, db: Session = Depends(get_db)):
    """Reject a video job (marks as failed)."""
    job = db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "failed"
    job.error_message = "Rejected by user"
    db.commit()
    return {"status": "rejected"}
