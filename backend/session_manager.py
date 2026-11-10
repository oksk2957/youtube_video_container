"""Temporary, cookie-bound edit sessions. No database and no persistent credentials."""
from __future__ import annotations

import hmac
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(tempfile.gettempdir()) / "one-shot-ai-video-editor"
BASE_DIR.mkdir(parents=True, exist_ok=True)
MAX_AGE_SECONDS = 60 * 60
FOLDER_PREFIX = "session-"
COOKIE_NAME = "one_shot_session"


class EditCancelled(Exception):
    pass


@dataclass
class Session:
    id: str
    token: str
    folder: Path
    source: Path
    filename: str
    metadata: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    status: str = "READY"
    progress: int = 0
    message: str = "업로드가 완료되었습니다."
    error: str | None = None
    title: str | None = None
    analysis_mode: str | None = None
    output_duration: float | None = None
    output: Path | None = None
    closed: bool = False
    cancellation: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    worker: threading.Thread | None = field(default=None, repr=False)
    process: subprocess.Popen | None = field(default=None, repr=False)

    def update(self, status: str | None = None, progress: int | None = None,
               message: str | None = None):
        with self.lock:
            if self.closed or self.cancellation.is_set():
                raise EditCancelled()
            if status is not None:
                self.status = status
            if progress is not None:
                self.progress = max(0, min(100, progress))
            if message is not None:
                self.message = message

    def check(self):
        if self.cancellation.is_set() or self.closed:
            raise EditCancelled()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "error": self.error,
                "title": self.title,
                "analysis_mode": self.analysis_mode,
                "has_output": bool(self.output and self.output.exists()),
                "output_duration": self.output_duration,
            }


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()

    def create(self, folder: Path, source: Path, filename: str, metadata: dict) -> Session:
        new = Session(
            id=uuid.uuid4().hex,
            token=uuid.uuid4().hex + uuid.uuid4().hex,
            folder=folder,
            source=source,
            filename=filename,
            metadata=metadata,
        )
        with self.lock:
            self.sessions[new.id] = new
        return new

    def identify(self, sid: str, token: str | None) -> Session | None:
        with self.lock:
            item = self.sessions.get(sid)
        if not item or not token or not hmac.compare_digest(item.token, token):
            return None
        with item.lock:
            if item.closed:
                return None
            item.last_seen = time.time()
        return item

    def by_token(self, token: str | None) -> Session | None:
        if not token:
            return None
        with self.lock:
            candidates = list(self.sessions.values())
        for candidate in candidates:
            if hmac.compare_digest(candidate.token, token):
                return candidate
        return None

    def cancel(self, item: Session):
        with item.lock:
            item.cancellation.set()
            if item.status not in {"COMPLETED", "FAILED", "CANCELLED", "READY"}:
                item.status = "CANCELLING"
                item.message = "실행 중인 작업을 취소하고 있습니다."
            proc = item.process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def close(self, item: Session):
        self.cancel(item)
        with item.lock:
            item.closed = True
            thread = item.worker
        with self.lock:
            self.sessions.pop(item.id, None)
        if thread and thread.is_alive():
            threading.Thread(target=self._cleanup_after_thread,
                             args=(thread, item.folder), daemon=True).start()
        else:
            self._delete(item.folder)

    @staticmethod
    def _delete(folder: Path):
        if re.fullmatch(r"session-[0-9a-f]{32}", folder.name) and folder.parent == BASE_DIR:
            shutil.rmtree(folder, ignore_errors=True)

    def _cleanup_after_thread(self, thread: threading.Thread, folder: Path):
        thread.join(timeout=330)
        if not thread.is_alive():
            self._delete(folder)

    def sweep(self):
        now = time.time()
        with self.lock:
            known = list(self.sessions.values())
        for item in known:
            if now - item.last_seen > MAX_AGE_SECONDS:
                self.close(item)
        with self.lock:
            active_folders = {s.folder for s in self.sessions.values()}
        for folder in BASE_DIR.glob(FOLDER_PREFIX + "*"):
            if folder in active_folders or not folder.is_dir():
                continue
            try:
                if now - folder.stat().st_mtime > MAX_AGE_SECONDS:
                    self._delete(folder)
            except OSError:
                pass


manager = SessionManager()
