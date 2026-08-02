"""
app/db/models.py — SQLAlchemy ORM models for all pipeline entities.
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean
from app.db.database import Base


class User(Base):
    """Stores user credentials and settings for Streamlit Auth."""
    __tablename__ = "users"

    username = Column(String(50), primary_key=True)
    password_hash = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    client_secrets_json = Column(Text, default="")
    oauth_tokens_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class TrendCache(Base):
    """Cached trend signals from all sources (TTL: 6 hours)."""
    __tablename__ = "trend_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)         # google_trends | youtube | reddit | hn
    raw_title = Column(Text, nullable=False)
    niche_score = Column(Float, default=0.0)
    virality_score = Column(Float, default=0.0)
    combined_score = Column(Float, default=0.0)
    suggested_angle = Column(Text, default="")
    format_recommendation = Column(String(50), default="shorts")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class VideoJob(Base):
    """Full lifecycle of a single video production job."""
    __tablename__ = "video_job"

    id = Column(String(36), primary_key=True)            # UUID
    topic = Column(Text, nullable=False)
    niche = Column(String(100), default="general")
    status = Column(String(30), default="queued")        # queued | generating | review | approved | uploading | done | failed
    confidence_score = Column(Float, default=0.0)
    auto_approved = Column(Boolean, default=False)

    # Stage outputs
    script_json = Column(Text, default="")               # full script JSON
    audio_path = Column(String(500), default="")
    video_path = Column(String(500), default="")
    thumbnail_path = Column(String(500), default="")
    seo_json = Column(Text, default="")

    # YouTube
    youtube_video_id = Column(String(100), default="")
    published_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, default="")
    current_stage = Column(String(50), default="")       # which pipeline stage is running
    stage_progress = Column(Float, default=0.0)          # 0.0 – 1.0

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishedHistory(Base):
    """YouTube published video history for originality checking."""
    __tablename__ = "published_history"

    youtube_video_id = Column(String(100), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    published_at = Column(DateTime, nullable=True)
    tfidf_vector_json = Column(Text, default="")         # serialised as JSON list of floats
    last_synced = Column(DateTime, default=datetime.utcnow)


class AssetCache(Base):
    """Local cache manifest for downloaded stock footage clips."""
    __tablename__ = "asset_cache"

    keyword_hash = Column(String(64), primary_key=True)  # SHA256 of keyword + source
    keyword = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)          # pexels | pixabay
    file_path = Column(String(500), nullable=False)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    duration_sec = Column(Float, default=0.0)
    cached_at = Column(DateTime, default=datetime.utcnow)


class QuotaUsage(Base):
    """Daily API quota tracker to prevent overage."""
    __tablename__ = "quota_usage"

    date = Column(String(10), primary_key=True)          # YYYY-MM-DD
    youtube_units_used = Column(Integer, default=0)
    groq_requests = Column(Integer, default=0)
    gemini_requests = Column(Integer, default=0)
    pexels_requests = Column(Integer, default=0)
    pixabay_requests = Column(Integer, default=0)
