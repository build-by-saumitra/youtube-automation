"""
app/pipeline/tts.py — Kokoro TTS voice synthesis (Apache 2.0, local, CPU-capable).

Generates per-segment WAV files and a concatenated final narration.wav.
Fallback chain: Kokoro → ElevenLabs (if API key set).
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any

import soundfile as sf
import numpy as np
from loguru import logger

from app.config import settings


def _kokoro_synthesise(text: str, voice: str, speed: float) -> np.ndarray:
    """
    Synthesise text using Kokoro TTS (local model).
    Returns numpy float32 audio array at 24kHz.
    """
    from kokoro import KPipeline  # type: ignore — installed via pip install kokoro

    pipeline = KPipeline(lang_code="a")  # 'a' = American English
    generator = pipeline(text, voice=voice, speed=speed)

    audio_chunks: list[np.ndarray] = []
    for _, _, audio in generator:
        audio_chunks.append(audio)

    if not audio_chunks:
        raise ValueError(f"Kokoro produced no audio for text: {text[:80]}")

    return np.concatenate(audio_chunks)


def _elevenlabs_synthesise(text: str, voice_id: str, api_key: str) -> bytes:
    """ElevenLabs premium fallback — returns raw MP3 bytes."""
    import httpx
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    resp = httpx.post(url, json=body, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


def synthesise_script(script: dict[str, Any], job_id: str, output_dir: str) -> tuple[str, float]:
    """
    Synthesise the full script narration to a WAV file.

    Args:
        script: Parsed script dict with title_hook, segments, cta.
        job_id: Pipeline job ID (used for output file naming).
        output_dir: Base output directory.

    Returns:
        (audio_path, total_duration_sec)
    """
    job_dir = Path(output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Build ordered list of narration text blocks
    texts: list[str] = []
    if script.get("title_hook"):
        texts.append(script["title_hook"])
    for seg in script.get("segments", []):
        if seg.get("text"):
            texts.append(seg["text"])
    if script.get("cta"):
        texts.append(script["cta"])

    full_text = " ".join(texts)
    logger.info(f"[TTS] Synthesising {len(full_text)} chars for job {job_id}")

    audio_path = str(job_dir / "narration.wav")
    sample_rate = 24000

    # ── Primary: Kokoro TTS ────────────────────────────────────────
    try:
        t0 = time.time()
        voice = "af_bella" if script.get("_niche") == "kids" else settings.kokoro_voice
        audio_array = _kokoro_synthesise(full_text, voice, settings.kokoro_speed)
        elapsed = time.time() - t0
        sf.write(audio_path, audio_array, sample_rate)
        duration = len(audio_array) / sample_rate
        logger.info(f"[TTS] Kokoro done in {elapsed:.1f}s — duration: {duration:.1f}s")
        return audio_path, duration

    except Exception as e:
        logger.warning(f"[TTS] Kokoro failed: {e}")

    # ── Fallback: ElevenLabs ───────────────────────────────────────
    if settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
        try:
            logger.info("[TTS] Falling back to ElevenLabs")
            mp3_bytes = _elevenlabs_synthesise(full_text, settings.elevenlabs_voice_id, settings.elevenlabs_api_key)
            # Convert MP3 bytes → WAV via soundfile + io
            mp3_path = str(job_dir / "narration.mp3")
            with open(mp3_path, "wb") as f:
                f.write(mp3_bytes)
            # Use ffmpeg to convert MP3 → WAV
            os.system(f'ffmpeg -y -i "{mp3_path}" -ar {sample_rate} "{audio_path}" -loglevel quiet')
            import soundfile as _sf
            data, _ = _sf.read(audio_path)
            duration = len(data) / sample_rate
            logger.info(f"[TTS] ElevenLabs done — duration: {duration:.1f}s")
            return audio_path, duration
        except Exception as e2:
            logger.error(f"[TTS] ElevenLabs fallback also failed: {e2}")

    raise RuntimeError(f"All TTS providers failed for job {job_id}")
