"""
app/originality/history_checker.py — TF-IDF cosine similarity check against published YouTube history.

Fetches published video titles + descriptions from YouTube Data API v3.
Caches vectors in SQLite (PublishedHistory table).
Refreshes every 24 hours.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from googleapiclient.discovery import build
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import PublishedHistory

_vectorizer: TfidfVectorizer | None = None
_corpus_matrix: Any = None
_corpus_ids: list[str] = []


def _get_youtube_service():
    """Build YouTube Data API v3 service using API key (read-only)."""
    from google.oauth2.credentials import Credentials
    import os
    token_file = settings.youtube_token_file
    if os.path.exists(token_file):
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(token_file)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)
    return None


def _fetch_channel_videos(db: Session, max_results: int = 200) -> list[dict]:
    """Fetch published video titles + descriptions from YouTube channel."""
    service = _get_youtube_service()
    if not service or not settings.youtube_channel_id:
        logger.warning("[Originality] YouTube service unavailable — skipping history fetch")
        return []

    videos: list[dict] = []
    try:
        # Get uploads playlist ID
        channels_resp = service.channels().list(
            part="contentDetails",
            id=settings.youtube_channel_id,
        ).execute()
        if not channels_resp.get("items"):
            return []

        uploads_id = channels_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Paginate through uploads
        next_page_token = None
        while len(videos) < max_results:
            pl_resp = service.playlistItems().list(
                part="snippet",
                playlistId=uploads_id,
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token,
            ).execute()

            for item in pl_resp.get("items", []):
                snip = item["snippet"]
                videos.append({
                    "id": snip["resourceId"]["videoId"],
                    "title": snip.get("title", ""),
                    "description": snip.get("description", "")[:500],
                    "published_at": snip.get("publishedAt"),
                })

            next_page_token = pl_resp.get("nextPageToken")
            if not next_page_token:
                break

        logger.info(f"[Originality] Fetched {len(videos)} published videos from channel")
    except Exception as e:
        logger.error(f"[Originality] YouTube history fetch error: {e}")

    return videos


def refresh_history(db: Session) -> None:
    """Fetch latest channel videos and store in PublishedHistory table."""
    videos = _fetch_channel_videos(db)
    if not videos:
        return

    for v in videos:
        doc = f"{v['title']} {v['description']}"
        row = PublishedHistory(
            youtube_video_id=v["id"],
            title=v["title"],
            description=v["description"],
            published_at=datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) if v.get("published_at") else None,
            last_synced=datetime.utcnow(),
        )
        db.merge(row)

    db.commit()
    logger.info(f"[Originality] History refreshed: {len(videos)} videos")

    # Invalidate in-memory cache
    global _vectorizer, _corpus_matrix, _corpus_ids
    _vectorizer = None
    _corpus_matrix = None
    _corpus_ids = []


def _build_tfidf_index(db: Session) -> None:
    """Build in-memory TF-IDF index from PublishedHistory table."""
    global _vectorizer, _corpus_matrix, _corpus_ids

    rows = db.query(PublishedHistory).all()
    if not rows:
        logger.info("[Originality] No published history — all topics pass originality check")
        return

    docs = [f"{r.title} {r.description}" for r in rows]
    _corpus_ids = [r.youtube_video_id for r in rows]

    _vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    _corpus_matrix = _vectorizer.fit_transform(docs)
    logger.info(f"[Originality] TF-IDF index built: {len(docs)} documents")


def check_similarity(topic: str, db: Session, refresh_if_stale: bool = True) -> float:
    """
    Compute maximum cosine similarity between the given topic and all published videos.

    Args:
        topic: The proposed video topic string.
        db: DB session.
        refresh_if_stale: Auto-refresh channel history if last sync > 24h.

    Returns:
        Float 0.0–1.0. Higher = more similar to existing content. 0.0 = no history.
    """
    global _vectorizer, _corpus_matrix, _corpus_ids

    # Check if refresh needed
    if refresh_if_stale:
        latest = db.query(PublishedHistory).order_by(PublishedHistory.last_synced.desc()).first()
        if not latest or (datetime.utcnow() - latest.last_synced) > timedelta(hours=24):
            refresh_history(db)

    # Build index if not cached
    if _vectorizer is None:
        _build_tfidf_index(db)

    if _vectorizer is None or _corpus_matrix is None:
        return 0.0  # No history → no similarity risk

    try:
        query_vec = _vectorizer.transform([topic])
        sims = cosine_similarity(query_vec, _corpus_matrix)
        max_sim = float(np.max(sims))
        logger.info(f"[Originality] Max similarity for '{topic[:60]}': {max_sim:.3f}")
        return max_sim
    except Exception as e:
        logger.error(f"[Originality] Similarity check failed: {e}")
        return 0.0
