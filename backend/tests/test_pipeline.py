"""Offline integration test: actual local session, mocked paid AI, real FFmpeg MP4."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import probe
from pipeline import process_session
from session_manager import BASE_DIR, manager


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class FullPipelineTest(unittest.TestCase):
    def test_mock_ai_selects_segments_and_generates_real_mp4(self):
        class FakeAI:
            def __init__(self, *args):
                self.closed = False

            def transcribe(self, audio, check=None):
                self.audio = audio
                return [
                    {"start": 0.0, "end": 2.0, "text": "처음 이야기입니다"},
                    {"start": 2.0, "end": 4.0, "text": "마지막 결론입니다"},
                ]

            def chat_json(self, system, prompt):
                return {"title": "핵심 요약", "cuts": [
                    {"first": 0, "last": 1, "reason": "완결된 내용"},
                ]}

            def close(self):
                self.closed = True

        folder = Path(tempfile.mkdtemp(prefix="session-", dir=BASE_DIR))
        session = None
        try:
            source = folder / "source.mp4"
            subprocess.run([
                "ffmpeg", "-nostdin", "-y", "-v", "error",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=20",
                "-f", "lavfi", "-i", "sine=frequency=500:sample_rate=48000",
                "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(source),
            ], check=True, timeout=90)
            session = manager.create(folder, source, "source.mp4", probe(source))
            settings = SimpleNamespace(
                base_url="https://api.example.com/v1", chat_model="example",
                asr_model="mock-asr", api_key="fake-token",
                format="shorts", style="news", target_seconds=30, enhance=True,
            )
            with patch.dict(os.environ, {"USE_OCR": "0"}):
                with patch("pipeline.AIProvider", FakeAI):
                    process_session(session, settings)
            self.assertEqual(session.status, "COMPLETED")
            self.assertTrue(session.output.exists())
            result = probe(session.output)
            self.assertEqual((result["width"], result["height"]), (720, 1280))
            self.assertLess(abs(result["duration"] - 4.0), 1.5)
            self.assertEqual(session.title, "핵심 요약")
        finally:
            if session:
                manager.close(session)
            else:
                shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
