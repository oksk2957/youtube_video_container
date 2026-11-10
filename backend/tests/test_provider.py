import os
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provider import validate_base_url, AIProvider
import httpx


class ProviderTests(unittest.TestCase):
    @patch("socket.getaddrinfo")
    def test_public_https_api_allowed(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        self.assertEqual(validate_base_url("https://api.example.com/v1"),
                         "https://api.example.com/v1")

    @patch("socket.getaddrinfo")
    def test_private_address_and_http_blocked(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 443))]
        with self.assertRaises(ValueError):
            validate_base_url("https://private.example.com/v1")
        with self.assertRaises(ValueError):
            validate_base_url("http://api.example.com/v1")

    def test_local_http_requires_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                validate_base_url("http://127.0.0.1:11434/v1")
        with patch.dict(os.environ, {"ALLOW_LOCAL_AI_HTTP": "1"}):
            self.assertEqual(validate_base_url("http://127.0.0.1:11434/v1"),
                             "http://127.0.0.1:11434/v1")

    @patch("socket.getaddrinfo")
    def test_mock_ai_chat_json(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        provider = AIProvider("https://api.example.com/v1", "chat", "asr", "fake-token")
        provider.http.close()
        provider.http = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={
                "choices": [{"message": {"content": '{"title":"test","cuts":[{"first":0,"last":1}]}'}}],
            })
        ))
        self.assertEqual(provider.chat_json("system", "user")["title"], "test")
        provider.close()

    @patch("socket.getaddrinfo")
    def test_mock_timed_transcription(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        provider = AIProvider("https://api.example.com/v1", "chat", "asr", "fake-token")
        provider.http.close()
        provider.http = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={
                "segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요"}],
            })
        ))
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            audio = Path(root) / "sample.mp3"
            audio.write_bytes(b"fake-mp3-test-only")
            self.assertEqual(provider.transcribe(audio)[0]["text"], "안녕하세요")
        provider.close()


if __name__ == "__main__":
    unittest.main()
