"""
app/pipeline/asset_manager.py — AI Image Background Generation.

Strategy:
  - Generate highly detailed vertical AI images via image.pollinations.ai
  - Cache downloaded images locally by prompt hash.
"""
from __future__ import annotations

import hashlib
import os
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.db.models import AssetCache, QuotaUsage

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"
CACHE_TTL_DAYS = 30


# ── Pollinations AI Image Generation ──────────────────────────────────────────────────

def _generate_pollinations_image(prompt: str) -> dict[str, Any] | None:
    """Generate a 9:16 image using Pollinations API."""
    encoded_prompt = quote_plus(prompt)
    # Using 1080x1920 for vertical Shorts format
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    
    try:
        # We can just return the URL, and the download function will fetch it
        return {
            "url": url,
            "width": 1080,
            "height": 1920,
            "duration": 10.0, # Dummy duration since it's an image
            "source": "pollinations",
        }
    except Exception as e:
        logger.warning(f"[Assets] Pollinations generation error for '{prompt[:20]}...': {e}")
        return None


PIXABAY_AUDIO_URL = "https://pixabay.com/api/audio/"

def fetch_background_music(genre: str = "lofi") -> str | None:
    """Fetch royalty-free background music from Pixabay Audio."""
    if not settings.pixabay_api_key or settings.pixabay_api_key.startswith("your_"):
        return None
        
    params = {
        "key": settings.pixabay_api_key,
        "q": genre,
        "per_page": 20,
    }
    try:
        resp = httpx.get(PIXABAY_AUDIO_URL, params=params, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            return None
            
        import random
        track = random.choice(hits)
        audio_url = track.get("audio")
        if not audio_url:
            return None
            
        dest_dir = Path("cache/music")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"pixabay_{track.get('id')}.mp3"
        
        if dest_path.exists():
            return str(dest_path)
            
        if _download_clip(audio_url, str(dest_path)):
            return str(dest_path)
            
    except Exception as e:
        logger.warning(f"[Assets] Failed to fetch background music: {e}")
        
    return None

def _download_clip(url: str, dest_path: str) -> bool:
    """Stream-download a video clip to disk."""
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Downloaded: {os.path.basename(dest_path)}")
        return True
    except Exception as e:
        logger.warning(f"Download failed ({url[:60]}...): {e}")
        return False


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _keyword_hash(keyword: str, source: str) -> str:
    return hashlib.sha256(f"{source}:{keyword.lower()}".encode()).hexdigest()[:16]


def _get_cached(db: Session, keyword: str, source: str = "any") -> AssetCache | None:
    h = _keyword_hash(keyword, source)
    row = db.get(AssetCache, h)
    if row and Path(row.file_path).exists():
        return row
    return None


def _save_cache(db: Session, keyword: str, source: str, file_path: str,
                width: int, height: int, duration: float) -> None:
    h = _keyword_hash(keyword, source)
    row = AssetCache(
        keyword_hash=h,
        keyword=keyword,
        source=source,
        file_path=file_path,
        width=width,
        height=height,
        duration_sec=duration,
        cached_at=datetime.utcnow(),
    )
    db.merge(row)
    db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_image_for_prompt(prompt: str, job_id: str, db: Session) -> str | None:
    """
    Generate (or retrieve from cache) an AI image for a prompt.

    Args:
        prompt: Detailed AI image prompt from script segment.
        job_id: Used for local file path organisation.
        db: DB session.

    Returns:
        Local file path of downloaded image, or None if not found.
    """
    cache_dir = Path(settings.cache_dir) / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check cache first
    cached = _get_cached(db, prompt, "pollinations")
    if cached:
        logger.info(f"[Assets] Cache hit for image: '{prompt[:30]}...'")
        return cached.file_path

    # Generate Image
    clip_info = _generate_pollinations_image(prompt)

    if not clip_info:
        logger.warning(f"[Assets] No image generated for prompt: '{prompt}'")
        return None

    # Download and cache
    source = clip_info["source"]
    safe_prompt = hashlib.md5(prompt.encode()).hexdigest()[:16]
    filename = f"{safe_prompt}_{source}.jpg"
    dest_path = str(cache_dir / filename)

    logger.info(f"[Assets] Generating image for '{prompt[:40]}...'")
    if _download_clip(clip_info["url"], dest_path):
        _save_cache(db, prompt, source, dest_path,
                    clip_info["width"], clip_info["height"], clip_info["duration"])
        return dest_path

    return None


def fetch_clips_for_script(script: dict[str, Any], job_id: str, db: Session) -> dict[str, str | None]:
    """
    Generate AI images for all image prompts across all script segments.

    Returns:
        Dict mapping image_prompt → local file path (or None if not found).
    """
    results: dict[str, str | None] = {}
    all_prompts: list[str] = []

    for segment in script.get("segments", []):
        prompt = segment.get("image_prompt")
        # Support fallback to visual_keywords if image_prompt isn't present
        if not prompt and segment.get("visual_keywords"):
            prompt = " ".join(segment.get("visual_keywords", []))
            
        if prompt and prompt not in all_prompts:
            all_prompts.append(prompt)

    logger.info(f"[Assets] Generating {len(all_prompts)} AI images")

    for prompt in all_prompts:
        results[prompt] = fetch_image_for_prompt(prompt, job_id, db)

    found = sum(1 for v in results.values() if v is not None)
    logger.info(f"[Assets] Successfully generated {found}/{len(all_prompts)} AI images")
    return results
