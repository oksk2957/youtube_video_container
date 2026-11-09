"""Explicit cleanup after stop.bat has terminated the local backend."""
import re
import shutil
from pathlib import Path

from session_manager import BASE_DIR


def clear_temp():
    removed = 0
    for candidate in BASE_DIR.iterdir():
        if candidate.is_dir() and re.fullmatch(r"session-[0-9a-f]{32}", candidate.name):
            shutil.rmtree(candidate, ignore_errors=True)
            if not candidate.exists():
                removed += 1
    return removed


if __name__ == "__main__":
    print("Temporary editing folders removed:", clear_temp())
