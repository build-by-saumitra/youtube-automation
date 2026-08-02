"""
app/pipeline/seo_generator.py — LLM-powered SEO metadata generation via Groq.

Produces: title, description, tags, category_id for YouTube upload.
"""
from __future__ import annotations

import json
from typing import Any

from groq import Groq
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

SEO_PROMPT = """You are a YouTube SEO expert who specialises in Shorts for the AI/Tech niche.

Generate optimised YouTube metadata for a Short video on the following topic.

**Topic:** {topic}
**Script hook:** {hook}
**Niche:** {niche}

Requirements:
- title: Exactly 1 title. Punchy, curiosity-driving, includes primary keyword. 60–80 characters.
- description: 2–3 sentences. Natural, includes 2–3 hashtags (e.g. #AIShorts #TechTips). Ends with CTA.
- tags: 10–15 relevant tags (mix of short-tail and long-tail keywords).
- category_id: Use "28" for Science & Technology, "27" for Education. Pick best fit.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "category_id": "28",
  "default_language": "en"
}}
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_seo_metadata(script: dict[str, Any]) -> dict[str, Any]:
    """
    Generate YouTube SEO metadata for a given script.

    Args:
        script: Parsed script dict with _topic, _niche, title_hook fields.

    Returns:
        Dict with title, description, tags, category_id, default_language.
    """
    topic = script.get("_topic", "AI Tools")
    niche = script.get("_niche", "general")
    hook = script.get("title_hook", "")

    prompt = SEO_PROMPT.format(topic=topic, hook=hook, niche=niche)

    raw: str = ""
    has_valid_groq_key = bool(settings.groq_api_key and not settings.groq_api_key.startswith("your_"))

    if has_valid_groq_key:
        try:
            client = Groq(api_key=settings.groq_api_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[SEO] Groq failed: {e}")

    if not raw:
        # Minimal fallback
        return {
            "title": f"{topic[:70]}",
            "description": f"Learn about {topic}. #AIShorts #TechTips #Shorts",
            "tags": [topic, "AI", "Technology", "Shorts", "LearnAI"],
            "category_id": "28",
            "default_language": "en",
        }

    # Clean and parse
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        metadata = json.loads(text)
        # Enforce limits
        metadata["title"] = metadata.get("title", topic)[:100]
        metadata["tags"] = metadata.get("tags", [])[:15]
        logger.info(f"[SEO] Generated: '{metadata['title']}'")
        return metadata
    except json.JSONDecodeError as e:
        logger.error(f"[SEO] Parse error: {e}")
        return {
            "title": f"{topic[:70]}",
            "description": f"Learn about {topic}. #AIShorts #TechTips",
            "tags": [topic, "AI", "Technology", "Shorts"],
            "category_id": "28",
            "default_language": "en",
        }
