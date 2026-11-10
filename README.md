# One-Shot AI Video Editor

로컬 PC에서 **영상 업로드 → AI 자동 편집 → 미리보기 → MP4 다운로드 → 작업 종료**를 수행하는 Next.js + Python FastAPI 프로그램입니다. 로그인, DB, S3, Docker가 필요하지 않습니다.

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
