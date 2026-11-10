"""Ensure dedicated one-shot ports and server identity are correct."""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_local_ports import port_is_busy, PORT_NAMES
from verify_running_editor import compatible_health, correct_frontend


class PortTests(unittest.TestCase):
    def test_legacy_3000_is_not_a_required_port(self):
        self.assertEqual(set(PORT_NAMES), {3100, 8100})
        self.assertNotIn(3000, PORT_NAMES)

    def test_correct_server_identity_is_required(self):
        health = {"app": "one-shot-local", "storage": "temporary-local",
                  "ok": True, "ffmpeg": True, "ffprobe": True}
        self.assertTrue(compatible_health(health))
        self.assertFalse(compatible_health({**health, "app": "legacy-s3"}))
        self.assertFalse(compatible_health({**health, "ffmpeg": False}))
        self.assertTrue(correct_frontend("<h1>AI 영상 자동 편집기</h1><p>ONE-SHOT STUDIO</p>"))
        self.assertFalse(correct_frontend("<title>Video Studio S3</title>"))

    def test_listener_is_detected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            self.assertTrue(port_is_busy(server.getsockname()[1]))

    def test_port_is_available_after_close(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            port = server.getsockname()[1]
        self.assertFalse(port_is_busy(port))


if __name__ == "__main__":
    unittest.main()
