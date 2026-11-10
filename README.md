# One-Shot AI Video Editor

로컬 PC에서 **영상 업로드 → AI 자동 편집 → 미리보기 → MP4 다운로드 → 작업 종료**를 수행하는 Next.js + Python FastAPI 프로그램입니다. 로그인, DB, S3, Docker가 필요하지 않습니다..

## 접속 주소

- **웹 편집기:** http://localhost:3000/
- **Python API:** http://127.0.0.1:8100/api/health
- 기존의 `3100` 포트와 달리, **이 버전은 3000번 포트**를 사용합니다.
- 브라우저에서 `ONE-SHOT STUDIO` 및 `AI 영상 자동 편집기`가 보이면 정상적인 웹 화면입니다.
- `npm run dev`만 실행하면 웹 화면은 보일 수 있지만 Python API가 실행되지 않아 영상 업로드·편집은 동작하지 않습니다. **전체 기능 실행에는 `run.bat`이 필요합니다.**

## Windows 설치/실행

**준비:** Node.js 22 이상, Python 3.11 이상, FFmpeg 및 FFprobe가 설치되어 PATH에 등록되어 있어야 합니다.

처음 다운로드하는 경우 PowerShell에서:

```powershell
git clone https://github.com/oksk2957/youtube_video_container.git
cd youtube_video_container
.\run.bat
```

이미 코드를 다운로드한 경우 프로젝트 폴더에서:

```powershell
git fetch origin
git switch main
git pull --ff-only
.\run.bat
```

이전에 `feat/one-shot-local-ai-video-editor` 브랜치를 다운로드했던 경우에도 위 `git switch main` 명령을 사용하면 됩니다. 기존 파일을 직접 수정했다면 먼저 변경사항을 백업하세요.

`run.bat`은 Python 런처(`py -3`)를 우선 사용하여 WindowsApps의 가짜 `python` 실행 별칭으로 인한 오류를 피하고, 3000/8100 포트 검사 → 가상환경/패키지 설치 → 두 서버 실행 → 연결 상태 검사 → 브라우저 열기를 수행합니다. 종료할 때는 `stop.bat`을 실행합니다.

### 시작되지 않을 때

```powershell
py -3 --version
node --version
ffmpeg -version
ffprobe -version
Get-NetTCPConnection -State Listen -LocalPort 3000,8100 -ErrorAction SilentlyContinue
```

- `py -3 --version`이 실패하면 Python을 올바르게 설치하고, Windows **앱 실행 별칭**의 `python.exe` / `python3.exe` 설정을 확인하세요.
- 3000번 포트에 구형 Next.js 서버가 실행 중이라면 해당 서버의 터미널에서 `Ctrl+C`로 종료한 후 `run.bat`을 다시 실행하세요. 다른 앱이 쓰는 포트의 프로세스를 무작정 종료하지 마세요.
- Python 백엔드 창 또는 Next.js 프런트엔드 창이 종료되었다면 해당 창의 오류 로그를 확인하세요.
- 성공 시 `http://localhost:3000/`으로 접속하고, 이전 기본 템플릿 화면이 캐시되어 있다면 `Ctrl+F5`를 누르세요.

## 편집 오류 진단 (Bruno / API / AI)

- **편집 UI는 `http://localhost:3000/`**입니다. `8100`번은 Python 백엔드 API이므로 그 주소에서 영상 편집 화면이 열리지 않습니다.
- `GET http://127.0.0.1:8100/api/health`에 대한 정상 응답은 `{"app":"one-shot-local","storage":"temporary-local","ok":true,"ffmpeg":true,"ffprobe":true,"local_ai_http":true}` 형태입니다.
- `POST /api/health`는 편집 시작 요청이 **아닙니다**. 지원하는 메서드는 GET뿐입니다. Origin이 없는 POST는 보안 검사에서 403으로 거부될 수 있습니다.
- Bruno의 `0B`, `No Body`, `Request / Response / Network`는 요청 본문과 도구 화면 요소일 수 있습니다. **HTTP 상태 코드 및 Response 본문**을 함께 확인해야 실제 오류를 알 수 있습니다.
- 영상 편집을 시작하는 API는 `POST /api/sessions/{session_id}/start`이고, 진행 상태·AI 오류는 `GET /api/sessions/{session_id}/status`에서 확인합니다. 직접 Bruno로 호출하면 업로드 시 발급된 **세션 쿠키**와 올바른 `Origin` 헤더가 필요하므로 웹 UI를 사용하는 편이 간단합니다.

PowerShell에서 백엔드가 정말 실행 중인지 점검:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8100/api/health"
```

- 연결 실패: `run.bat`으로 Python 백엔드가 시작되었는지 확인합니다. 3000/8100 포트가 다른 서버에 이미 사용되고 있다면 해당 서버를 정상 종료한 뒤 재시작합니다.
- `ffmpeg: false` 또는 `ffprobe: false`: FFmpeg/FFprobe 설치와 PATH를 확인합니다.
- HTTP 401/403: AI 제공업체 API 키와 권한을 확인합니다. **키를 로그나 이슈에 게시하지 마세요.**
- HTTP 404: AI Base URL(`/v1` 포함 여부) 및 모델·서비스의 API 호환성을 확인합니다.
- HTTP 429: AI 제공업체 사용 한도, 잔액, 요청 제한을 확인합니다.
- 로컬 `local:small` 음성 인식은 모델을 첫 실행 시 다운로드할 수 있으므로 인터넷 연결과 저장 공간이 필요합니다. 음성 인식 없는 영상은 장면 분석으로 전환합니다.
- 웹 편집기 우측 진행 화면에 뜬 상세 오류와 Python 서버 창의 로그를 함께 확인하세요. API 키 또는 원본 영상의 개인정보는 공유하지 마세요.

### 로컬 AI `http://localhost:7070/v1` 연결 시 2%에서 실패할 때

