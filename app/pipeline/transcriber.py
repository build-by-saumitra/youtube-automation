"""
app/pipeline/transcriber.py — faster-whisper word-level timestamp extraction.

Produces:
  - narration.srt  (SubRip subtitles)
  - narration_words.json  (word-level timing for FFmpeg drawtext captions)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel  # type: ignore
from loguru import logger

# Cache the model instance so it's only loaded once per process
_model_instance: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model_instance
    if _model_instance is None:
        # Use 'base.en' for CPU; automatically uses 'int8' quantization on ARM
        logger.info("[Transcriber] Loading faster-whisper model (base.en)...")
        _model_instance = WhisperModel("base.en", device="cpu", compute_type="int8")
        logger.info("[Transcriber] Model loaded.")
    return _model_instance


def _format_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timecode HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_audio(audio_path: str, job_id: str, output_dir: str) -> dict[str, Any]:
    """
    Transcribe audio file using faster-whisper.

    Args:
        audio_path: Path to narration WAV file.
        job_id: Pipeline job ID.
        output_dir: Base output directory.

    Returns:
        Dict with keys:
          - srt_path: path to generated .srt file
          - words_path: path to word-level JSON timestamp file
          - words: list of {word, start, end} dicts
          - full_text: complete transcript text
    """
    job_dir = Path(output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    srt_path = str(job_dir / "narration.srt")
    words_path = str(job_dir / "narration_words.json")

    logger.info(f"[Transcriber] Transcribing: {audio_path}")

    model = _get_model()
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        beam_size=5,
    )

    logger.info(f"[Transcriber] Detected language: {info.language} ({info.language_probability:.2%})")

    # Collect words + build SRT
    all_words: list[dict] = []
    srt_lines: list[str] = []
    seg_index = 1

    for segment in segments:
        # SRT entry per segment
        srt_lines.append(str(seg_index))
        srt_lines.append(f"{_format_srt_time(segment.start)} --> {_format_srt_time(segment.end)}")
        srt_lines.append(segment.text.strip())
        srt_lines.append("")
        seg_index += 1

        # Word-level entries
        if segment.words:
            for word in segment.words:
                all_words.append({
                    "word": word.word.strip(),
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                })

    # Write SRT
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    # Write word-level JSON
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(all_words, f, indent=2)

    full_text = " ".join(w["word"] for w in all_words)
    logger.info(f"[Transcriber] Done: {len(all_words)} words, {seg_index - 1} segments")

    return {
        "srt_path": srt_path,
        "words_path": words_path,
        "words": all_words,
        "full_text": full_text,
    }
