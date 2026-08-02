"""
app/agents/script_generator.py — Groq/Llama 3.3 script generation with Jinja2 niche templates.

Output schema: structured JSON with segments, visual_keywords, duration_hints.
Fallback chain: Groq → Ollama (local).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from groq import Groq
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

# ── Jinja2 template environment ───────────────────────────────────────────────
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), trim_blocks=True, lstrip_blocks=True)

# ── Niche → template mapping ──────────────────────────────────────────────────
NICHE_TEMPLATES = {
    "ai_tech": "ai_tech.j2",
    "finance": "finance.j2",
    "general": "general.j2",
    "kids": "kids.j2",
}


def _detect_niche(topic: str) -> str:
    """Simple keyword-based niche detection from topic string."""
    topic_lower = topic.lower()
    ai_keywords = {"ai", "gpt", "llm", "chatgpt", "claude", "gemini", "machine learning",
                   "deep learning", "neural", "model", "python", "data", "automation", "agent"}
    finance_keywords = {"stock", "invest", "market", "crypto", "bitcoin", "ethereum", "finance",
                        "trading", "portfolio", "economy", "revenue", "profit"}
    kids_keywords = {"kid", "kids", "child", "children", "cartoon", "animation", "toddler"}
    
    if any(k in topic_lower for k in kids_keywords):
        return "kids"
    if any(k in topic_lower for k in ai_keywords):
        return "ai_tech"
    if any(k in topic_lower for k in finance_keywords):
        return "finance"
    return "general"


def _build_prompt(topic: str, angle: str, niche: str) -> str:
    """Render the Jinja2 niche template with topic + angle."""
    template_file = NICHE_TEMPLATES.get(niche, "general.j2")
    try:
        template = jinja_env.get_template(template_file)
        return template.render(topic=topic, angle=angle)
    except Exception as e:
        logger.warning(f"Template render failed ({template_file}): {e} — using fallback")
        template = jinja_env.get_template("general.j2")
        return template.render(topic=topic, angle=angle)


# ── Groq API call ──────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_groq(prompt: str) -> str:
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content


# ── Ollama fallback ────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """Fallback to local Ollama (requires ollama server running locally)."""
    import httpx
    try:
        resp = httpx.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        raise RuntimeError(f"Ollama fallback also failed: {e}")


def _parse_script_json(raw_text: str, topic: str) -> dict[str, Any]:
    """Parse LLM output as JSON. Strip markdown fences if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"Script JSON parse error: {e}\nRaw: {text[:500]}")
        # Return a minimal fallback structure
        return {
            "title_hook": f"Did you know about {topic}?",
            "segments": [
                {
                    "text": f"Let's talk about {topic}.",
                    "duration_hint_sec": 8,
                    "image_prompt": f"A cinematic background image about {topic}, ultra-detailed, 8k.",
                    "caption_style": "highlight",
                }
            ],
            "cta": "Follow for more AI tips!",
            "total_estimated_duration": 30,
        }


# ── Public API ────────────────────────────────────────────────────────────────

def generate_script(topic: str, angle: str = "", niche: str | None = None) -> dict[str, Any]:
    """
    Generate a structured YouTube Shorts script for the given topic.

    Args:
        topic: The trending topic or title.
        angle: Optional suggested angle from Idea Explorer.
        niche: Explicit niche override. Auto-detected if None.

    Returns:
        Structured script dict with title_hook, segments, cta, total_estimated_duration.
    """
    if niche is None:
        niche = _detect_niche(topic)

    prompt = _build_prompt(topic, angle, niche)
    logger.info(f"Generating script for: '{topic}' (niche={niche})")

    raw: str = ""
    has_valid_groq_key = bool(settings.groq_api_key and not settings.groq_api_key.startswith("your_"))

    if has_valid_groq_key:
        try:
            raw = _call_groq(prompt)
            logger.info("Script generated via Groq")
        except Exception as e:
            logger.warning(f"Groq failed: {e} — trying Ollama fallback")

    if not raw:
        try:
            raw = _call_ollama(prompt)
            logger.info("Script generated via Ollama fallback")
        except Exception as e:
            logger.warning(f"Ollama fallback unavailable ({e}) — generating placeholder script for local testing")
            raw = ""

    script = _parse_script_json(raw, topic)
    script["_topic"] = topic
    script["_niche"] = niche
    return script

