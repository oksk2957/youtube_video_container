"use client";

import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8100"
    : "http://localhost:8100");
const MAX_BYTES = 1024 * 1024 * 1024;

type SessionInfo = {
  session_id: string;
  filename: string;
  duration: number;
  width: number;
  height: number;
  has_audio: boolean;
};
type Status = {
  status: string;
  progress: number;
  message: string;
  error: string | null;
  has_output: boolean;
  title: string | null;
  analysis_mode: string | null;
  output_duration: number | null;
};

function time(seconds: number) {
  const rounded = Math.round(seconds);
  return Math.floor(rounded / 60) + ":" + String(rounded % 60).padStart(2, "0");
}

function apiErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.slice(0, 3).map(item => {
        if (!item || typeof item !== "object") return "";
        const { loc, msg } = item as { loc?: unknown; msg?: unknown };
        const field = Array.isArray(loc) ? loc.filter(x => x !== "body").join(".") : "";
        return typeof msg === "string" ? (field ? field + ": " : "") + msg : "";
      }).filter(Boolean);
      if (messages.length) return "입력값 오류: " + messages.join(" / ");
    }
  }
  return "서버 요청에 실패했습니다 (HTTP " + status + ").";
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API + path, {
      method,
      credentials: "include",
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("로컬 Python API에 연결하지 못했습니다. 백엔드 창과 8100번 포트를 확인하세요.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
  return data as T;
}


type BackendHealth = {
  app?: string;
  storage?: string;
  ffmpeg?: boolean;
  ffprobe?: boolean;
};

async function verifyLocalEditor(): Promise<void> {
  let response: Response;
  try {
    response = await fetch(API + "/api/health", { credentials: "include", cache: "no-store" });
  } catch {
    throw new Error("Python 편집 서버에 연결할 수 없습니다. run.bat으로 로컬 서버를 실행하세요.");
  }
  if (!response.ok) {
    throw new Error("Python 서버가 올바르게 응답하지 않습니다. 기존 서버를 종료하고 run.bat을 재실행하세요.");
  }
  let health: BackendHealth;
  try {
    health = await response.json();
  } catch {
    throw new Error("Python 서버가 예상과 다른 응답을 반환했습니다.");
  }
  if (health.app !== "one-shot-local" || health.storage !== "temporary-local") {
    throw new Error("예전 S3/MinIO 서버 등 다른 백엔드가 실행 중입니다. 기존 서버를 모두 종료한 뒤 run.bat을 재실행하세요.");
  }
  if (!health.ffmpeg || !health.ffprobe) {
    throw new Error("FFmpeg 또는 FFprobe가 인식되지 않습니다. 설치 및 PATH를 확인하세요.");
  }
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const blobUrl = useRef<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [job, setJob] = useState<Status | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [backendReady, setBackendReady] = useState(false);
  const [backendStatus, setBackendStatus] = useState("Python 서버 연결을 확인 중입니다.");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [chatModel, setChatModel] = useState("gpt-4o-mini");
  const [asrModel, setAsrModel] = useState("local:small");
  const [apiKey, setApiKey] = useState("");
  const [ratio, setRatio] = useState<"shorts" | "wide">("shorts");
  const [style, setStyle] = useState<"auto" | "news" | "dynamic" | "calm">("auto");
  const [duration, setDuration] = useState(45);
  const [enhance, setEnhance] = useState(true);

  useEffect(() => {
    let mounted = true;
    void verifyLocalEditor().then(() => {
      if (mounted) {
        setBackendReady(true);
        setBackendStatus("로컬 편집 엔진 연결됨 · S3/MinIO 사용 안 함");
      }
    }).catch((error) => {
      if (mounted) {
        setBackendReady(false);
        setBackendStatus(error instanceof Error ? error.message : "서버 연결 오류");
      }
    });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!session || !job || !["ANALYZING", "PLANNING", "RENDERING", "CANCELLING"].includes(job.status)) return;
    let active = true;
    const timer = window.setInterval(() => {
      void request<Status>("/api/sessions/" + session.session_id + "/status")
        .then(next => { if (active) setJob(next); })
        .catch(() => { if (active) setError("작업 상태를 확인할 수 없습니다. Python 서버를 확인하세요."); });
    }, 1400);
    return () => { active = false; window.clearInterval(timer); };
  }, [session?.session_id, job?.status]);

  useEffect(() => {
    return () => {
      if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    };
  }, []);

  function showFile(selected: File) {
    if (!/\.(mp4|mov|webm)$/i.test(selected.name) || selected.size === 0 || selected.size > MAX_BYTES) {
      setError("MP4, MOV, WebM 형식의 1GiB 이하 파일을 선택하세요.");
      return;
    }
    if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    const url = URL.createObjectURL(selected);
    blobUrl.current = url;
    setPreview(url);
    setFile(selected);
    setError("");
  }

  async function upload() {
    if (!file || uploading || session) return;
    setError("");
    setUploadPct(0);
    setUploading(true);
    try {
      await verifyLocalEditor();
      setBackendReady(true);
      setBackendStatus("로컬 편집 엔진 연결됨 · S3/MinIO 사용 안 함");
      const info = await new Promise<SessionInfo>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;
        xhr.withCredentials = true;
        xhr.open("POST", API + "/api/sessions");
        xhr.upload.onprogress = event => {
          if (event.lengthComputable) setUploadPct(Math.round(event.loaded / event.total * 100));
        };
        xhr.onerror = () => reject(new Error("로컬 Python 서버에 연결할 수 없습니다. run.bat 실행 상태를 확인하세요."));
        xhr.onabort = () => reject(new Error("업로드를 취소했습니다."));
        xhr.onload = () => {
          const data = (() => { try { return JSON.parse(xhr.responseText); } catch { return {}; } })();
          if (xhr.status < 200 || xhr.status >= 300) {
            reject(new Error(apiErrorMessage(data, xhr.status)));
          } else resolve(data as SessionInfo);
        };
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      });
      setSession(info);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "업로드 실패";
      setError(message);
      if (message.includes("서버") || message.includes("FFmpeg")) {
        setBackendReady(false);
        setBackendStatus(message);
      }
    } finally {
      xhrRef.current = null;
      setUploading(false);
    }
  }

  async function start() {
    if (!session || busy) return;
    if (!apiKey.trim() && !baseUrl.startsWith("http://127.0.0.1") && !baseUrl.startsWith("http://localhost")) {
      setError("AI 제공업체의 API 키를 입력하세요.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const result = await request<Status>("/api/sessions/" + session.session_id + "/start", "POST", {
        base_url: baseUrl, chat_model: chatModel, asr_model: asrModel,
        api_key: apiKey, format: ratio, style, target_seconds: duration, enhance,
      });
      setJob(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "자동 편집 시작 실패");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!session) return;
    setBusy(true);
    try {
      const result = await request<Status>("/api/sessions/" + session.session_id + "/cancel", "POST");
      setJob(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "취소 실패");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setError("");
    if (uploading) xhrRef.current?.abort();
    if (session) {
      try { await request("/api/sessions/" + session.session_id, "DELETE"); }
      catch { setError("서버 정리 요청에 실패했습니다. 임시 파일은 만료 시 자동 정리됩니다."); }
    }
    if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    blobUrl.current = null;
    setPreview("");
    setFile(null);
    setSession(null);
    setJob(null);
    setApiKey("");
    setUploadPct(0);
    if (inputRef.current) inputRef.current.value = "";
  }

  const editing = !!job && ["ANALYZING", "PLANNING", "RENDERING", "CANCELLING"].includes(job.status);
  const completed = job?.status === "COMPLETED" && job.has_output;
  const canEdit = !!session && !editing;
  const videoUrl = session && completed ? API + "/api/sessions/" + session.session_id + "/output" : preview;

  return (
    <main className="app-shell">
      <header className="masthead">
        <div className="brand-icon">✦</div>
        <div>
          <p className="eyebrow">ONE-SHOT STUDIO</p>
          <h1>AI 영상 자동 편집기</h1>
          <p className="muted">업로드 → 자동 편집 → 미리보기 → 다운로드 → 초기화</p>
        </div>
        <span className="local-chip">● 로컬 PC 전용</span>
      </header>
      <p className={backendReady ? "connection-ok" : "connection-warning"} role="status">
        {backendReady ? "✓ " : "⚠ "}{backendStatus}
      </p>

      <div className="workspace">
        <div className="left-column">
          <section className="panel">
            <div className="section-head"><span className="step-index">01</span><h2>영상 업로드</h2></div>
            {!session ? (
              <div className="drop-area" onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); if (!session && !uploading && e.dataTransfer.files[0]) showFile(e.dataTransfer.files[0]); }}>
                <div className="drop-symbol">↥</div>
                <strong>{file ? file.name : "MP4 파일을 여기로 끌어오세요"}</strong>
                <p>MP4 · MOV · WebM / 최대 1GiB · 로컬 임시 저장</p>
                <input ref={inputRef} type="file" accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm" hidden
                  onChange={e => { if (e.target.files?.[0]) showFile(e.target.files[0]); }}/>
                <button className="outline-button" type="button" disabled={uploading} onClick={() => inputRef.current?.click()}>
                  파일 선택
                </button>
              </div>
            ) : (
              <div className="uploaded-file">
                <span className="file-mark">▶</span>
                <div><strong>{session.filename}</strong>
                  <p>{time(session.duration)} · {session.width}×{session.height} · {session.has_audio ? "음성 있음" : "무음 영상"}</p>
                </div>
                <span className="success-dot">✓</span>
              </div>
            )}
            {file && !session && (
              <div className="upload-actions">
                <button className="primary-button" type="button" disabled={uploading} onClick={() => void upload()}>
                  {uploading ? "업로드 중..." : "이 영상으로 시작"}
                </button>
                {uploading && <>
                  <progress max={100} value={uploadPct} className="progress-bar"/>
                  <span className="small muted">{uploadPct}%</span>
                  <button className="text-button" type="button" onClick={() => xhrRef.current?.abort()}>업로드 취소</button>
                </>}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-head"><span className="step-index">02</span><h2>AI 연결</h2></div>
            <label className="field">AI Base URL
              <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} disabled={editing} spellCheck={false}
                placeholder="https://api.example.com/v1" autoComplete="off"/>
            </label>
            <div className="field-grid">
              <label className="field">분석 모델
                <input value={chatModel} onChange={e => setChatModel(e.target.value)} disabled={editing} spellCheck={false}/>
              </label>
              <label className="field">음성 인식
                <input value={asrModel} onChange={e => setAsrModel(e.target.value)} disabled={editing} spellCheck={false}
                  placeholder="local:small 또는 whisper-1"/>
              </label>
            </div>
            <label className="field">API 키 (세션 종료 시 폐기)
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} disabled={editing}
                autoComplete="off" placeholder="이 편집 작업에만 사용"/>
            </label>
            <p className="hint">일반 공개 HTTPS AI API 사용 가능. 로컬 Whisper는 <code>local:small</code>.
              외부 AI에는 선택한 영상의 음성 전사 및 화면 분석 내용이 전송될 수 있습니다.</p>
          </section>

          <section className="panel">
            <div className="section-head"><span className="step-index">03</span><h2>자동 편집 설정</h2></div>
            <div className="field-grid">
              <label className="field">출력 형식
                <select disabled={editing} value={ratio} onChange={e => setRatio(e.target.value as "shorts" | "wide")}>
                  <option value="shorts">쇼츠 · 9:16 세로</option>
                  <option value="wide">일반 · 16:9 가로</option>
                </select>
              </label>
              <label className="field">완성 길이
                <select disabled={editing} value={duration} onChange={e => setDuration(Number(e.target.value))}>
                  <option value={30}>30초</option><option value={45}>45초</option>
                  <option value={60}>60초</option><option value={120}>2분</option>
                </select>
              </label>
              <label className="field full">AI 스타일
                <select disabled={editing} value={style} onChange={e => setStyle(e.target.value as typeof style)}>
                  <option value="auto">AI 자동 판단</option>
                  <option value="news">정보·뉴스형 (내용 보존)</option>
                  <option value="dynamic">다이내믹 하이라이트</option>
                  <option value="calm">차분한 설명형</option>
                </select>
              </label>
            </div>
            <label className="toggle"><input type="checkbox" checked={enhance} disabled={editing}
              onChange={e => setEnhance(e.target.checked)}/><span>한국어 자막·음량 정리</span></label>
            <button className="primary-button wide" disabled={!canEdit || busy} type="button" onClick={() => void start()}>
              ✨ {completed ? "설정을 바꿔 다시 편집" : "AI 자동 편집 시작"}
            </button>
            <p className="hint">기존 원본을 손상시키지 않고 새 결과를 만듭니다.</p>
          </section>
        </div>

        <div className="right-column">
          <section className="panel preview-panel">
            <div className="section-head"><span className="step-index">04</span>
              <h2>{completed ? "완성 영상 미리보기" : "영상 미리보기"}</h2></div>
            <div className={"video-stage " + (ratio === "shorts" && completed ? "vertical" : "")}>
              {videoUrl ? (
                <video key={videoUrl} controls playsInline src={videoUrl} className="preview-video"/>
              ) : (
                <div className="empty-preview"><span>▶</span><p>영상을 업로드하면 여기에서 확인할 수 있습니다.</p></div>
              )}
            </div>
            {job && (
              <div className="job-status" aria-live="polite">
                <div className="job-row"><strong>{job.message}</strong><span>{job.progress}%</span></div>
                <progress className="progress-bar" max={100} value={job.progress}/>
                {job.analysis_mode && <p className="hint">분석 방식: {job.analysis_mode}</p>}
                {job.error && <p className="error-text" role="alert">{job.error}</p>}
                {editing && <button className="outline-button" type="button" disabled={busy}
                  onClick={() => void cancel()}>편집 중단</button>}
              </div>
            )}
            {completed && session && (
              <div className="result-actions">
                <div className="result-summary"><strong>{job.title || "AI 편집 영상"}</strong>
                  <span>최종 길이 약 {time(job.output_duration || duration)}</span>
                </div>
                <a className="primary-button wide download-button"
                  href={API + "/api/sessions/" + session.session_id + "/download"}>
                  ↓ MP4 다운로드
                </a>
                <p className="hint">다운로드한 파일은 PC에 남습니다. 작업 종료 전까지 재편집할 수 있습니다.</p>
              </div>
            )}
          </section>
          <section className="panel bottom-panel">
            <div className="section-head"><span className="step-index">05</span><h2>작업 종료·초기화</h2></div>
            <p className="muted">업로드 원본, 전사, 임시 영상과 결과물은 프로그램의 임시 세션에서만 관리합니다.</p>
            <button className="outline-button danger" type="button"
              disabled={!file && !session} onClick={() => void reset()}>
              ↺ 작업 종료하고 처음부터 시작
            </button>
            <p className="hint">창을 닫아도 만료된 세션은 자동 정리됩니다. 다운로드 파일은 삭제하지 않습니다.</p>
          </section>
          {error && <div className="alert" role="alert">{error}</div>}
        </div>
      </div>
      <footer>개인 PC용 일회성 편집기 · 계정/프로젝트/클라우드 저장 없음 · AI 편집 결과는 게시 전 확인하세요.</footer>
    </main>
  );
}
