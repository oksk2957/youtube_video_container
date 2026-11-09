"""Scene-motion sampling and optional on-screen OCR, including videos without speech."""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from media import run
from session_manager import Session

FRAME_W, FRAME_H = 160, 90
FRAME_BYTES = FRAME_W * FRAME_H


def motion_scores(source: Path, duration: float, session: Session | None = None) -> list[float]:
    raw = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-v", "error",
        "-i", str(source), "-vf", "fps=1,scale=160:90,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ], session=session, timeout=300)
    if not raw:
        return [0.0] * math.ceil(duration)
    scores = [0.0]
    previous = raw[:FRAME_BYTES]
    for position in range(FRAME_BYTES, len(raw) - FRAME_BYTES + 1, FRAME_BYTES):
        if session:
            session.check()
        current = raw[position:position + FRAME_BYTES]
        # Pixel subsampling keeps CPU use low even on lengthy videos.
        samples = zip(current[::8], previous[::8])
        difference = sum(abs(a - b) for a, b in samples) / (FRAME_BYTES / 8 * 255)
        scores.append(round(difference, 4))
        previous = current
    return scores


def ocr_at(source: Path, when: float, session: Session | None = None) -> str:
    if not shutil.which("tesseract"):
        return ""
    try:
        picture = run([
            "ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-ss", str(when),
            "-i", str(source), "-frames:v", "1", "-vf", "scale=640:-2",
            "-f", "image2pipe", "-vcodec", "png", "-",
        ], session=session, timeout=15)
        proc = subprocess.run(["tesseract", "stdin", "stdout", "-l", "kor+eng"],
                              input=picture, capture_output=True, timeout=12)
        if proc.returncode:
            proc = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng"],
                                  input=picture, capture_output=True, timeout=12)
        if proc.returncode:
            return ""
        return " ".join(proc.stdout.decode("utf-8", errors="ignore").split())[:160]
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return ""


def visual_windows(source: Path, duration: float, session: Session | None = None) -> tuple[list[dict], bool]:
    scores = motion_scores(source, duration, session=session)
    windows = []
    has_ocr = False
    total = math.ceil(duration / 5)
    if total > 360:
        raise ValueError("장면 분석은 최대 30분 영상까지 지원합니다.")
    for i in range(total):
        start = i * 5.0
        end = min(duration, start + 5)
        if end - start < 0.2:
            continue
        strength = max(scores[int(start):max(int(start) + 1, math.ceil(end))] or [0.0])
        description = f"Time {start:.1f}-{end:.1f}s, normalized visual change score {strength:.3f}"
        # OCR is optional, sparse and only captures actual on-screen text; no fabricated labels.
        if i % 6 == 0 and shutil.which("tesseract"):
            text = ocr_at(source, min(duration - 0.2, start + 2), session=session)
            if text:
                description += "; unverified screen OCR: " + text
                has_ocr = True
        windows.append({"start": start, "end": round(end, 3), "text": description})
    return windows, has_ocr


def add_screen_text(source: Path, transcript: list[dict], session: Session | None = None) -> list[dict]:
    if not shutil.which("tesseract"):
        return transcript
    # A few screenshots provide extra context without modifying spoken subtitle text.
    samples = {}
    every = max(1, len(transcript) // 12)
    for index in range(0, len(transcript), every):
        if session:
            session.check()
        text = ocr_at(source, transcript[index]["start"] + 0.2, session=session)
        if text:
            samples[index] = text
    augmented = []
    for index, segment in enumerate(transcript):
        item = dict(segment)
        if samples:
            sample_index = max((k for k in samples if k <= index), default=None)
            if sample_index is not None and index - sample_index <= every:
                item["text"] += " [possibly imperfect on-screen OCR: " + samples[sample_index] + "]"
        augmented.append(item)
    return augmented
