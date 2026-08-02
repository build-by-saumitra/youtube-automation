"""
tests/test_confidence_scorer.py — Unit tests for the confidence scoring module.
"""
import pytest
from app.confidence.scorer import (
    _score_duration,
    _score_originality,
    _score_asset_coverage,
    _score_seo_title,
    _score_audio_quality,
    compute_confidence_score,
)
import tempfile, os


# ── Duration scoring ───────────────────────────────────────────────────────────

def test_duration_score_in_range():
    script = {"total_estimated_duration": 50}
    assert _score_duration(script, 50.0) == 1.0


def test_duration_score_too_short():
    script = {"total_estimated_duration": 10}
    assert _score_duration(script, 10.0) == 0.0


def test_duration_score_slightly_outside():
    script = {"total_estimated_duration": 60}
    score = _score_duration(script, 60.0)
    assert score == 0.6


# ── Originality scoring ────────────────────────────────────────────────────────

def test_originality_unique():
    assert _score_originality(0.1) == 1.0


def test_originality_borderline():
    assert _score_originality(0.65) == 0.7


def test_originality_too_similar():
    assert _score_originality(0.8) == 0.0


# ── Asset coverage ─────────────────────────────────────────────────────────────

def test_asset_coverage_full():
    script = {
        "segments": [
            {"visual_keywords": ["ai robot", "code screen"]},
            {"visual_keywords": ["data chart"]},
        ]
    }
    asset_map = {"ai robot": "/some/file.mp4", "data chart": "/some/file2.mp4"}
    assert _score_asset_coverage(script, asset_map) == 1.0


def test_asset_coverage_partial():
    script = {
        "segments": [
            {"visual_keywords": ["ai robot"]},
            {"visual_keywords": ["missing keyword"]},
            {"visual_keywords": ["another missing"]},
        ]
    }
    asset_map = {"ai robot": "/some/file.mp4"}
    score = _score_asset_coverage(script, asset_map)
    assert score < 1.0


def test_asset_coverage_empty():
    script = {"segments": [{"visual_keywords": ["nothing"]}]}
    asset_map = {}
    assert _score_asset_coverage(script, asset_map) == 0.2


# ── SEO title ──────────────────────────────────────────────────────────────────

def test_seo_title_good():
    seo = {"title": "How AI Is Changing Data Science Forever in 2025 — Must Know"}
    assert _score_seo_title(seo) == 1.0


def test_seo_title_too_short():
    seo = {"title": "AI 2025"}
    assert _score_seo_title(seo) == 0.3


def test_seo_title_empty():
    seo = {"title": ""}
    assert _score_seo_title(seo) == 0.3


# ── Audio quality ──────────────────────────────────────────────────────────────

def test_audio_quality_good():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"\x00" * 50000)  # ~50KB fake WAV
        tmp_path = f.name
    try:
        assert _score_audio_quality(tmp_path, 45.0) == 1.0
    finally:
        os.unlink(tmp_path)


def test_audio_quality_missing():
    assert _score_audio_quality("/nonexistent/file.wav", 45.0) == 0.0


def test_audio_quality_too_short_duration():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"\x00" * 50000)
        tmp_path = f.name
    try:
        assert _score_audio_quality(tmp_path, 5.0) == 0.3
    finally:
        os.unlink(tmp_path)


# ── Composite score ────────────────────────────────────────────────────────────

def test_compute_confidence_high_score():
    script = {
        "total_estimated_duration": 50,
        "segments": [{"visual_keywords": ["ai"]}],
    }
    seo = {"title": "How AI Is Transforming Data Science in 2025"}
    asset_map = {"ai": "/fake/path.mp4"}

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"\x00" * 50000)
        tmp_path = f.name
    try:
        score, breakdown = compute_confidence_score(
            script=script,
            seo=seo,
            audio_path=tmp_path,
            audio_duration=50.0,
            asset_map=asset_map,
            similarity_score=0.1,
        )
        assert score >= 0.75
        assert "duration" in breakdown
    finally:
        os.unlink(tmp_path)
