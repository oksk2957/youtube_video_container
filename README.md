# One-Shot AI Video Editor

## 중요: 같은 S3 업로드 오류가 반복되는 이유

`Unable to start object storage upload`는 **구버전 PR #1**의
`src/app/api/uploads/init/route.ts`에서만 발생합니다. 사용자 제공 요청 기록은 실제로
`http://localhost:3000/projects/.../edit` 및 `POST /api/uploads/init`로 접속 중임을 보여줍니다.

이번 수정부터 새 일회성 버전은 기존 서버와 포트까지 완전히 분리했습니다.

| 구분 | 구버전(S3 사용) | 새 일회성 버전(S3 없음) |
|---|---|---|
| 웹 페이지 | http://localhost:3000 | **http://127.0.0.1:3100** |
| Python API | 없음 또는 별도 | **http://127.0.0.1:8100** |
| 업로드 API | /api/uploads/init | **/api/sessions** |
| 프로젝트·로그인 | 있음 | 없음 |

기존 3000번 서버를 꼭 종료할 필요는 없습니다. 다만 3000번 페이지를 계속 사용하면 예전 오류가 그대로 발생합니다. **반드시 3100번 주소를 열어야 합니다.**

### 깨끗한 새 폴더에 설치 (추천)

PowerShell에서 다음 명령을 사용합니다.

```powershell
git clone -b feat/one-shot-local-ai-video-editor https://github.com/oksk2957/youtube_video_container.git youtube-video-one-shot-fixed
cd youtube-video-one-shot-fixed
.\run.bat
```

처음 실행 시 Node.js 22+, Python 3.11+, FFmpeg/FFprobe가 PATH에 있어야 하고
Python과 Node 패키지가 설치됩니다. `run.bat`이 새로운 포트 3100·8100에 다른 프로그램이 없는지 확인합니다.
그 다음 **실제 실행 중인 FastAPI 서버가 로컬 편집기인지, Next.js 화면이 새 편집기인지**를 검증하고 브라우저를 엽니다.

### 이미 받은 Git 저장소를 업데이트하는 경우

미커밋 변경사항이 있다면 별도로 안전하게 백업한 후:

```powershell
git fetch origin
git switch feat/one-shot-local-ai-video-editor
git pull --ff-only
.\run.bat
```

로컬 브랜치가 아직 없다면 `git switch -c feat/one-shot-local-ai-video-editor --track origin/feat/one-shot-local-ai-video-editor`을 사용하세요.

브라우저 주소는 `http://127.0.0.1:3100`입니다. Ctrl+F5로 새로고침하면
`ONE-SHOT STUDIO` 및 **로컬 편집 엔진 연결됨 · S3/MinIO 사용 안 함** 표시를 확인할 수 있습니다.

편집 프로그램이 실행 중인 포트를 확인하려면:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 3000,3100,8000,8100 |
  Select-Object LocalPort,OwningProcess
```

**첨부한 네트워크 기록에 세션 쿠키가 포함된 경우:** 기존 편집기에서 로그아웃해
그 세션을 종료하고, 진단 로그를 공유할 때는 Cookie/Authorization 헤더를 가려 주세요.

로그인·프로젝트 생성·DB·S3·MinIO·Docker 없이 내 PC에서 사용하는 일회성 AI 자동 영상 편집기입니다.

**사용 흐름:** 영상 업로드 → AI Base URL / 모델 / 키 설정 → 영상 분석 및 자동 편집 → 미리보기 → MP4 다운로드 → 작업 종료 / 임시 파일 삭제.

## 빠른 시작 (Windows)

1. Node.js 22 이상, Python 3.11 이상, FFmpeg/FFprobe를 설치하고 PATH에 등록합니다.
2. 프로젝트 루트에서 **run.bat**을 실행합니다. 처음 실행할 때 Python 가상환경·패키지와 Next.js 의존성을 설치합니다. Docker는 필요하지 않습니다.
3. 브라우저에서 **http://127.0.0.1:3100** 주소를 사용하세요. 보안 쿠키는 같은 로컬 호스트를 사용하므로 localhost 대신 127.0.0.1로 접속합니다.
4. MP4, MOV 또는 WebM 파일을 선택해 업로드합니다. 실제 FFprobe 파일 검사 통과 후 임시 작업이 생성됩니다.
5. 호환 AI 서비스의 HTTPS **Base URL**(예: https://api.openai.com/v1), Chat 모델, API 키를 입력합니다. 음성 인식은 **local:small**(로컬 CPU Whisper) 또는 해당 제공업체가 지원하는 전사 모델(예: whisper-1)을 선택합니다.
6. 쇼츠 9:16 / 가로 16:9, 30·45·60·120초, AI 스타일을 설정하고 **AI 자동 편집 시작**을 누릅니다.
7. 완성되면 미리보기를 확인하고 **MP4 다운로드**를 누릅니다. 다시 편집을 선택해 원본 파일을 계속 사용할 수도 있습니다.
8. **작업 종료하고 처음부터 시작**을 누릅니다. 프로그램을 완전히 종료할 때는 **stop.bat**을 실행하세요.

로컬 Whisper 첫 실행 시 모델 파일을 다운로드하므로 인터넷과 추가 디스크 공간이 필요합니다. 이후 모델 캐시는 일반 패키지 관리 및 Hugging Face 캐시 정책에 따르며, **영상 작업 파일을 저장하는 세션 폴더와는 별도**입니다.

## 기술 구성

- **Next.js 16 / React 19**: 드래그 앤 드롭 파일 선택, Base URL·스타일 설정, 진행률, 미리보기, 다운로드.
- **Python FastAPI**: 스트리밍 업로드, FFprobe 검증, 임시 디렉터리와 쿠키 기반 일회성 세션, 비동기 작업 상태 관리, 취소·정리.
- **Python AIProvider**: OpenAI 호환 chat completions, verbose-json ASR 또는 선택형 로컬 faster-whisper.
- **Python Planner**: 원본 타임코드 기반 주요 구간 선정. 잘못된 구간/중복/범위 초과를 거부하고 AI에 재요청.
- **장면 기반 보조 분석**: 1초 간격 화면 밝기 변화·움직임 특징, Tesseract 설치 시 일부 OCR. 무음 영상에서는 화면 분석을 기반으로 AI가 컷을 선정합니다.
- **FFmpeg**: 컷 생성, 연결, 자막, 음성 정규화, 9:16 세로 또는 16:9 가로 MP4 출력.
- **데이터 관리**: OS 임시 경로의 `one-shot-ai-video-editor/session-<id>`에서만 원본·중간 결과·완성본 보관. 프로젝트/계정/클라우드 업로드 없음.

## 테스트 (Windows, Linux, macOS)

터미널 1:

```sh
python -m venv .venv
# Activate .venv using the appropriate shell.
python -m pip install -r backend/requirements.txt
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

