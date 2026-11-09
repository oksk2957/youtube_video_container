"use client";
import { useEffect, useState } from "react";

type Asset = { id: string; fileName: string };
type Provider = { baseUrl: string; chatModel: string; transcriptionModel: string; hasApiKey: boolean };
type Job = { id: string; status: string; progress: number; title?: string | null; error?: string | null; hasDownload?: boolean };

export default function AutoEditPanel({ projectId, assets }: { projectId: string; assets: Asset[] }) {
  const [provider, setProvider] = useState<Provider | null>(null);
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [chatModel, setChatModel] = useState("gpt-4o-mini");
  const [transcriptionModel, setTranscriptionModel] = useState("whisper-1");
  const [apiKey, setApiKey] = useState("");
  const [assetId, setAssetId] = useState("");
  const [format, setFormat] = useState<"shorts" | "wide">("shorts");
  const [style, setStyle] = useState<"auto" | "news" | "dynamic" | "calm">("auto");
  const [targetSeconds, setTargetSeconds] = useState<30 | 45 | 60 | 120>(45);
  const [job, setJob] = useState<Job | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch("/api/ai-provider").then(r => r.json()).then(d => {
      if (!active || !d.config) return;
      setProvider(d.config);
      setBaseUrl(d.config.baseUrl);
      setChatModel(d.config.chatModel);
      setTranscriptionModel(d.config.transcriptionModel);
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!assets.some(a => a.id === assetId)) {
      // The selection can become stale when a media upload completes.
      const id = assets[0]?.id;
      if (id) queueMicrotask(() => setAssetId(id));
    }
  }, [assets, assetId]);
  useEffect(() => {
    if (!job || !["QUEUED", "RUNNING"].includes(job.status)) return;
    let active = true;
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch("/api/auto-edits/" + job.id, { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          if (active) setJob(data.job);
        }
      } catch { /* Retry polling. */ }
    }, 3000);
    return () => { active = false; clearInterval(interval); };
  }, [job?.id, job?.status]);

  async function saveProvider() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/ai-provider", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseUrl, chatModel, transcriptionModel, ...(apiKey ? { apiKey } : {}) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "설정 저장 실패");
      setProvider({ baseUrl, chatModel, transcriptionModel, hasApiKey: true });
      setApiKey("");
      setMessage("AI 제공업체 설정을 저장했습니다.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "설정 오류"); }
    finally { setBusy(false); }
  }
  async function start() {
    if (!assetId) return;
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/auto-edits", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId, assetId, format, style, targetSeconds }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "AI 자동 편집 요청 실패");
      setJob(data.job);
      setMessage("작업 대기열에 등록했습니다.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "오류"); }
    finally { setBusy(false); }
  }

  return (
    <section className="mt-8 rounded-xl border border-blue-900 bg-zinc-900 p-5 text-white">
      <h2 className="text-lg font-bold">✨ AI 자동 편집 (Python + FFmpeg)</h2>
      <p className="mt-1 text-xs text-zinc-400">AI가 발화를 분석해 핵심 구간을 선택하고 자막을 합성해 MP4를 만듭니다.</p>
      <details className="mt-4 rounded-lg border border-zinc-700 p-3" open={!provider}>
        <summary className="cursor-pointer text-sm font-semibold">AI Base URL · 모델 · API 키 설정</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs sm:col-span-2">API Base URL
            <input aria-label="AI API Base URL" value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1" className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm"/>
          </label>
          <label className="text-xs">편집 분석 AI 모델
            <input value={chatModel} onChange={e => setChatModel(e.target.value)}
              className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm"/>
          </label>
          <label className="text-xs">음성 인식 모델 (segment timestamps 필수)
            <input value={transcriptionModel} onChange={e => setTranscriptionModel(e.target.value)}
              className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm"/>
          </label>
          <label className="text-xs sm:col-span-2">API 키
            <input type="password" autoComplete="off" value={apiKey} onChange={e => setApiKey(e.target.value)}
              placeholder={provider ? "설정됨 · 변경하려면 새 키를 입력" : "API 키 입력"}
              className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm"/>
          </label>
        </div>
        <p className="mt-3 text-xs text-amber-300">
          서버 AI_ALLOWED_HOSTS에 API 도메인을 허용해야 합니다. /chat/completions와
          /audio/transcriptions (verbose_json 타임스탬프) 호환 서버가 필요합니다.
        </p>
        <button type="button" disabled={busy} onClick={() => void saveProvider()}
          className="mt-3 rounded bg-blue-600 px-4 py-2 text-sm disabled:opacity-40">설정 저장</button>
      </details>
      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <label className="text-xs sm:col-span-2">원본 동영상
          <select value={assetId} onChange={e => setAssetId(e.target.value)}
            className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm">
            <option value="">동영상 선택</option>
            {assets.map(a => <option key={a.id} value={a.id}>{a.fileName}</option>)}
          </select>
        </label>
        <label className="text-xs">출력 형식
          <select value={format} onChange={e => setFormat(e.target.value as "shorts" | "wide")}
            className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm">
            <option value="shorts">쇼츠 9:16</option>
            <option value="wide">일반 16:9</option>
          </select>
        </label>
        <label className="text-xs">목표 길이
          <select value={targetSeconds} onChange={e => setTargetSeconds(Number(e.target.value) as 30 | 45 | 60 | 120)}
            className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm">
            {[30,45,60,120].map(n => <option key={n} value={n}>{n}초</option>)}
          </select>
        </label>
        <label className="text-xs sm:col-span-2">자동 편집 스타일
          <select value={style} onChange={e => setStyle(e.target.value as "auto" | "news" | "dynamic" | "calm")}
            className="mt-1 w-full rounded bg-zinc-800 p-2 text-sm">
            <option value="auto">AI 자동 판단</option>
            <option value="news">정보·뉴스형</option>
            <option value="dynamic">다이내믹 하이라이트</option>
            <option value="calm">차분한 설명형</option>
          </select>
        </label>
        <div className="flex items-end sm:col-span-2">
          <button type="button" disabled={busy || !provider || !assetId || ["QUEUED", "RUNNING"].includes(job?.status || "")}
            onClick={() => void start()} className="w-full rounded bg-emerald-600 px-4 py-2 text-sm font-semibold disabled:opacity-40">
            AI 자동 편집 시작
          </button>
        </div>
      </div>
      {message && <p role="status" className="mt-3 text-sm">{message}</p>}
      {job && (
        <div className="mt-4 rounded-lg border border-zinc-700 p-3 text-sm" aria-live="polite">
          <p>작업 상태: {job.status} · {job.progress}%</p>
          <div className="mt-2 h-2 overflow-hidden rounded bg-zinc-700">
            <div className="h-full bg-emerald-500" style={{ width: job.progress + "%" }}/>
          </div>
          {job.title && <p className="mt-2 font-semibold">{job.title}</p>}
          {job.error && <p role="alert" className="mt-2 text-red-400">{job.error}</p>}
          {job.hasDownload && <a href={"/api/auto-edits/" + job.id + "/download"}
            className="mt-3 inline-block rounded bg-blue-600 px-4 py-2">MP4 다운로드</a>}
        </div>
      )}
      <p className="mt-3 text-xs text-zinc-500">중요한 주장·수치·인용은 자동 편집 결과와 원본을 비교해 검토하세요.</p>
    </section>
  );
}
