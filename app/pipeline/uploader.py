"""
app/pipeline/uploader.py — YouTube Data API v3 upload with OAuth 2.0 + quota tracking.

Upload flow:
  1. Upload video as 'private' with scheduled publishAt time.
  2. Set custom thumbnail via thumbnails.set.
  3. Store YouTube video ID in DB.
  4. Track daily quota usage in SQLite.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httplib2
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import QuotaUsage

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# Cost of videos.insert in YouTube API quota units
UPLOAD_QUOTA_COST = 1600
THUMBNAIL_QUOTA_COST = 50
DAILY_QUOTA_LIMIT = 9_000  # leave 1,000 units headroom


def _get_credentials() -> Credentials:
    """Load or refresh OAuth 2.0 credentials. Run interactive flow if needed."""
    creds: Credentials | None = None
    token_file = settings.youtube_token_file

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as e:
            logger.warning(f"[Uploader] Token refresh failed: {e} — re-authenticating")
            creds = None

    if not creds or not creds.valid:
        secrets_file = settings.youtube_client_secrets_file
        if not os.path.exists(secrets_file):
            raise FileNotFoundError(
                f"YouTube client_secrets.json not found at '{secrets_file}'. "
                "Download it from Google Cloud Console and set YOUTUBE_CLIENT_SECRETS_FILE."
            )
        flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)
        _save_token(creds)

    return creds


def _save_token(creds: Credentials) -> None:
    with open(settings.youtube_token_file, "w") as f:
        f.write(creds.to_json())


def _check_quota(db: Session) -> None:
    """Raise if today's quota would be exceeded by this upload."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = db.get(QuotaUsage, today)
    used = row.youtube_units_used if row else 0
    needed = UPLOAD_QUOTA_COST + THUMBNAIL_QUOTA_COST
    if used + needed > DAILY_QUOTA_LIMIT:
        raise RuntimeError(
            f"[Uploader] Daily YouTube quota would be exceeded "
            f"(used={used}, needed={needed}, limit={DAILY_QUOTA_LIMIT})"
        )


def _increment_quota(db: Session, amount: int) -> None:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = db.get(QuotaUsage, today)
    if not row:
        row = QuotaUsage(date=today)
        db.add(row)
    row.youtube_units_used = (row.youtube_units_used or 0) + amount
    db.commit()


def upload_video(
    video_path: str,
    thumbnail_path: str,
    seo: dict[str, Any],
    db: Session,
    schedule_minutes_from_now: int = 30,
) -> str:
    """
    Upload a video to YouTube (as private + scheduled).

    Args:
        video_path: Local path to the rendered MP4.
        thumbnail_path: Local path to the thumbnail JPEG.
        seo: SEO metadata dict (title, description, tags, category_id).
        db: DB session for quota tracking.
        schedule_minutes_from_now: How many minutes from now to schedule publish.

    Returns:
        YouTube video ID string.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    _check_quota(db)

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # Scheduled publish time
    publish_at = (datetime.utcnow() + timedelta(minutes=schedule_minutes_from_now)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )

    body = {
        "snippet": {
            "title": seo.get("title", "AI Short"),
            "description": seo.get("description", ""),
            "tags": seo.get("tags", []),
            "categoryId": seo.get("category_id", "28"),
            "defaultLanguage": seo.get("default_language", "en"),
        },
        "status": {
            "privacyStatus": "private",  # always upload private first
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
        },
    }

    logger.info(f"[Uploader] Uploading: {Path(video_path).name} ({Path(video_path).stat().st_size / 1_048_576:.1f}MB)")

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,  # 8MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Resumable upload with progress logging
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"[Uploader] Upload progress: {progress}%")

    video_id = response["id"]
    _increment_quota(db, UPLOAD_QUOTA_COST)
    logger.info(f"[Uploader] Video uploaded: https://youtu.be/{video_id} (private, scheduled at {publish_at})")

    # Set thumbnail
    if os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            _increment_quota(db, THUMBNAIL_QUOTA_COST)
            logger.info(f"[Uploader] Thumbnail set for {video_id}")
        except Exception as e:
            logger.warning(f"[Uploader] Thumbnail set failed: {e}")

    return video_id
