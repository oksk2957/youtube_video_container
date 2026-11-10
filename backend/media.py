"""FFprobe and cancellable FFmpeg rendering; originals are never modified."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path

from session_manager import EditCancelled, Session


def run(command: list[str], session: Session | None = None, timeout: int = 900,
        cwd: Path | None = None) -> bytes:
    start = time.monotonic()
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    if session:
        with session.lock:
            session.process = proc
    try:
        while True:
            if session:
                session.check()
            if time.monotonic() - start > timeout:
                raise TimeoutError("영상 분석 또는 FFmpeg 작업 시간이 초과되었습니다.")
            try:
                stdout, stderr = proc.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                continue
        if session:
            session.check()
        if proc.returncode:
            # Avoid leaking local paths or media transcript into user-facing errors.
            raise RuntimeError("FFmpeg/FFprobe 실행 실패: " + stderr.decode(errors="replace")[-500:])
        return stdout
    except BaseException:
        if proc.poll() is None:
            proc.kill()
        proc.communicate()
        raise
    finally:
        if session:
            with session.lock:
                if session.process is proc:
                    session.process = None


def probe(path: Path) -> dict:
    raw = run([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path),
    ], timeout=30)
    data = json.loads(raw.decode())
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("영상 스트림이 없는 파일입니다.")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    if not 0.5 <= duration <= 1800 or width <= 0 or height <= 0:
        raise ValueError("지원 범위: 0.5초~30분 길이의 정상 영상 파일입니다.")
    return {
        "duration": round(duration, 3),
        "width": width, "height": height,
        "has_audio": audio is not None,
        "video_codec": video.get("codec_name", "unknown"),
        "audio_codec": audio.get("codec_name", "none") if audio else "none",
    }


def extract_audio(source: Path, output: Path, session: Session):
    run([
        "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
        "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-b:a", "48k", str(output),
    ], session=session, timeout=400)
    if output.stat().st_size > 24 * 1024 * 1024:
        raise ValueError("음성 인식 파일이 AI 제공업체의 일반적인 업로드 제한을 초과했습니다.")


def timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def srt_captions(plan: dict, transcript: list[dict]) -> str:
    lines = []
    number = 1
    offset = 0.0
    for cut in plan["cuts"]:
        for segment in transcript[cut["first"]:cut["last"] + 1]:
            relative_start = max(0.0, segment["start"] - cut["start"])
            relative_end = min(cut["end"] - cut["start"], segment["end"] - cut["start"])
            if relative_end - relative_start < 0.08:
                continue
            text = " ".join(str(segment["text"]).replace("\r", " ").replace("\n", " ").split())
            if not text:
                continue
            # Two lines at most per subtitle, proportionally distributed in the ASR segment.
            chunks = textwrap.wrap(text, width=27, break_long_words=True, break_on_hyphens=False)
            groups = ["\n".join(chunks[i:i + 2]) for i in range(0, len(chunks), 2)]
            for index, caption in enumerate(groups):
                start = offset + relative_start + (relative_end - relative_start) * index / len(groups)
                end = offset + relative_start + (relative_end - relative_start) * (index + 1) / len(groups)
                lines.extend([str(number), timestamp(start) + " --> " + timestamp(end), caption, ""])
                number += 1
        offset += cut["end"] - cut["start"]
    return "\n".join(lines)


def video_filter(fmt: str) -> str:
    if fmt == "wide":
        return "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
    if fmt == "shorts":
        # No important slide margins or text are cropped; the blurred background fills the canvas.
        return (
            "[0:v:0]split=2[bg][fg];"
            "[bg]scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280,boxblur=12:3[blur];"
            "[fg]scale=720:1280:force_original_aspect_ratio=decrease[front];"
            "[blur][front]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1[v]"
        )
    raise ValueError("지원하지 않는 출력 비율입니다.")


def render(source: Path, output: Path, plan: dict, transcript: list[dict],
           fmt: str, enhance: bool, has_audio: bool, session: Session | None = None,
           progress=None) -> dict:
    folder = output.parent
    clips = []
    for index, cut in enumerate(plan["cuts"]):
        if session:
            session.check()
        segment_path = folder / f"clip_{index:03d}.mp4"
        cmd = [
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
            "-ss", str(cut["start"]), "-i", str(source),
        ]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        if fmt == "shorts":
            cmd += ["-filter_complex", video_filter(fmt), "-map", "[v]"]
        else:
            cmd += ["-vf", video_filter(fmt), "-map", "0:v:0"]
        cmd += [
            "-map", "0:a:0" if has_audio else "1:a:0",
            "-t", str(round(cut["end"] - cut["start"], 3)),
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-shortest", "-movflags", "+faststart", str(segment_path),
        ]
        run(cmd, session=session, timeout=1200)
        clips.append(segment_path)
        if progress:
            progress(60 + round(28 * (index + 1) / len(plan["cuts"])))

    playlist = folder / "concat.ffconcat"
    playlist.write_text(
        "ffconcat version 1.0\n" +
        "".join("file 'clip_" + f"{i:03d}" + ".mp4'\n" for i in range(len(clips))),
        encoding="utf-8",
    )
    merged = folder / "merged.mp4"
    run([
        "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
        "-safe", "0", "-f", "concat", "-i", str(playlist),
        "-c", "copy", str(merged),
    ], session=session, cwd=folder, timeout=600)

    captions = folder / "captions.srt"
    text = srt_captions(plan, transcript) if enhance and transcript else ""
    if text:
        captions.write_text(text, encoding="utf-8-sig")
        # Relative subtitle path in cwd avoids Windows drive-colon filter escaping.
        vf = ("subtitles=captions.srt:force_style='Fontname=Noto Sans CJK KR,"
              "Fontsize=22,Outline=2,Shadow=1,Alignment=2,MarginV=100'")
        cmd = [
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
            "-i", str(merged), "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "23", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output),
        ]
        run(cmd, session=session, cwd=folder, timeout=1200)
    elif enhance:
        run([
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error",
            "-i", str(merged), "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output),
        ], session=session, timeout=500)
    else:
        shutil.copyfile(merged, output)
    final = probe(output)
    expected = (720, 1280) if fmt == "shorts" else (1280, 720)
    if (final["width"], final["height"]) != expected:
        raise ValueError("렌더링 결과 영상 크기가 올바르지 않습니다.")
    if abs(final["duration"] - plan["actualSeconds"]) > 3:
        raise ValueError("렌더링 결과 길이가 편집 계획과 다릅니다.")
    return final
