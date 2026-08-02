"""
app/scheduler.py — APScheduler cron jobs for background automation.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config import settings
from app.db.database import SessionLocal
from app.agents.idea_explorer import run_idea_explorer

scheduler = AsyncIOScheduler()


async def _run_idea_explorer_job():
    logger.info("[Scheduler] Running scheduled Idea Explorer...")
    db = SessionLocal()
    try:
        results = run_idea_explorer(db)
        logger.info(f"[Scheduler] Idea Explorer found {len(results)} ideas")
    except Exception as e:
        logger.error(f"[Scheduler] Idea Explorer job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        _run_idea_explorer_job,
        trigger=IntervalTrigger(hours=settings.idea_explorer_interval_hours),
        id="idea_explorer",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"[Scheduler] Started — Idea Explorer every {settings.idea_explorer_interval_hours}h")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] Stopped")
