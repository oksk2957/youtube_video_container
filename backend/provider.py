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
        if not api_key and urlsplit(self.base_url).hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("외부 AI 서비스의 API 키가 필요합니다.")
        self.headers = {"Authorization": "Bearer " + api_key} if api_key else {}
        self.http = httpx.Client(timeout=httpx.Timeout(180, connect=15), follow_redirects=False, trust_env=False)

    def close(self):
        self.http.close()

    def _post(self, endpoint: str, **kwargs) -> httpx.Response:
        """Give actionable provider errors without echoing credentials or remote bodies."""
        try:
            response = self.http.post(self.base_url + endpoint, **kwargs)
        except httpx.TimeoutException as exc:
            raise ValueError("AI 서버 응답 시간이 초과되었습니다. 인터넷 연결과 제공업체 상태를 확인하세요.") from exc
        except httpx.RequestError as exc:
            raise ValueError("AI 서버에 연결하지 못했습니다. Base URL과 네트워크 연결을 확인하세요.") from exc
        code = response.status_code
        if code in (401, 403):
            raise ValueError(f"AI API 인증 또는 접근 권한 오류 (HTTP {code}). API 키와 권한을 확인하세요.")
        if code == 404:
            raise ValueError("AI API 주소 또는 모델 경로를 찾지 못했습니다 (HTTP 404). Base URL에 /v1이 필요한지 확인하세요.")
        if code == 429:
            raise ValueError("AI API 호출 한도 초과 (HTTP 429). 잔액·요금제·요청 제한을 확인하세요.")
        if code >= 500:
            raise ValueError(f"AI 제공업체 서버 오류 (HTTP {code}). 잠시 후 다시 시도하세요.")
        if code >= 400:
            raise ValueError(f"AI API 요청 오류 (HTTP {code}). 모델 이름과 서비스의 API 호환성을 확인하세요.")
        return response

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
            try:
                model = WhisperModel(size, device="cpu", compute_type="int8")
            except (RuntimeError, OSError, ValueError) as exc:
                raise ValueError("로컬 Whisper 모델을 불러오지 못했습니다. 첫 실행 시 인터넷 연결, 디스크 용량, 모델 설치 상태를 확인하세요.") from exc
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
            if len(output) > 450:
                raise ValueError("음성 인식 구간이 450개를 넘는 영상은 현재 지원하지 않습니다.")
            return output
        with audio.open("rb") as handle:
            response = self._post(
                "/audio/transcriptions",
                headers=self.headers,
                data={
                    "model": self.asr_model,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                },
                files={"file": (audio.name, handle, "audio/mpeg")},
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError("AI 음성 인식 API가 JSON이 아닌 응답을 반환했습니다.") from exc
        if not isinstance(data, dict):
            raise ValueError("AI 음성 인식 API의 응답이 JSON 객체가 아닙니다.")
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
        if len(output) > 450:
            raise ValueError("음성 인식 구간이 450개를 넘는 영상은 현재 지원하지 않습니다.")
        return output

    def chat_json(self, system: str, user: str) -> dict:
        response = self._post(
            "/chat/completions",
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
