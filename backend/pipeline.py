"""End-to-end ephemeral AI edit pipeline. No S3, login, database or project state."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from media import extract_audio, render
from planner import make_plan
from provider import AIProvider
from session_manager import Session
from visual import add_screen_text, visual_windows


def process_session(session: Session, settings):
    provider = AIProvider(settings.base_url, settings.chat_model, settings.asr_model, settings.api_key)
    try:
        with tempfile.TemporaryDirectory(prefix="render-", dir=session.folder) as workspace:
            temp = Path(workspace)
            metadata = session.metadata
            duration = metadata["duration"]
            session.update("ANALYZING", 8, "영상과 오디오 특성을 분석합니다.")
            transcript: list[dict] = []
            if metadata["has_audio"]:
                audio = temp / "speech.mp3"
                extract_audio(session.source, audio, session)
                session.update("ANALYZING", 24, "AI 음성 인식을 수행하고 있습니다.")
                transcript = provider.transcribe(audio, check=session.check)
            session.check()
            if transcript:
                session.analysis_mode = "음성 분석" + (" + OCR" if os.getenv("USE_OCR", "1") == "1" else "")
                session.update("ANALYZING", 42, "음성과 화면을 함께 분석합니다.")
                planner_segments = (
                    add_screen_text(session.source, transcript, session)
                    if os.getenv("USE_OCR", "1") == "1" else transcript
                )
                mode = "speech"
            else:
                session.update("ANALYZING", 38, "음성이 없어 화면 변화 기반 분석으로 전환합니다.")
                planner_segments, ocr = visual_windows(session.source, duration, session)
                if not planner_segments:
                    raise ValueError("분석 가능한 영상 장면이 없습니다.")
                session.analysis_mode = "장면 변화 + 화면 글자(OCR)" if ocr else "장면 변화 (OCR 없음)"
                mode = "visual"
            session.check()
            session.update("PLANNING", 52, "AI가 핵심 구간과 이야기 흐름을 선정합니다.")
            plan = make_plan(provider, planner_segments, settings.target_seconds, duration, settings.style, mode)
            session.check()
            session.update("RENDERING", 60, "FFmpeg가 선택한 장면을 편집합니다.")
            temporary_output = temp / "final.mp4"
            result = render(
                session.source, temporary_output, plan,
                transcript if mode == "speech" else [],
                settings.format, settings.enhance, metadata["has_audio"],
                session=session,
                progress=lambda value: session.update("RENDERING", value, "MP4를 생성하고 있습니다."),
            )
            session.check()
            session.update("RENDERING", 96, "완성 파일을 검증하고 있습니다.")
            final_file = session.folder / ("output-" + uuid.uuid4().hex + ".mp4")
            os.replace(temporary_output, final_file)
            with session.lock:
                if session.closed or session.cancellation.is_set():
                    final_file.unlink(missing_ok=True)
                    session.check()
                previous = session.output
                session.output = final_file
                session.title = plan["title"]
                session.output_duration = result["duration"]
                session.status = "COMPLETED"
                session.progress = 100
                session.message = "자동 편집이 완료되었습니다. 미리보기 후 다운로드하세요."
                session.error = None
            # A re-edit keeps its source, but no long-term versions or projects.
            if previous:
                try:
                    previous.unlink(missing_ok=True)
                except OSError:
                    pass
    finally:
        provider.close()
