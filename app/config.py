"""
app/config.py — Centralised settings via pydantic-settings.
All values are read from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── LLM ──────────────────────────────────────────────────────
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # ── TTS ──────────────────────────────────────────────────────
    kokoro_voice: str = "af_heart"
    kokoro_speed: float = 1.05
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # ── Stock Footage ─────────────────────────────────────────────
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    # ── YouTube ───────────────────────────────────────────────────
    youtube_client_secrets_file: str = "client_secrets.json"
    youtube_token_file: str = "token.json"
    youtube_channel_id: str = ""

    # ── Reddit ────────────────────────────────────────────────────
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "youtube-automation-bot/1.0"

    # ── Paths ─────────────────────────────────────────────────────
    output_dir: str = "output"
    cache_dir: str = "cache"
    music_dir: str = "music"
    db_path: str = "data/db.sqlite3"

    # ── Pipeline ──────────────────────────────────────────────────
    auto_approve_threshold: float = 0.80
    idea_explorer_interval_hours: int = 6
    enable_auto_queue: bool = True

    # ── Server ────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    streamlit_port: int = 8501

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.output_dir, self.cache_dir, self.music_dir, Path(self.db_path).parent]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
