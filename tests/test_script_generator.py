"""
tests/test_script_generator.py — Unit tests for script generation.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.agents.script_generator import _detect_niche, _parse_script_json


def test_detect_niche_ai():
    assert _detect_niche("ChatGPT just released a new model") == "ai_tech"


def test_detect_niche_finance():
    assert _detect_niche("Stock market crashes — what investors should know") == "finance"


def test_detect_niche_general():
    assert _detect_niche("The history of coffee shops in New York") == "general"


def test_parse_script_json_valid():
    raw = '''{
        "title_hook": "Did you know AI can now code better than most engineers?",
        "segments": [
            {"text": "Here is why.", "duration_hint_sec": 10, "visual_keywords": ["code", "AI"], "caption_style": "highlight"}
        ],
        "cta": "Follow for more!",
        "total_estimated_duration": 45
    }'''
    result = _parse_script_json(raw, "AI coding")
    assert result["title_hook"].startswith("Did you know")
    assert len(result["segments"]) == 1
    assert result["total_estimated_duration"] == 45


def test_parse_script_json_with_markdown():
    raw = '```json\n{"title_hook":"Hook","segments":[],"cta":"Follow!","total_estimated_duration":30}\n```'
    result = _parse_script_json(raw, "test")
    assert result["title_hook"] == "Hook"


def test_parse_script_json_invalid_returns_fallback():
    result = _parse_script_json("this is not json at all {{{{", "My Topic")
    assert "title_hook" in result
    assert "segments" in result
    assert "My Topic" in result["title_hook"] or "My Topic" in str(result)


def test_detect_niche_python():
    assert _detect_niche("Python automation scripts for developers") == "ai_tech"


def test_detect_niche_crypto():
    assert _detect_niche("Bitcoin ETF approval — what this means for crypto investors") == "finance"
