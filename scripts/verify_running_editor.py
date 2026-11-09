"""Confirm the dedicated 3100/8100 services really belong to One-Shot Studio."""
from __future__ import annotations

import json
import sys
import time
from urllib.request import urlopen

WEB = "http://127.0.0.1:3100/"
API = "http://127.0.0.1:8100/api/health"


def compatible_health(data: dict) -> bool:
    return (data.get("app") == "one-shot-local"
            and data.get("storage") == "temporary-local"
            and data.get("ok") is True
            and data.get("ffmpeg") is True
            and data.get("ffprobe") is True)


def correct_frontend(html: str) -> bool:
    return "ONE-SHOT STUDIO" in html and "AI 영상 자동 편집기" in html


def get_status() -> tuple[bool, str]:
    try:
        with urlopen(API, timeout=3) as response:
            health = json.load(response)
        if not compatible_health(health):
            return False, "Python API is not the local one-shot editor, or FFmpeg is missing."
        with urlopen(WEB, timeout=3) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")
        if not correct_frontend(html):
            return False, "Port 3100 does not serve the expected One-Shot Studio homepage."
        return True, "One-shot editor verified (local upload, no S3)."
    except (OSError, TimeoutError, ValueError, KeyError) as error:
        return False, "Still connecting: " + type(error).__name__


def main() -> int:
    print("[CHECK] Verifying live Next.js and FastAPI identities...", flush=True)
    deadline = time.monotonic() + 75
    last = ""
    while time.monotonic() < deadline:
        good, message = get_status()
        if good:
            print("[OK] " + message)
            print("[OPEN] " + WEB)
            print("[INFO] Do NOT open localhost:3000 (legacy S3 editor).")
            return 0
        last = message
        time.sleep(1)
    print("[ERROR] The dedicated one-shot editor did not become ready.")
    print("[ERROR] " + last)
    print("[FIX] Check the OneShot-Backend / OneShot-Frontend terminal windows.")
    print("[FIX] The legacy S3 app at http://localhost:3000 is NOT the correct editor.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
