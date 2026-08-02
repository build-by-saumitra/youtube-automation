"""
app/agents/idea_explorer.py — Multi-source trend aggregator + Gemini Flash LLM scoring.

Sources:
  1. Google Trends Daily RSS (no auth)
  2. YouTube Data API v3 trending (categories 28=Science&Tech, 27=Education)
  3. Reddit PRAW (r/artificial, r/MachineLearning, r/technology, r/investing)
  4. HackerNews Algolia front-page API

All signals are passed to Gemini Flash for niche relevance + virality scoring.
Results are cached in SQLite with a 6-hour TTL.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import feedparser
from google import genai
from google.genai import types as genai_types
import httpx
import praw
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import TrendCache

# ── Source URLs ────────────────────────────────────────────────────────────────
GOOGLE_TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
HN_API_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=20"
YOUTUBE_TRENDING_URL = "https://www.googleapis.com/youtube/v3/videos"

# ── Niche subreddits to monitor ────────────────────────────────────────────────
SUBREDDITS = ["artificial", "MachineLearning", "technology", "investing", "datascience"]


# ── Source fetchers ────────────────────────────────────────────────────────────

def fetch_google_trends() -> list[str]:
    """Parse Google Trends daily trending RSS feed (US). Returns list of topic titles."""
    try:
        feed = feedparser.parse(GOOGLE_TRENDS_RSS_URL)
        titles = [entry.get("title", "") for entry in feed.entries[:15]]
        logger.info(f"Google Trends: {len(titles)} topics fetched")
        return titles
    except Exception as e:
        logger.warning(f"Google Trends fetch failed: {e}")
        return []


def fetch_youtube_trending(api_key: str) -> list[str]:
    """Fetch YouTube trending videos for Science&Tech (28) and Education (27)."""
    if not api_key or api_key.startswith("your_"):
        logger.warning("YouTube API key not configured — skipping YouTube trending")
        return []

    titles: list[str] = []
    for category_id in ["28", "27"]:
        try:
            params = {
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": "US",
                "videoCategoryId": category_id,
                "maxResults": 10,
                "key": api_key,
            }
            resp = httpx.get(YOUTUBE_TRENDING_URL, params=params, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            titles.extend(item["snippet"]["title"] for item in items)
        except Exception as e:
            logger.warning(f"YouTube trending (cat {category_id}) failed: {e}")

    logger.info(f"YouTube Trending: {len(titles)} topics fetched")
    return titles


def fetch_reddit_topics(client_id: str, client_secret: str, user_agent: str) -> list[str]:
    """Fetch hot posts from niche subreddits via PRAW (read-only)."""
    if not client_id or not client_secret or client_id.startswith("your_"):
        logger.warning("Reddit credentials not configured — skipping Reddit")
        return []

    titles: list[str] = []
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            read_only=True,
        )
        for sub in SUBREDDITS:
            for post in reddit.subreddit(sub).hot(limit=5):
                if not post.stickied:
                    titles.append(post.title)
    except Exception as e:
        logger.warning(f"Reddit fetch failed: {e}")

    logger.info(f"Reddit: {len(titles)} topics fetched")
    return titles


def fetch_hackernews_topics() -> list[str]:
    """Fetch front-page HackerNews stories via Algolia API (no auth)."""
    try:
        resp = httpx.get(HN_API_URL, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        titles = [h.get("title", "") for h in hits if h.get("title")]
        logger.info(f"HackerNews: {len(titles)} topics fetched")
        return titles
    except Exception as e:
        logger.warning(f"HackerNews fetch failed: {e}")
        return []


# ── LLM Scoring ───────────────────────────────────────────────────────────────

SCORING_PROMPT = """You are an expert YouTube Shorts content strategist. Given a list of trending topics, score each for:
1. niche_relevance (0-1): How relevant is this to AI Tools, Tech, Data Science, or Investing?
2. virality_score (0-1): How likely is this to go viral as a 60-second educational Short?

For each topic, also suggest:
- suggested_angle: A specific creative angle/hook for a YouTube Short (1 sentence)
- format_recommendation: "shorts" always (we only do Shorts for now)

Return ONLY valid JSON array, no markdown, no explanation:
[
  {
    "title": "...",
    "niche_relevance": 0.0,
    "virality_score": 0.0,
    "combined_score": 0.0,
    "suggested_angle": "...",
    "format_recommendation": "shorts"
  }
]

