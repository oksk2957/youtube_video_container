"""OpenAI-compatible chat / transcription client. Credentials live only in job memory."""
from __future__ import annotations

import ipaddress
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def validate_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    try:
        url = urlsplit(value)
        hostname = (url.hostname or "").lower().rstrip(".")
        port = url.port
    except (ValueError, AttributeError) as exc:
        raise ValueError("AI Base URL 형식이 올바르지 않습니다.") from exc
    if not hostname or url.username or url.password or url.fragment or url.query:
        raise ValueError("AI Base URL에 사용자 정보·쿼리·해시를 넣을 수 없습니다.")
    local = hostname in {"localhost", "127.0.0.1"}
    if local:
        if os.getenv("ALLOW_LOCAL_AI_HTTP") != "1":
            raise ValueError("로컬 AI 연결에는 ALLOW_LOCAL_AI_HTTP=1 설정이 필요합니다.")
        if url.scheme not in {"https", "http"}:
            raise ValueError("로컬 AI URL에는 HTTP 또는 HTTPS를 사용하세요.")
    elif url.scheme != "https":
        raise ValueError("외부 AI 서버에는 HTTPS가 필요합니다.")
    if not local:
        try:
            resolved = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
            if not resolved:
                raise ValueError("AI 호스트를 찾지 못했습니다.")
            for answer in resolved:
                address = ipaddress.ip_address(answer[4][0])
                if not address.is_global:
                    raise ValueError("사설망·내부망 주소는 AI Base URL로 사용할 수 없습니다.")
        except OSError as exc:
            raise ValueError("AI 서버 주소를 확인할 수 없습니다.") from exc
    return value


class AIProvider:
    def __init__(self, base_url: str, chat_model: str, asr_model: str, api_key: str):
        self.base_url = validate_base_url(base_url)
        self.chat_model = chat_model.strip()
        self.asr_model = asr_model.strip()
        if not self.chat_model or not self.asr_model:
            raise ValueError("AI 모델 이름을 입력하세요.")
        if not api_key and not self.base_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("외부 AI 서비스의 API 키가 필요합니다.")
        self.headers = {"Authorization": "Bearer " + api_key} if api_key else {}
        self.http = httpx.Client(timeout=httpx.Timeout(180, connect=15), follow_redirects=False, trust_env=False)

    def close(self):
        self.http.close()

    def transcribe(self, audio: Path, check=None) -> list[dict]:
        if check:
            check()
        if self.asr_model.startswith("local:"):
            size = self.asr_model.partition(":")[2]
            if size not in {"tiny", "base", "small"}:
                raise ValueError("로컬 음성 인식은 local:tiny / local:base / local:small만 지원합니다.")
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ValueError("로컬 Whisper 패키지가 설치되지 않았습니다. requirements-whisper.txt를 설치하세요.") from exc
            model = WhisperModel(size, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(audio), vad_filter=True, beam_size=3)
            output = []
            for segment in segments:
                if check:
                    check()
                if segment.text.strip() and 0 <= segment.start < segment.end:
                    output.append({
                        "start": round(segment.start, 3),
                        "end": round(segment.end, 3),
                        "text": segment.text.strip()[:700],
                    })
            return output[:450]
        with audio.open("rb") as handle:
            response = self.http.post(
                self.base_url + "/audio/transcriptions",
                headers=self.headers,
                data={
                    "model": self.asr_model,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                },
                files={"file": (audio.name, handle, "audio/mpeg")},
            )
        if response.status_code >= 400:
            raise ValueError("AI 음성 인식 API가 요청을 처리하지 못했습니다. 모델과 API 호환성을 확인하세요.")
        data = response.json()
        raw_segments = data.get("segments")
        if not isinstance(raw_segments, list):
            raise ValueError("ASR API가 시작·종료 시간 정보가 있는 segments를 제공하지 않습니다. local:small을 사용해 보세요.")
        output = []
        for item in raw_segments:
            try:
                start, end, text = float(item["start"]), float(item["end"]), str(item["text"]).strip()
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError("음성 인식 시간 정보가 올바르지 않습니다.") from exc
            if not 0 <= start < end <= 3600:
                raise ValueError("음성 인식 시간 정보가 영상 범위를 벗어났습니다.")
            if text:
                output.append({"start": round(start, 3), "end": round(end, 3), "text": text[:700]})
        return output[:450]

    def chat_json(self, system: str, user: str) -> dict:
        response = self.http.post(
            self.base_url + "/chat/completions",
            headers={**self.headers, "Content-Type": "application/json"},
            json={
                "model": self.chat_model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        if response.status_code >= 400:
            raise ValueError("AI 대화 API가 요청을 처리하지 못했습니다. Base URL, 모델명, API 키를 확인하세요.")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ValueError("AI 대화 API의 응답 형식이 올바르지 않습니다.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not isinstance(content, str):
            raise ValueError("AI가 JSON 텍스트를 반환하지 않았습니다.")
        content = content.strip()
        fence = chr(96) * 3
        if content.startswith(fence):
            content = content.partition("\n")[2].rsplit(fence, 1)[0].strip()
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("AI가 유효한 편집 계획 JSON을 반환하지 않았습니다.") from exc
        if not isinstance(value, dict):
            raise ValueError("AI 편집 계획은 JSON 객체여야 합니다.")
        return value
