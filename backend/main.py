"""Local-only FastAPI backend for temporary AI video editing sessions."""
from __future__ import annotations

import asyncio
import logging
import ntpath
import os
import shutil
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from media import probe
from pipeline import process_session
from session_manager import BASE_DIR, COOKIE_NAME, EditCancelled, Session, manager

LOG = logging.getLogger("one-shot-backend")
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
ALLOWED_SUFFIXES = {".mp4", ".mov", ".webm"}
FRONTEND_ORIGIN = "http://127.0.0.1:3000"


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.sweep()
    exit_flag = threading.Event()
    def garbage_collector():
        while not exit_flag.wait(60):
            manager.sweep()
    sweeper = threading.Thread(target=garbage_collector, daemon=True, name="temp-cleaner")
    sweeper.start()
    yield
    exit_flag.set()
    with manager.lock:
        items = list(manager.sessions.values())
    for item in items:
        manager.close(item)


app = FastAPI(title="One-Shot AI Video Editor", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
)


@app.middleware("http")
async def protect_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("origin") != FRONTEND_ORIGIN:
            return JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class EditSettings(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    chat_model: str = Field(min_length=1, max_length=120)
    asr_model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(default="", max_length=4096)
    format: Literal["shorts", "wide"] = "shorts"
    style: Literal["auto", "news", "dynamic", "calm"] = "auto"
    target_seconds: Literal[30, 45, 60, 120] = 45
    enhance: bool = True


def authorized(request: Request, sid: str) -> Session:
    session = manager.identify(sid, request.cookies.get(COOKIE_NAME))
    if not session:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다. 다시 업로드해 주세요.")
    return session


def validate_video_signature(head: bytes, ext: str):
    if ext in {".mp4", ".mov"} and b"ftyp" not in head[:32]:
        raise HTTPException(status_code=400, detail="MP4/MOV 파일의 실제 형식이 올바르지 않습니다.")
    if ext == ".webm" and not head.startswith(b"\x1a\x45\xdf\xa3"):
        raise HTTPException(status_code=400, detail="WebM 파일의 실제 형식이 올바르지 않습니다.")


@app.get("/api/health")
def health():
    return {"app": "one-shot-local", "storage": "temporary-local", "ok": True,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None}


@app.post("/api/sessions", status_code=201)
async def upload_video(request: Request, file: UploadFile = File(...)):
    filename = ntpath.basename(file.filename or "video.mp4")[:200]
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="MP4, MOV, WebM 파일만 업로드할 수 있습니다.")
    existing = manager.by_token(request.cookies.get(COOKIE_NAME))
    if existing:
        if existing.worker and existing.worker.is_alive():
            raise HTTPException(status_code=409, detail="이전 작업을 먼저 종료해 주세요.")
        manager.close(existing)
    folder = Path(tempfile.mkdtemp(prefix="session-", dir=BASE_DIR))
    source = folder / ("source" + suffix)
    total = 0
    try:
        if shutil.disk_usage(BASE_DIR).free < 512 * 1024 * 1024:
            raise HTTPException(status_code=507, detail="영상 편집을 위한 디스크 공간이 부족합니다.")
        with source.open("wb") as out:
            first = await file.read(4 * 1024 * 1024)
            validate_video_signature(first, suffix)
            while first:
                total += len(first)
                if total > MAX_UPLOAD:
                    raise HTTPException(status_code=413, detail="파일 크기는 최대 1GiB입니다.")
                out.write(first)
                first = await file.read(4 * 1024 * 1024)
        if total == 0:
            raise HTTPException(status_code=400, detail="비어 있는 파일입니다.")
        meta = await asyncio.to_thread(probe, source)
        if meta["width"] > 4096 or meta["height"] > 4096:
            raise HTTPException(status_code=422, detail="4096px 이하의 영상을 사용해 주세요.")
        session = manager.create(folder, source, filename, meta)
        response = JSONResponse({
            "session_id": session.id,
            "filename": filename,
            "duration": meta["duration"],
            "width": meta["width"],
            "height": meta["height"],
            "has_audio": meta["has_audio"],
        }, status_code=201)
        response.set_cookie(
            COOKIE_NAME, session.token, max_age=3600, httponly=True,
            secure=False, samesite="lax", path="/",
        )
        return response
    except HTTPException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        LOG.warning("Upload or media probing rejected: %s", type(exc).__name__)
        raise HTTPException(status_code=422, detail="영상 파일을 읽지 못했습니다. 인코딩과 파일 상태를 확인하세요.") from exc
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await file.close()


@app.get("/api/sessions/{sid}/status")
def status(request: Request, sid: str):
    return authorized(request, sid).snapshot()


def perform_edit(session: Session, settings: EditSettings):
    try:
        process_session(session, settings)
    except EditCancelled:
        with session.lock:
            session.status = "CANCELLED"
            session.message = "편집 작업이 취소되었습니다. 설정을 바꿔 다시 시도할 수 있습니다."
            session.error = None
    except Exception as exc:
        LOG.exception("Auto edit failed with %s", type(exc).__name__)
        with session.lock:
            session.status = "FAILED"
            session.message = "자동 편집에 실패했습니다."
            session.error = str(exc)[:350] if isinstance(exc, ValueError) else "영상 처리 또는 AI 연결에 실패했습니다. 서버 로그를 확인하세요."
    finally:
        with session.lock:
            session.process = None


@app.post("/api/sessions/{sid}/start")
def start_edit(request: Request, sid: str, settings: EditSettings):
    session = authorized(request, sid)
    with session.lock:
        if session.worker and session.worker.is_alive():
            raise HTTPException(status_code=409, detail="이전 편집 작업이 아직 진행 중입니다.")
        if session.closed:
            raise HTTPException(status_code=404, detail="이미 종료된 작업입니다.")
        session.cancellation = threading.Event()
        session.status = "ANALYZING"
        session.progress = 2
        session.message = "원본 영상을 분석하고 있습니다."
        session.error = None
        session.analysis_mode = None
        session.title = None
        thread = threading.Thread(target=perform_edit, args=(session, settings),
                                  daemon=True, name="video-edit-" + session.id[:8])
        session.worker = thread
        thread.start()
    return session.snapshot()


@app.post("/api/sessions/{sid}/cancel")
def cancel_edit(request: Request, sid: str):
    session = authorized(request, sid)
    manager.cancel(session)
    return session.snapshot()


@app.get("/api/sessions/{sid}/output")
def output_preview(request: Request, sid: str):
    session = authorized(request, sid)
    with session.lock:
        result = session.output if session.status == "COMPLETED" else None
    if not result or not result.exists():
        raise HTTPException(status_code=404, detail="완성된 영상이 없습니다.")
    return FileResponse(result, media_type="video/mp4", headers={"Content-Disposition": "inline"})


@app.get("/api/sessions/{sid}/download")
def download(request: Request, sid: str):
    session = authorized(request, sid)
    with session.lock:
        result = session.output if session.status == "COMPLETED" else None
    if not result or not result.exists():
        raise HTTPException(status_code=404, detail="완성된 영상이 없습니다.")
    return FileResponse(result, media_type="video/mp4", filename="ai-edited.mp4")


@app.delete("/api/sessions/{sid}")
def close_session(request: Request, sid: str):
    session = authorized(request, sid)
    manager.close(session)
    response = JSONResponse({"ok": True, "message": "임시 작업을 종료하고 정리했습니다."})
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    return response