Topics to score:
{topics_list}
"""


def score_with_llm(raw_titles: list[str]) -> list[dict[str, Any]]:
    """Use Gemini Flash to score and rank topics by niche relevance + virality."""
    if not settings.gemini_api_key or settings.gemini_api_key.startswith("your_"):
        logger.warning("Gemini API key not configured — returning unscored topics")
        return [{"title": t, "niche_relevance": 0.5, "virality_score": 0.5,
                 "combined_score": 0.5, "suggested_angle": "", "format_recommendation": "shorts"}
                for t in raw_titles]

    # Deduplicate and limit
    unique_titles = list(dict.fromkeys(raw_titles))[:30]
    topics_str = "\n".join(f"- {t}" for t in unique_titles)

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=SCORING_PROMPT.format(topics_list=topics_str),
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )
        raw_text = response.text.strip()
        # Strip any accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        scored = json.loads(raw_text)
        # Recalculate combined_score: 40% niche + 60% virality
        for item in scored:
            item["combined_score"] = round(
                item.get("niche_relevance", 0) * 0.4 + item.get("virality_score", 0) * 0.6, 4
            )
        # Sort descending
        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        logger.info(f"Gemini scored {len(scored)} topics. Top: {scored[0]['title'] if scored else 'none'}")
        return scored

    except Exception as e:
        logger.error(f"Gemini scoring failed: {e}")
        return [{"title": t, "niche_relevance": 0.5, "virality_score": 0.5,
                 "combined_score": 0.5, "suggested_angle": "", "format_recommendation": "shorts"}
                for t in unique_titles]


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_key(title: str, source: str) -> str:
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()


def get_cached_trends(db: Session) -> list[TrendCache]:
    """Return non-expired trend cache entries, sorted by combined_score desc."""
    now = datetime.utcnow()
    return (
        db.query(TrendCache)
        .filter(TrendCache.expires_at > now)
        .order_by(TrendCache.combined_score.desc())
        .all()
    )


def save_trends_to_cache(db: Session, scored_items: list[dict], source: str = "mixed") -> None:
    """Persist scored trend items to SQLite with 6-hour TTL."""
    expires = datetime.utcnow() + timedelta(hours=settings.idea_explorer_interval_hours)
    for item in scored_items:
        entry = TrendCache(
            source=source,
            raw_title=item["title"],
            niche_score=item.get("niche_relevance", 0.0),
            virality_score=item.get("virality_score", 0.0),
            combined_score=item.get("combined_score", 0.0),
            suggested_angle=item.get("suggested_angle", ""),
            format_recommendation=item.get("format_recommendation", "shorts"),
            fetched_at=datetime.utcnow(),
            expires_at=expires,
        )
        db.merge(entry)
    db.commit()
    logger.info(f"Cached {len(scored_items)} trend items (TTL 6h)")


# ── Main entrypoint ────────────────────────────────────────────────────────────

def run_idea_explorer(db: Session) -> list[dict[str, Any]]:
    """
    Full idea explorer run:
    1. Check cache — if valid entries exist, return top 5 from cache.
    2. Otherwise fetch all sources, score with Gemini, cache, return top 5.
    """
    cached = get_cached_trends(db)
    if cached:
        logger.info(f"Returning {len(cached)} cached trend items (not expired)")
        return [
            {
                "title": c.raw_title,
                "niche_relevance": c.niche_score,
                "virality_score": c.virality_score,
                "combined_score": c.combined_score,
                "suggested_angle": c.suggested_angle,
                "format_recommendation": c.format_recommendation,
            }
            for c in cached[:5]
        ]

    logger.info("Cache expired — running full idea explorer fetch...")

    raw: list[str] = []
    raw += fetch_google_trends()
    raw += fetch_youtube_trending(settings.pexels_api_key)  # note: uses YT api key separately
    raw += fetch_reddit_topics(settings.reddit_client_id, settings.reddit_client_secret, settings.reddit_user_agent)
    raw += fetch_hackernews_topics()

    if not raw:
        logger.warning("No topics fetched from any source!")
        return []

    scored = score_with_llm(raw)
    save_trends_to_cache(db, scored, source="mixed")

    return scored[:5]
