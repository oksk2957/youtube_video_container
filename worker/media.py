"""FFmpeg media operations: preserve original media, render clips, burn exact ASR captions."""
import json
import subprocess
import textwrap
from pathlib import Path


def run(command: list[str], timeout: int = 1800):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("Media command failed: " + result.stderr[-1200:])
    return result.stdout


def probe(source: Path) -> dict:
    data = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(source)]))
    video = next((x for x in data["streams"] if x["codec_type"] == "video"), None)
    audio = next((x for x in data["streams"] if x["codec_type"] == "audio"), None)
    if not video:
        raise ValueError("Uploaded media has no video stream")
    duration = float(data["format"].get("duration") or 0)
    if not 1 <= duration <= 3600:
        raise ValueError("Supported source duration is from 1 second to 60 minutes")
    if not audio:
        raise ValueError("Auto-edit currently needs a video with a spoken audio track")
    return {"duration": duration, "width": int(video["width"]),
            "height": int(video["height"]), "audio": True}


def extract_audio(source: Path, destination: Path):
    run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
         "-b:a", "48k", str(destination)])
    if destination.stat().st_size > 24 * 1024 * 1024:
        raise ValueError("Transcription audio is larger than API limit")


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    sec, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{sec:02},{milliseconds:03}"


def srt_captions(plan: dict, transcript: list[dict]) -> str:
    lines = []
    offset = 0.0
    number = 1
    for cut in plan["cuts"]:
        for word in transcript[cut["first"]:cut["last"] + 1]:
            start = offset + max(0.0, word["start"] - cut["start"])
            end = offset + min(cut["end"] - cut["start"], word["end"] - cut["start"])
            if end <= start:
                continue
            # Caption text is taken only from ASR, never AI-invented.
            content = word["text"].replace("\n", " ").replace("\r", " ").strip()
            wrapped = "\n".join(textwrap.wrap(content, 32, break_long_words=True))
            lines.extend([str(number), timestamp(start) + " --> " + timestamp(end), wrapped, ""])
            number += 1
        offset += cut["end"] - cut["start"]
    return "\n".join(lines)


def video_filter(format_name: str) -> str:
    if format_name == "wide":
        return "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
    if format_name == "shorts":
        # Entire 16:9 slide stays visible; blurred backdrop fills the 9:16 canvas.
        return ("[0:v:0]split=2[bg][fg];"
                "[bg]scale=720:1280:force_original_aspect_ratio=increase,"
                "crop=720:1280,boxblur=12:3[blur];"
                "[fg]scale=720:1280:force_original_aspect_ratio=decrease[front];"
                "[blur][front]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1[v]")
    raise ValueError("Unknown export format")


def render(source: Path, destination: Path, plan: dict, transcript: list[dict],
           format_name: str, progress=None) -> dict:
    scratch = destination.parent
    clips = []
    for index, cut in enumerate(plan["cuts"]):
        clip_file = scratch / f"cut_{index:03d}.mp4"
        cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error",
               "-ss", str(cut["start"]), "-i", str(source),
               "-t", str(round(cut["end"] - cut["start"], 3))]
        if format_name == "shorts":
            cmd += ["-filter_complex", video_filter(format_name), "-map", "[v]"]
        else:
            cmd += ["-vf", video_filter(format_name), "-map", "0:v:0"]
        cmd += ["-map", "0:a:0", "-r", "30", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
                "-movflags", "+faststart", str(clip_file)]
        run(cmd)
        clips.append(clip_file)
        if progress:
            progress(60 + round((index + 1) / len(plan["cuts"]) * 25))

    playlist = scratch / "cuts.ffconcat"
    playlist.write_text("ffconcat version 1.0\n" +
                        "".join("file '" + str(path) + "'\n" for path in clips), encoding="utf-8")
    combined = scratch / "combined.mp4"
    run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-safe", "0", "-f", "concat",
         "-i", str(playlist), "-c", "copy", str(combined)])
    captions = scratch / "captions.srt"
    captions.write_text(srt_captions(plan, transcript), encoding="utf-8")
    captions_filter = (
        "subtitles=" + str(captions) +
        ":force_style='Fontname=Noto Sans CJK KR,Fontsize=24,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "Outline=2,Shadow=1,Alignment=2,MarginV=100'"
    )
    run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(combined),
         "-vf", captions_filter, "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(destination)])
    result = probe(destination)
    if abs(result["duration"] - plan["actualSeconds"]) > 3:
        raise ValueError("Final output duration differs significantly from planned duration")
    return result
