"""Minimal OpenAI-compatible provider adapter with encrypted server-side credentials."""
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_api_key(ciphertext: str) -> str:
    key_hex = os.environ.get("AI_CONFIG_ENCRYPTION_KEY", "")
    if len(key_hex) != 64:
        raise ValueError("AI_CONFIG_ENCRYPTION_KEY must be a 32-byte hex value")
    iv, tag, encrypted = (base64.b64decode(x) for x in ciphertext.split("."))
    return AESGCM(bytes.fromhex(key_hex)).decrypt(iv, encrypted + tag, None).decode("utf-8")


def validate_base_url(value: str) -> str:
    url = urlsplit(value)
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("AI provider URL must not contain credentials, query or fragment")
    hostname = (url.hostname or "").lower().rstrip(".")
    allow = {h.strip().lower() for h in os.getenv("AI_ALLOWED_HOSTS", "api.openai.com").split(",") if h.strip()}
    if hostname not in allow:
        raise ValueError("AI provider host is not in AI_ALLOWED_HOSTS")
    local = hostname in {"localhost", "127.0.0.1"}
    if url.scheme != "https" and not (local and url.scheme == "http" and os.getenv("AI_ALLOW_LOCAL_HTTP") == "true"):
        raise ValueError("AI provider must use HTTPS")
    if not url.netloc:
        raise ValueError("Invalid provider URL")
    return value.rstrip("/")


class AIProvider:
    def __init__(self, base_url: str, chat_model: str, transcription_model: str, api_key: str):
        self.base_url = validate_base_url(base_url)
        self.chat_model = chat_model
        self.transcription_model = transcription_model
        self.headers = {"Authorization": "Bearer " + api_key}
        self.http = httpx.Client(timeout=httpx.Timeout(300, connect=20), follow_redirects=False)

    def transcribe(self, audio_file: Path) -> list[dict]:
        with audio_file.open("rb") as handle:
            response = self.http.post(
                self.base_url + "/audio/transcriptions",
                headers=self.headers,
                data={"model": self.transcription_model, "response_format": "verbose_json",
                      "timestamp_granularities[]": "segment"},
                files={"file": (audio_file.name, handle, "audio/mpeg")},
            )
        response.raise_for_status()
        result = response.json()
        segments = result.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ValueError("This transcription endpoint must return verbose_json segments with timestamps")
        output = []
        for segment in segments:
            try:
                start, end = float(segment["start"]), float(segment["end"])
                phrase = str(segment["text"]).strip()
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Invalid transcription segment") from exc
            if not 0 <= start < end or not phrase or end > 86_400:
                raise ValueError("Invalid transcription timestamps")
            output.append({"start": round(start, 3), "end": round(end, 3), "text": phrase[:1000]})
        if len(output) > 1800:
            raise ValueError("Too many ASR segments for first-version editor")
        return output

    def chat_json(self, system: str, user: str) -> dict:
        response = self.http.post(
            self.base_url + "/chat/completions",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"model": self.chat_model, "temperature": 0.2,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]},
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
        if not isinstance(content, str):
            raise ValueError("AI returned non-text result")
        content = content.strip()
        if content.startswith("```"):
            content = content.partition("\n")[2].rsplit("```", 1)[0].strip()
        try:
            obj = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("AI returned invalid JSON") from exc
        if not isinstance(obj, dict):
            raise ValueError("AI must return JSON object")
        return obj
