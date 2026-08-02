"""
app/pipeline/video_assembler.py — FFmpeg + MoviePy video assembly for 9:16 YouTube Shorts.

Visual elements:
  - Ken Burns zoom/pan on each B-roll clip
  - Word-highlight captions (FFmpeg drawtext, one word at a time)
  - Progress bar timer at top (animated fill)
  - Background music (random pick from music/, ducked -12dB under voice)

Canvas: 1080x1920 (9:16), H.264 + AAC, crf=23
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
from pathlib import Path
import imageio_ffmpeg
from loguru import logger

from app.config import settings

def _get_ffmpeg() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


# ── Canvas Dimensions ─────────────────────────────────────────────────────────
W, H = 1080, 1920
CAPTION_ZONE_Y = int(H * 0.68)      # captions start at 68% from top
PROGRESS_BAR_H = 14                  # pixels tall
FONT_SIZE = 68
ACCENT_COLOR = "orange@1.0"          # animated progress bar color
CAPTION_BG = "black@0.6"             # semi-transparent black background box
TEXT_COLOR = "white"
HIGHLIGHT_COLOR = "yellow"           # active word color


# ── Helper: pick random royalty-free music track ───────────────────────────────

def _pick_music_track() -> str | None:
    music_dir = Path(settings.music_dir)
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    if not tracks:
        # Try fetching from API
        from app.pipeline.asset_manager import fetch_background_music
        track_path = fetch_background_music("lofi upbeat")
        if track_path:
            logger.info(f"[Assembler] Fetched API background music: {track_path}")
            return track_path
            
        logger.warning("[Assembler] No music tracks found in music/ and API fetch failed — skipping music")
        return None
    return str(random.choice(tracks))


# ── Ken Burns effect helper ────────────────────────────────────────────────────

def _apply_ken_burns(clip_path: str, out_path: str, duration: float) -> None:
    """Apply a slow zoom-in Ken Burns effect using FFmpeg zoompan filter."""
    cmd = [_get_ffmpeg(), "-y"]
    
    # If the input is an image, we need to loop it to create a video stream
    if clip_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        cmd += ["-loop", "1", "-framerate", "25"]
        
    cmd += ["-i", clip_path]
    
    cmd += [
        "-vf", (
            f"scale=2*{W}:2*{H}:force_original_aspect_ratio=increase,"
            f"crop=2*{W}:2*{H},"
            f"zoompan=z='if(lte(zoom,1.0),1.05,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={int(duration * 25)}:s={W}x{H}:fps=25,"
            f"scale={W}:{H}"
        ),
        "-t", str(duration),
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        out_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ── Build clips list from script + asset map ──────────────────────────────────

def _build_clip_segments(script: dict, asset_map: dict[str, str | None],
                         total_audio_duration: float, tmp_dir: str) -> list[tuple[str, float]]:
    """
    Map each script segment to a B-roll clip + duration.

    Returns list of (clip_path, duration_sec) for each segment.
    """
    segments = script.get("segments", [])
    if not segments:
        return []

    results: list[tuple[str, float]] = []
    remaining = total_audio_duration
    seg_count = len(segments)

    for i, seg in enumerate(segments):
        # Duration: evenly distribute audio time across segments
        seg_duration = round(remaining / (seg_count - i), 2)
        remaining -= seg_duration

        # Find clip for this segment's image prompt
        clip_path: str | None = None
        prompt = seg.get("image_prompt")
        
        # Fallback to visual_keywords if image_prompt is missing (for older cached jobs)
        if not prompt and seg.get("visual_keywords"):
            prompt = " ".join(seg.get("visual_keywords", []))
            
        if prompt and asset_map.get(prompt):
            clip_path = asset_map[prompt]

        if not clip_path:
            logger.warning(f"[Assembler] No clip for segment {i} — using styled canvas frame")
            # Create a styled colored canvas clip as fallback
            canvas_path = os.path.join(tmp_dir, f"black_{i}.mp4")
            _create_black_clip(canvas_path, seg_duration, index=i)
            clip_path = canvas_path

        # Apply Ken Burns to the clip
        kb_path = os.path.join(tmp_dir, f"clip_{i}_kb.mp4")
        try:
            _apply_ken_burns(clip_path, kb_path, seg_duration)
            results.append((kb_path, seg_duration))
        except Exception as e:
            logger.warning(f"[Assembler] Ken Burns failed for clip {i}: {e} — using raw clip")
            results.append((clip_path, seg_duration))

    return results


BACKGROUND_PALETTES = [
    "gradients=s=1080x1920:r=25:c0=0x0f172a:c1=0x1e1b4b:c2=0x312e81:c3=0x0284c7:speed=0.015,drawgrid=width=120:height=120:thickness=2:color=white@0.1",
    "gradients=s=1080x1920:r=25:c0=0x18002e:c1=0x3b0764:c2=0x581c87:c3=0x0f172a:speed=0.015,drawgrid=width=120:height=120:thickness=2:color=white@0.1",
    "gradients=s=1080x1920:r=25:c0=0x022c22:c1=0x064e3b:c2=0x0f172a:c3=0x0369a1:speed=0.015,drawgrid=width=120:height=120:thickness=2:color=white@0.1",
    "gradients=s=1080x1920:r=25:c0=0x03071e:c1=0x0f172a:c2=0x1e1b4b:c3=0x4338ca:speed=0.015,drawgrid=width=120:height=120:thickness=2:color=white@0.1",
    "gradients=s=1080x1920:r=25:c0=0x090d16:c1=0x111827:c2=0x1f2937:c3=0x0891b2:speed=0.015,drawgrid=width=120:height=120:thickness=2:color=white@0.1",
]


def _create_black_clip(out_path: str, duration: float, index: int = 0) -> None:
    """Create a high-end animated liquid gradient motion clip with tech grid for segments lacking stock footage."""
    grad = BACKGROUND_PALETTES[index % len(BACKGROUND_PALETTES)]
    cmd = [
        _get_ffmpeg(), "-y",
        "-f", "lavfi", "-i", grad,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ── Concatenate clips ──────────────────────────────────────────────────────────

def _concat_clips(clip_pairs: list[tuple[str, float]], concat_path: str) -> None:
    """Concatenate a list of clips using FFmpeg concat demuxer."""
    if not clip_pairs:
        raise ValueError("No clip pairs to concatenate")

    if len(clip_pairs) == 1:
        src = clip_pairs[0][0]
        cmd = [_get_ffmpeg(), "-y", "-i", src, "-c", "copy", concat_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"[Assembler] Single clip copy failed: {res.stderr}")
            raise RuntimeError(f"Clip copy failed: {res.stderr}")
        return

    list_file = concat_path + ".txt"
    with open(list_file, "w") as f:
        for clip_path, _ in clip_pairs:
            safe = clip_path.replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    cmd = [
        _get_ffmpeg(), "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        concat_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"[Assembler] Concat failed: {res.stderr}")
        raise RuntimeError(f"Concat failed: {res.stderr}")


def _generate_ass_file(words: list[dict], ass_path: str, is_kids: bool = False) -> None:
    """
    Generate an Advanced SubStation Alpha (.ass) subtitle file for CapCut-style captions.
    Uses bold fonts, drop shadows, and perfect vertical centering.
    """
    if not words:
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("")
        return

    # ASS Header and Styles
    ass_content = [
        "[Script Info]",
        "Title: CapCut Style Captions",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 1",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    
    # Kids get a super bright yellow, adults get white
    primary_color = "&H0000FFFF" if is_kids else "&H00FFFFFF"
    
    ass_content.append(f"Style: Default,Arial,96,{primary_color},&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,8,12,5,30,30,900,1")
    # Alignment 5 means exactly center of the screen
    ass_content.extend([
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ])

    def format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round(seconds % 1, 2) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # Group words for rapid pacing (Hormozi style)
    # 1 word per chunk unless it's a tiny connector word
    chunks: list[dict] = []
    i = 0
    while i < len(words):
        w1 = words[i]
        text = w1["word"].strip()
        start = w1["start"]
        end = w1["end"]
        
        # Combine if it's a tiny word (e.g. "a", "in", "is") and the next word is close
        if len(text) <= 3 and i + 1 < len(words) and (words[i + 1]["end"] - start) <= 0.8:
            w2 = words[i + 1]
            text = f"{text} {w2['word'].strip()}"
            end = w2["end"]
            i += 2
        else:
            i += 1
            
        chunks.append({"text": text, "start": start, "end": end})

    for idx, chunk in enumerate(chunks):
        start_t = format_time(chunk["start"])
        # Gapless subtitles
        if idx + 1 < len(chunks):
            end_t = format_time(chunks[idx + 1]["start"])
        else:
            end_t = format_time(chunk["end"])

        text = chunk["text"].replace("\\", "\\\\").replace("\n", "\\N")
        # Aggressive pop animation, NO fade out so it cuts instantly to the next word
        styled_text = f"{{\\fscx130\\fscy130\\t(0,100,\\fscx100\\fscy100)}}{text}"
        
        ass_content.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{styled_text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_content))


# ── Progress bar filter ────────────────────────────────────────────────────────

def _build_progress_bar_filter(total_duration: float) -> str:
    """Animated progress bar at the top of the frame."""
    return (
        f"drawbox=x=0:y=0:w='(t/{total_duration})*iw':h={PROGRESS_BAR_H}"
        f":color={ACCENT_COLOR}:t=fill"
    )


# ── Main Assembler ────────────────────────────────────────────────────────────

def assemble_video(
    script: dict[str, Any],
    audio_path: str,
    words: list[dict],
    asset_map: dict[str, str | None],
    job_id: str,
    output_dir: str,
    total_audio_duration: float,
) -> str:
    """
    Full video assembly pipeline.

    Args:
        script: Parsed script dict.
        audio_path: Path to synthesised narration WAV.
        words: Word-level timing list from transcriber.
        asset_map: Keyword → local clip path mapping.
        job_id: Pipeline job ID.
        output_dir: Base output directory.
        total_audio_duration: Duration of the narration audio (seconds).

    Returns:
        Path to the final rendered MP4 file.
    """
    job_dir = Path(output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    final_path = os.path.abspath(str(job_dir / "final.mp4"))
    audio_path = os.path.abspath(audio_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        logger.info(f"[Assembler] Building {len(script.get('segments', []))} clip segments")

        # 1. Build Ken Burns B-roll clips
        clip_segments = _build_clip_segments(script, asset_map, total_audio_duration, tmp_dir)

        # 2. Concatenate clips into a single background video
        raw_concat = os.path.abspath(os.path.join(tmp_dir, "concat.mp4"))
        _concat_clips(clip_segments, raw_concat)

        # 3. Build FFmpeg overlay filter chain
        vf_parts: list[str] = []

        # Scale to exact canvas
        vf_parts.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")

        # Progress bar
        vf_parts.append(_build_progress_bar_filter(total_audio_duration))

        # Word-highlight captions (.ass subtitles)
        ass_path = os.path.abspath(os.path.join(tmp_dir, "captions.ass"))
        is_kids = script.get("_niche") == "kids"
        _generate_ass_file(words, ass_path, is_kids=is_kids)
        # We need to escape the path for the FFmpeg filter
        safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
        vf_parts.append(f"ass='{safe_ass_path}'")

        vf_filter = "[0:v]" + ",".join(vf_parts) + "[vout]"

        # 4. Pick background music
        music_path = _pick_music_track()

        filter_lines = [vf_filter]
        if music_path:
            # Mix: voice + ducked music (-12dB)
            audio_filter = (
                "[1:a]volume=1.0[voice];"
                f"[2:a]volume=0.18,afade=in:d=1,afade=out:st={max(0, total_audio_duration - 2)}:d=2[music];"
                "[voice][music]amix=inputs=2:duration=first[aout]"
            )
            filter_lines.append(audio_filter)

        # Write filter graph to temp file
        filter_script_path = os.path.abspath(os.path.join(tmp_dir, "filter_graph.txt"))
        with open(filter_script_path, "w", encoding="utf-8") as f:
            f.write(";\n".join(filter_lines))

        # 5. Final FFmpeg render
        cmd = [_get_ffmpeg(), "-y"]

        # Input 0: concatenated video
        cmd += ["-i", raw_concat]
        # Input 1: narration audio
        cmd += ["-i", audio_path]

        if music_path:
            # Input 2: background music
            cmd += ["-i", music_path]
            cmd += [
                "-filter_complex_script", filter_script_path,
                "-map", "[vout]",
                "-map", "[aout]",
            ]
        else:
            cmd += [
                "-filter_complex_script", filter_script_path,
                "-map", "[vout]",
                "-map", "1:a",
            ]

        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-t", f"{total_audio_duration + 0.5:.2f}",
            final_path,
        ]

        logger.info(f"[Assembler] Running final FFmpeg render with cmd: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"[Assembler] FFmpeg error:\n{result.stderr[-2000:]}")
            raise RuntimeError(f"FFmpeg render failed for job {job_id}")

        size_mb = Path(final_path).stat().st_size / 1_048_576
        logger.info(f"[Assembler] Done: {final_path} ({size_mb:.1f}MB)")

    return final_path
