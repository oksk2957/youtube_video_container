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

    @patch("socket.getaddrinfo")
    def test_provider_http_errors_are_actionable(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        for status_code, expected in [
            (401, "API 키"), (403, "접근 권한"), (404, "Base URL"),
            (429, "한도"), (500, "서버 오류"),
        ]:
            with self.subTest(status_code=status_code):
                provider = AIProvider("https://api.example.com/v1", "chat", "asr", "test-token")
                provider.http.close()
                provider.http = httpx.Client(transport=httpx.MockTransport(
                    lambda request, code=status_code: httpx.Response(code, json={"message": "secret"})
                ))
                with self.assertRaisesRegex(ValueError, expected):
                    provider.chat_json("system", "user")
                provider.close()

    @patch("socket.getaddrinfo")
    def test_provider_network_failure_is_actionable(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        provider = AIProvider("https://api.example.com/v1", "chat", "asr", "test-token")
        provider.http.close()
        def fail(request):
            raise httpx.ConnectError("connection refused", request=request)
        provider.http = httpx.Client(transport=httpx.MockTransport(fail))
        with self.assertRaisesRegex(ValueError, "연결하지 못했습니다"):
            provider.chat_json("system", "user")
        provider.close()

    def test_local_https_allows_missing_key_with_opt_in(self):
        with patch.dict(os.environ, {"ALLOW_LOCAL_AI_HTTP": "1"}):
            provider = AIProvider("https://localhost:11434/v1", "chat", "local:tiny", "")
            provider.close()

    @patch("socket.getaddrinfo")
    def test_invalid_transcription_json_is_friendly(self, resolver):
        resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        provider = AIProvider("https://api.example.com/v1", "chat", "asr", "fake-token")
        provider.http.close()
        provider.http = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=["unexpected"])
        ))
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            audio = Path(root) / "sample.mp3"
            audio.write_bytes(b"test")
            with self.assertRaisesRegex(ValueError, "JSON 객체"):
                provider.transcribe(audio)
        provider.close()


if __name__ == "__main__":
    unittest.main()