터미널 2:

```sh
npm install
npm run dev -- -H 127.0.0.1
```

자동 검사:

```sh
npm run lint
npm run build
npx tsc --noEmit
python -m unittest discover -s backend/tests -v
```

GitHub Actions에서 Next.js 빌드, Python API, 모의 AI, 화면/음성/무음 영상, 실제 FFmpeg 렌더링 테스트가 자동 실행됩니다. 유료 외부 API 엔드투엔드 검증은 사용자 API 키가 있어야 별도로 가능하며, CI는 외부 유료 서비스를 호출하지 않습니다.

## 세션 및 개인 정보 보호

- 모든 편집 요청은 **127.0.0.1**에서만 수신하고, 브라우저의 POST/DELETE Origin을 검사합니다. 웹 UI는 **127.0.0.1:3100**, API는 **127.0.0.1:8000**으로 고정됩니다.
- 로그인 계정은 만들지 않지만, 임시 HTTPOnly 세션 쿠키로 각 작업의 출력에 대한 접근을 제한합니다. 쿠키는 브라우저 세션 관리를 위한 것이지 영구 프로젝트가 아닙니다.
- API 키는 서버의 실행 중 스레드 메모리에서만 사용하며 DB, 파일, 브라우저 localStorage에 저장하지 않습니다. 사용자가 브라우저에 입력한 키도 '작업 종료' 시 화면 상태에서 지웁니다.
- 외부 AI는 공개 HTTPS 주소만 허용합니다. 로컬 AI 서비스가 필요하면 **ALLOW_LOCAL_AI_HTTP=1**로 명시적으로 허용한 뒤 `http://127.0.0.1:PORT/v1` 주소를 지정합니다.
- 원본·중간 파일·결과물은 사용자가 '작업 종료'를 누르거나 프로세스가 종료되면 정리합니다. 앱이 강제 종료될 경우 오래된 폴더는 한 시간 후 정리 대상으로 처리됩니다. **OS에 의한 복구 불가능한 물리적 삭제를 보장하지는 않습니다.**
- 다운로드 요청 직후에는 서버 파일을 삭제하지 않습니다. 브라우저의 파일 저장 완료를 확실하게 확인할 수 없기 때문입니다.
- 편집 결과와 원본 모두 민감한 내용일 수 있습니다. 외부 AI에 음성 전사·OCR이 전송될 수 있으므로 해당 제공업체의 데이터 정책을 확인하세요.

## 현재 버전의 제한

- 1GiB 이하 파일, 0.5초~30분 영상, 최대 4096px 해상도. 실행 환경의 디스크 여유 공간과 인코딩 성능에 영향을 받습니다.
- 발화 구간을 중심으로 편집할 때는 선택된 실제 ASR 세그먼트를 사용합니다. 음성이 없는 영상은 화면 변화 점수와 선택적 OCR로 후보를 구성하므로, 실제 시각 의미 분석은 제한적입니다.
- 쇼츠는 원본 전체 화면을 유지한 채 흐린 배경으로 9:16을 채웁니다. 슬라이드·그래프의 텍스트를 새 레이아웃으로 재구성하거나 고품질 모션 그래픽을 만드는 기능은 아직 없습니다.
- 자막은 ASR 결과이며 전문적인 팩트체크·실시간 화자 식별·완벽한 입모양 싱크를 보장하지 않습니다.
- 영상 품질이 자동으로 '100점'이 되는 것은 아닙니다. 특히 정치·경제·의료 등 사실 검증이 중요한 콘텐츠는 게시 전에 원본과 비교하세요.
- 브라우저 새로고침 후 편집 화면 상태는 복원되지 않습니다. 서버 임시 세션은 만료 또는 종료 시 삭제됩니다.
- 동시 접속을 전제로 하는 다중 사용자 서비스나 외부 공개 배포용이 아닙니다.

## 소스 파일

```text
src/app/page.tsx       업로드·편집·미리보기 UI
backend/main.py        FastAPI / 로그인 없는 임시 세션 API
backend/session_manager.py   세션·취소·정리
backend/provider.py    호환 AI API 및 로컬 ASR
backend/planner.py     AI 컷 계획 및 검증
backend/visual.py      장면 변화 / 선택적 OCR
backend/media.py       FFprobe / FFmpeg / MP4 출력
backend/pipeline.py    전체 작업 연결
backend/tests/         단위·API·실제 FFmpeg 테스트
run.bat, stop.bat       Windows 실행 및 종료
```
