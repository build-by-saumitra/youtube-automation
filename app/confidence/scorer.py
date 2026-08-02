"""
app/confidence/scorer.py — 5-criteria confidence scorer for semi-dark-mode automation.

Score ≥ 0.80 → auto-approve for upload.
Score < 0.80 → flag for human review in Streamlit UI.
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.config import settings


def _score_duration(script: dict, audio_duration: float) -> float:
    """Check estimated audio duration is within Shorts range (30–58s)."""
    estimated = script.get("total_estimated_duration", 0)
    duration = audio_duration if audio_duration > 0 else estimated
    if 30 <= duration <= 58:
        return 1.0
    elif 25 <= duration < 30 or 58 < duration <= 62:
        return 0.6  # slightly outside but acceptable
    else:
        logger.warning(f"[Scorer] Duration {duration:.1f}s out of Shorts range")
        return 0.0


def _score_originality(similarity_score: float) -> float:
    """Originality check — lower similarity is better."""
    if similarity_score <= 0.50:
        return 1.0
    elif similarity_score <= 0.65:
        return 0.7
    elif similarity_score <= 0.70:
        return 0.4
    else:
        return 0.0  # too similar to existing content


def _score_asset_quality(script: dict, asset_map: dict[str, str | None]) -> float:
    """What % of script segments have high-quality AI images generated."""
    segments = script.get("segments", [])
    if not segments:
        return 0.0

    score_total = 0.0
    for seg in segments:
        prompt = seg.get("image_prompt")
        if not prompt and seg.get("visual_keywords"):
            prompt = " ".join(seg.get("visual_keywords", []))
            
        if not prompt:
            continue
            
        best_clip = asset_map.get(prompt)
        
        if best_clip:
            if "cache/images" in str(best_clip):
                score_total += 1.0 # Real AI Image (perfect)
            elif "assets/videos" in str(best_clip) or "cache/clips" in str(best_clip):
                score_total += 0.5 # Legacy clip fallback
            else:
                score_total += 0.2 # Unknown / dynamic canvas

    coverage = score_total / len(segments)
    if coverage >= 0.80:
        return 1.0
    elif coverage >= 0.50:
        return 0.6
    else:
        logger.warning(f"[Scorer] Low asset quality (AI images missing): {coverage:.0%}")
        return 0.2


def _score_seo(seo: dict) -> float:
    """Validate Comprehensive SEO — Title length, Description hashtags, Tags count."""
    title = seo.get("title", "")
    desc = seo.get("description", "")
    tags = seo.get("tags", [])
    
    score = 0.0
    # Title
    if 40 <= len(title) <= 100 and len(title.split()) >= 4:
        score += 0.5
    # Description
    if desc.count("#") >= 3:
        score += 0.25
    # Tags
    if len(tags) >= 5:
        score += 0.25
        
    return score


def _score_audio_pacing(script: dict, audio_path: str, audio_duration: float) -> float:
    """Analyze Words-Per-Minute (WPM) to ensure natural pacing."""
    if not audio_path or not os.path.exists(audio_path):
        return 0.0
        
    word_count = sum(len(seg.get("text", "").split()) for seg in script.get("segments", []))
    if script.get("title_hook"):
        word_count += len(script["title_hook"].split())
        
    wpm = (word_count / audio_duration) * 60 if audio_duration > 0 else 0
    
    if 130 <= wpm <= 180:
        return 1.0 # Perfect viral pacing
    elif 110 <= wpm < 130 or 180 < wpm <= 200:
        return 0.7 # Acceptable
    else:
        logger.warning(f"[Scorer] Unnatural Pacing: {wpm:.0f} WPM")
        return 0.3


def _score_script_anatomy(script: dict) -> float:
    """Validate that the LLM generated a strong hook, CTA, and fast-paced segments."""
    score = 0.0
    if script.get("title_hook") and len(script["title_hook"]) > 10:
        score += 0.3
    if script.get("cta") and "subscribe" in script["cta"].lower() or "follow" in script["cta"].lower():
        score += 0.2
        
    segments = script.get("segments", [])
    if len(segments) >= 4: # Rapid pacing check
        score += 0.5
    elif len(segments) >= 3:
        score += 0.3
        
    return min(1.0, score)


def compute_confidence_score(
    script: dict[str, Any],
    seo: dict[str, Any],
    audio_path: str,
    audio_duration: float,
    asset_map: dict[str, str | None],
    similarity_score: float = 0.0,
) -> tuple[float, dict[str, float]]:
    """
    Compute composite confidence score (0.0 – 1.0) using 6 weighted factors.
    """
    scores = {
        "duration":       _score_duration(script, audio_duration) * 0.10,
        "originality":    _score_originality(similarity_score) * 0.15,
        "asset_quality":  _score_asset_quality(script, asset_map) * 0.25,
        "seo":            _score_seo(seo) * 0.15,
        "audio_pacing":   _score_audio_pacing(script, audio_path, audio_duration) * 0.20,
        "script_anatomy": _score_script_anatomy(script) * 0.15,
    }

    total = round(sum(scores.values()), 4)
    breakdown = {k: round(v, 4) for k, v in scores.items()}

    threshold = settings.auto_approve_threshold
    decision = "auto-approve" if total >= threshold else "needs-review"
    logger.info(f"[Scorer] Score={total:.3f} → {decision} | {breakdown}")

    return total, breakdown
