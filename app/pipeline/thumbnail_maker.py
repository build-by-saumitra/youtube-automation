"""
app/pipeline/thumbnail_maker.py — Auto-generated thumbnails using HTML/CSS + Playwright.

Template: High-end web-based template (glassmorphism, gradients, Google Fonts).
Output: 1280×720 JPEG (YouTube thumbnail standard).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from loguru import logger

import imageio_ffmpeg

def _get_ffmpeg() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _extract_thumbnail_frame(video_path: str, job_dir: str) -> str | None:
    """Extract a visually rich frame from the video using FFmpeg (at 20% mark)."""
    frame_path = os.path.join(job_dir, "thumb_frame.jpg")
    cmd = [
        _get_ffmpeg(), "-y",
        "-ss", "00:00:03",
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        frame_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(frame_path):
        return frame_path
    return None


def create_thumbnail(
    title: str,
    video_path: str,
    job_id: str,
    output_dir: str,
    niche: str = "AI & Tech",
    accent_color: tuple[int, int, int] | str = "#ff5722",
) -> str:
    """
    Generate a stunning YouTube thumbnail for a Short using HTML/CSS & Playwright.

    Args:
        title: Video title text to overlay.
        video_path: Path to the assembled video (used to extract a frame).
        job_id: Pipeline job ID.
        output_dir: Base output directory.
        niche: Short niche label shown in bottom strip.
        accent_color: Accent color (hex string).

    Returns:
        Path to the generated 1280×720 JPEG thumbnail.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[Thumbnail] Playwright not installed. Run: uv pip install playwright && uv run playwright install chromium")
        raise RuntimeError("Playwright not installed.")

    job_dir = str(Path(output_dir) / job_id)
    Path(job_dir).mkdir(parents=True, exist_ok=True)
    
    html_path = os.path.join(job_dir, "thumbnail.html")
    thumb_path = os.path.join(job_dir, "thumbnail.jpg")

    # Ensure accent_color is a hex string
    if isinstance(accent_color, tuple):
        accent_color = f"#{accent_color[0]:02x}{accent_color[1]:02x}{accent_color[2]:02x}"

    # Extract background frame
    frame_path = _extract_thumbnail_frame(video_path, job_dir)
    if frame_path:
        bg_url = f"file://{os.path.abspath(frame_path)}"
    else:
        bg_url = "" # Fallback to CSS gradient

    bg_style = f"background-image: url('{bg_url}'); background-size: cover; background-position: center;" if bg_url else "background: linear-gradient(135deg, #0f172a, #1e1b4b, #090d16);"

    # HTML Template
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1280, height=720, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@800&family=Inter:wght@600&display=swap" rel="stylesheet">
        <style>
            body {{
                margin: 0;
                padding: 0;
                width: 1280px;
                height: 720px;
                {bg_style}
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                font-family: 'Outfit', sans-serif;
                overflow: hidden;
                position: relative;
            }}
            .overlay {{
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.1) 100%);
                z-index: 1;
            }}
            .content {{
                position: relative;
                z-index: 2;
                text-align: center;
                padding: 40px;
                width: 90%;
            }}
            .title {{
                color: #ffffff;
                font-size: 110px;
                font-weight: 800;
                line-height: 1.1;
                text-transform: uppercase;
                text-shadow: 0px 10px 20px rgba(0,0,0,0.8), 0px 0px 40px rgba(255,255,255,0.2);
                margin-bottom: 40px;
            }}
            .highlight {{
                color: #fbbf24; /* yellow-400 */
            }}
            .niche-strip {{
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 80px;
                background-color: {accent_color};
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 2;
                box-shadow: 0px -5px 20px rgba(0,0,0,0.5);
            }}
            .niche-text {{
                color: #ffffff;
                font-family: 'Inter', sans-serif;
                font-size: 44px;
                font-weight: 600;
                letter-spacing: 4px;
                text-transform: uppercase;
                text-shadow: 0px 4px 10px rgba(0,0,0,0.3);
            }}
            .glass-box {{
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 30px;
                padding: 40px 60px;
                display: inline-block;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }}
        </style>
    </head>
    <body>
        <div class="overlay"></div>
        <div class="content">
            <div class="glass-box">
                <div class="title">{title.replace('Python', '<span class="highlight">Python</span>').replace('Secret', '<span class="highlight">Secret</span>')}</div>
            </div>
        </div>
        <div class="niche-strip">
            <div class="niche-text">⚡ {niche}</div>
        </div>
    </body>
    </html>
    """

    with open(html_path, "w") as f:
        f.write(html_content)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(f"file://{os.path.abspath(html_path)}")
        # Wait a moment for fonts/images to load
        page.wait_for_timeout(500)
        page.screenshot(path=thumb_path, type="jpeg", quality=92)
        browser.close()

    logger.info(f"[Thumbnail] HTML rendering complete. Saved: {thumb_path}")
    return thumb_path