- 편집 화면에서 `ALLOW_LOCAL_AI_HTTP=1` 오류가 나면 실행 중인 **구형 Python 백엔드**이거나 Windows 환경변수 `ALLOW_LOCAL_AI_HTTP=0`이 명시적으로 설정되어 있을 수 있습니다.
- 최신 버전은 **이 PC의 `localhost`/`127.0.0.1` HTTP AI 서버만 기본 허용**합니다. 외부 AI 서버는 HTTPS만 허용하고, 내부망·사설 IP로의 연결도 차단합니다. 로컬 HTTP를 금지하려면 `ALLOW_LOCAL_AI_HTTP=0`으로 명시적으로 끌 수 있습니다.
- 편집 UI는 실행 중인 API의 `/api/health` 응답에서 `local_ai_http` 값을 확인합니다. `false`이거나 필드가 없다면 오래된 백엔드/환경 설정을 확인해야 합니다.
- 코드를 받는 것만으로 실행 중인 서버가 갱신되지 않습니다. **먼저 `stop.bat` 실행**, 그다음 아래 명령으로 최신 `main`을 받고 **`run.bat`으로 재실행**하세요.

```powershell
cd "C:\project_v1\project-2026-11-06\youtube_video_project_v1"
.\stop.bat
git fetch origin
git switch main
git pull --ff-only origin main
.\run.bat
Invoke-RestMethod "http://127.0.0.1:8100/api/health"
Test-NetConnection -ComputerName 127.0.0.1 -Port 7070
```

- 상태 확인 응답에서 `local_ai_http: true`여야 하며, `TcpTestSucceeded: True`는 **7070 포트에 프로그램이 실행 중임을 의미할 뿐 AI API 호환성을 보증하지는 않습니다**.
- 별도 실행 중인 AI 서버가 `POST /v1/chat/completions`을 지원하고 `fusion` 모델을 인식하는지도 확인하세요. `local:small`은 영상 편집기 PC의 faster-whisper 음성 인식 모델입니다.
- 브라우저 개발자 도구에서 복사한 요청의 `credentials: "omit"`은 업로드 시 발급된 세션 쿠키를 전송하지 않습니다. 실제 편집 UI는 `credentials: "include"`를 사용하므로 **웹 화면에서 다시 실행**하세요. 직접 API 요청을 재생하거나 키를 공개 로그에 공유하지 마세요.
- AI API 키가 화면 캡처나 복사한 요청에 노출됐다면 제공처에서 즉시 **폐기 후 재발급**하세요.

## 기능

1. MP4, MOV 또는 WebM 영상 업로드 (최대 1GiB, 최대 30분, 최대 4096px).
2. AI 서비스의 HTTPS Base URL, 채팅 모델, API 키를 입력합니다.
3. 음성 인식은 `local:small`(로컬 faster-whisper) 또는 외부 서비스가 지원하는 전사 모델을 선택합니다.
4. 쇼츠 9:16 / 가로 16:9, 길이 30/45/60/120초, 편집 스타일을 선택합니다.
5. 실제 FFmpeg를 사용해 편집한 뒤 미리보기 및 MP4 다운로드를 제공합니다.
6. **작업 종료하고 처음부터 시작**을 누르면 임시 작업을 정리합니다.

`local:small`을 사용하면 첫 실행에서 모델을 다운로드할 수 있습니다. AI 편집 결과의 사실관계·내용 선정·자막 품질은 게시 전에 반드시 원본과 비교하세요.

## 개발자 실행

`npm run dev`는 Next.js 프런트엔드만 실행합니다. 전체 테스트는 아래와 같습니다.

```sh
npm install
npm run lint
npm run build
npx tsc --noEmit
python -m pip install -r backend/requirements.txt
python -m unittest discover -s backend/tests -v
```

수동으로 API를 실행하려면 `python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8100 --no-access-log`을 사용합니다. 웹 서버는 `npm run dev -- -H 127.0.0.1 -p 3000`으로 실행합니다.

웹 출처 허용 목록은 `http://localhost:3000`과 `http://127.0.0.1:3000` 두 로컬 주소로 제한됩니다. API는 `127.0.0.1:8100`에만 바인딩됩니다. 브라우저는 현재 접속한 루프백 호스트(localhost 또는 127.0.0.1)와 같은 호스트의 API에 요청하므로 세션 쿠키가 유지됩니다.

## 보안 및 제한

- 세션 쿠키로 각 작업의 원본/결과 접근을 제한하고, 변경 요청에서 허용된 Origin을 확인합니다.
- 영상 파일과 AI API 키를 데이터베이스에 저장하지 않습니다. 작업 파일은 OS 임시 폴더에 생성되며 세션 종료·서버 종료·만료 정리 대상이 됩니다. 보안 삭제(wipe)는 아닙니다.
- 외부 AI에 음성 전사나 OCR 등 영상 관련 정보가 전송될 수 있으므로 제공업체의 데이터 정책을 확인하세요.
- 로컬 전용 편집기로 다중 사용자 운영이나 인터넷 공개 배포 용도로 설계되지 않았습니다.
- Windows 배치 파일의 개인 PC 환경 실행과 실제 외부 유료 AI 호출은 GitHub CI와 별도로 점검이 필요합니다.

코드 위치: `src/app/page.tsx`(프런트엔드), `backend/`(FastAPI·AI·FFmpeg), `scripts/`(실행 점검), `run.bat`, `stop.bat`.
