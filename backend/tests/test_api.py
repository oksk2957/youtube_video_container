import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app, manager

ORIGIN = {"Origin": "http://localhost:3000"}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.video = Path(cls.folder.name) / "source.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=20",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.video),
        ], check=True, timeout=45)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_health_identifies_one_shot_backend(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["app"], "one-shot-local")
        self.assertEqual(response.json()["storage"], "temporary-local")
        self.assertNotIn("s3", response.text.lower())

    def test_health_is_get_only(self):
        response = self.client.post("/api/health", headers=ORIGIN)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers["allow"], "GET")

    def test_health_exposes_local_http_policy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(self.client.get("/api/health").json()["local_ai_http"])
            self.assertNotIn("ALLOW_LOCAL_AI_HTTP", os.environ)
        with patch.dict(os.environ, {"ALLOW_LOCAL_AI_HTTP": "0"}):
            self.assertFalse(self.client.get("/api/health").json()["local_ai_http"])
        with patch.dict(os.environ, {"ALLOW_LOCAL_AI_HTTP": "1"}):
            self.assertTrue(self.client.get("/api/health").json()["local_ai_http"])

    def upload(self):
        return self.client.post("/api/sessions", headers=ORIGIN,
            files={"file": ("video.mp4", io.BytesIO(self.video.read_bytes()), "video/mp4")})

    def test_upload_status_download_reset(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        sid = response.json()["session_id"]
        status = self.client.get("/api/sessions/" + sid + "/status")
        self.assertEqual(status.json()["status"], "READY")
        self.assertEqual(self.client.get("/api/sessions/" + sid + "/output").status_code, 404)
        self.assertEqual(self.client.delete("/api/sessions/" + sid, headers=ORIGIN).status_code, 200)
        self.assertEqual(self.client.get("/api/sessions/" + sid + "/status").status_code, 404)
        self.assertIsNone(manager.by_token(response.cookies.get("one_shot_session")))

    def test_alternate_loopback_origin_allowed(self):
        response = self.client.post("/api/sessions",
            headers={"Origin": "http://127.0.0.1:3000"},
            files={"file": ("video.mp4", io.BytesIO(self.video.read_bytes()), "video/mp4")})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.client.delete("/api/sessions/" + response.json()["session_id"],
            headers={"Origin": "http://127.0.0.1:3000"}).status_code, 200)

    def test_cross_origin_upload_blocked(self):
        response = self.client.post("/api/sessions", headers={"Origin": "https://evil.example"},
            files={"file": ("video.mp4", io.BytesIO(self.video.read_bytes()), "video/mp4")})
        self.assertEqual(response.status_code, 403)

    def test_invalid_file_rejected(self):
        response = self.client.post("/api/sessions", headers=ORIGIN,
            files={"file": ("bad.mp4", io.BytesIO(b"not a video"), "video/mp4")})
        self.assertEqual(response.status_code, 400)

    def test_unknown_session_not_accessible(self):
        self.assertEqual(self.client.get("/api/sessions/not-a-real-session/status").status_code, 404)

    def test_cancel_running_job(self):
        up = self.upload()
        self.assertEqual(up.status_code, 201)
        sid = up.json()["session_id"]
        def wait_until_cancelled(session, settings):
            for _ in range(500):
                session.check()
                time.sleep(0.005)
        with patch("main.process_session", wait_until_cancelled):
            response = self.client.post("/api/sessions/" + sid + "/start", headers=ORIGIN, json={
                "base_url": "https://api.example.com/v1", "chat_model": "test-model",
                "asr_model": "local:tiny", "api_key": "dummy",
                "format": "shorts", "style": "calm", "target_seconds": 30,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.post("/api/sessions/" + sid + "/cancel",
                                              headers=ORIGIN).status_code, 200)
            for _ in range(100):
                state = self.client.get("/api/sessions/" + sid + "/status").json()
                if state["status"] == "CANCELLED":
                    break
                time.sleep(0.02)
            self.assertEqual(state["status"], "CANCELLED")
            self.assertEqual(self.client.delete("/api/sessions/" + sid, headers=ORIGIN).status_code, 200)

    def test_mock_auto_edit_completion(self):
        up = self.upload()
        self.assertEqual(up.status_code, 201)
        sid = up.json()["session_id"]
        def fake_pipeline(session, settings):
            session.update("RENDERING", 75, "가짜 렌더링 테스트")
            target = session.folder / "output.mp4"
            shutil.copyfile(session.source, target)
            with session.lock:
                session.output = target
                session.output_duration = session.metadata["duration"]
                session.status = "COMPLETED"
                session.progress = 100
                session.message = "테스트 완료"
        with patch("main.process_session", fake_pipeline):
            response = self.client.post("/api/sessions/" + sid + "/start", headers=ORIGIN, json={
                "base_url": "https://api.example.com/v1", "chat_model": "fake-chat",
                "asr_model": "local:tiny", "api_key": "test-key",
                "format": "shorts", "style": "auto", "target_seconds": 30,
            })
            self.assertEqual(response.status_code, 200)
            for _ in range(60):
                status = self.client.get("/api/sessions/" + sid + "/status").json()
                if status["status"] == "COMPLETED":
                    break
                time.sleep(0.05)
            self.assertEqual(status["status"], "COMPLETED")
            self.assertEqual(self.client.get("/api/sessions/" + sid + "/download").status_code, 200)
        self.assertEqual(self.client.delete("/api/sessions/" + sid, headers=ORIGIN).status_code, 200)


if __name__ == "__main__":
    unittest.main()
