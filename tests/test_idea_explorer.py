"""
tests/test_idea_explorer.py — Unit tests for Idea Explorer data source parsers.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.agents.idea_explorer import (
    fetch_hackernews_topics,
    fetch_google_trends,
    score_with_llm,
)


def test_fetch_hackernews_topics_success():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "hits": [
            {"title": "New AI model beats GPT-4"},
            {"title": "Open source LLM released"},
            {"title": ""},  # empty — should be filtered
        ]
    }
    with patch("httpx.get", return_value=mock_response):
        results = fetch_hackernews_topics()
    assert len(results) == 2
    assert "New AI model beats GPT-4" in results


def test_fetch_hackernews_topics_failure():
    with patch("httpx.get", side_effect=Exception("network error")):
        results = fetch_hackernews_topics()
    assert results == []


def test_score_with_llm_no_api_key():
    """With no Gemini key, should return unscored items."""
    with patch("app.agents.idea_explorer.settings") as mock_settings:
        mock_settings.gemini_api_key = ""
        results = score_with_llm(["Topic A", "Topic B"])
    assert len(results) == 2
    assert all(r["combined_score"] == 0.5 for r in results)


def test_score_with_llm_parses_response():
    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(
        text='''[
            {"title": "AI Revolution", "niche_relevance": 0.9, "virality_score": 0.85,
             "combined_score": 0.87, "suggested_angle": "Show 3 AI tools that save 10 hours/week",
             "format_recommendation": "shorts"}
        ]'''
    )
    with patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("google.generativeai.configure"):
        from unittest.mock import patch as p2
        with p2("app.agents.idea_explorer.settings") as ms:
            ms.gemini_api_key = "fake-key"
            ms.idea_explorer_interval_hours = 6
            results = score_with_llm(["AI Revolution"])

    assert len(results) == 1
    assert results[0]["title"] == "AI Revolution"
