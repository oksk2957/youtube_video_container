"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import UploadDropzone from "@/components/upload/UploadDropzone";
import Timeline, { formatTime } from "@/components/editor/Timeline";
import {
  appendClip, clipAt, durationMs, moveClip, removeClip, splitClip, trimClip,
} from "@/features/editor/timeline.mjs";
import type { Timeline as TimelineData } from "@/features/editor/timeline.mjs";

export type MediaAsset = {
  id: string; fileName: string; contentType: string;
  durationMs: number | null; width: number | null; height: number | null;
};

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "요청에 실패했습니다.");
  return data as T;
}

function getVideoMetadata(url: string): Promise<{ durationMs: number; width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      if (!Number.isFinite(video.duration) || video.duration <= 0) {
        reject(new Error("영상 길이를 확인할 수 없습니다.")); return;
      }
      resolve({
        durationMs: Math.round(video.duration * 1000),
        width: video.videoWidth,
        height: video.videoHeight,
      });
      video.removeAttribute("src");
      video.load();
    };
    video.onerror = () => reject(new Error("브라우저가 이 영상의 코덱을 지원하지 않습니다."));
    video.src = url;
  });
}

export default function EditorShell({
  projectId, projectName, initialTimeline, initialRevision, initialAssets,
}: {
  projectId: string; projectName: string;
  initialTimeline: TimelineData; initialRevision: number; initialAssets: MediaAsset[];
}) {
  const [timeline, setTimeline] = useState<TimelineData>(initialTimeline);
  const [assets, setAssets] = useState<MediaAsset[]>(initialAssets);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(initialTimeline.clips[0]?.id ?? null);
  const [playheadMs, setPlayheadMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState("저장됨");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TimelineData[]>([]);
  const [future, setFuture] = useState<TimelineData[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const currentDraft = useRef(timeline);
  const persistedDraft = useRef(timeline);
  const revision = useRef(initialRevision);
  const saving = useRef(false);
  const saveBlocked = useRef(false);

  useEffect(() => { currentDraft.current = timeline; }, [timeline]);

  useEffect(() => {
    let alive = true;
    async function resolveUrls() {
      const missing = assets.filter((asset) => !urls[asset.id]);
      if (!missing.length) return;
      const results = await Promise.all(missing.map(async (asset) => {
        try {
          const { url } = await getJson<{ url: string }>("/api/assets/" + asset.id + "/url");
          return [asset.id, url] as const;
        } catch { return null; }
      }));
      if (alive) setUrls((previous) => ({
        ...previous,
        ...Object.fromEntries(results.filter((result) => result !== null)),
      }));
    }
    void resolveUrls();
    return () => { alive = false; };
  }, [assets, urls]);

  const save = useCallback(async () => {
    if (saving.current || saveBlocked.current || currentDraft.current === persistedDraft.current) return;
    saving.current = true;
    setStatus("저장 중...");
    const snapshot = currentDraft.current;
    try {
      const response = await fetch("/api/projects/" + projectId, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ revision: revision.current, timeline: snapshot }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 409) saveBlocked.current = true;
        throw new Error(data.error || "저장에 실패했습니다.");
      }
      revision.current = data.revision;
      persistedDraft.current = snapshot;
      setStatus("저장됨");
      setError("");
    } catch (e) {
      setStatus("저장 실패");
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      saving.current = false;
      if (!saveBlocked.current && currentDraft.current !== persistedDraft.current) {
        setTimeout(() => { void save(); }, 1500);
      }
    }
  }, [projectId]);

  useEffect(() => {
    if (timeline === persistedDraft.current || saveBlocked.current) return;
    const handle = setTimeout(() => { void save(); }, 1200);
    return () => clearTimeout(handle);
  }, [timeline, save]);

  function edit(next: TimelineData) {
    if (saveBlocked.current) { setError("저장 충돌입니다. 새로고침 후 다시 편집하세요."); return; }
    setHistory((previous) => [...previous.slice(-49), timeline]);
    setFuture([]);
    currentDraft.current = next;
    setTimeline(next);
    setPlayheadMs((position) => Math.min(position, durationMs(next)));
    setStatus("변경됨");
    setError("");
  }

  function execute(command: () => TimelineData) {
    try { edit(command()); }
    catch (e) { setError(e instanceof Error ? e.message : "편집 오류"); }
  }

  const total = durationMs(timeline);
  const active = clipAt(timeline, Math.min(playheadMs, Math.max(0, total - 1)));
  const selected = timeline.clips.find((clip) => clip.id === selectedId);
  const names = Object.fromEntries(assets.map((asset) => [asset.id, asset.fileName]));
  const videoSrc = active ? urls[active.clip.assetId] : undefined;

  useEffect(() => {
    const player = videoRef.current;
    if (!player || !active || !videoSrc) return;
    const target = (active.clip.sourceStartMs + playheadMs - active.startMs) / 1000;
    if (player.readyState >= 1 && Math.abs(player.currentTime - target) > 0.35) {
      player.currentTime = target;
    }
    if (playing && player.paused) {
      void player.play().catch(() => setPlaying(false));
    }
  }, [active, playheadMs, videoSrc, playing]);

  function onTimeUpdate() {
    const player = videoRef.current;
    if (!player || !active) return;
    const relative = Math.round(player.currentTime * 1000) - active.clip.sourceStartMs;
    if (relative >= active.clip.durationMs - 50) {
      if (active.index === timeline.clips.length - 1) {
        setPlaying(false);
        setPlayheadMs(total);
        player.pause();
      } else setPlayheadMs(active.endMs);
    } else if (relative >= 0) {
      setPlayheadMs(active.startMs + relative);
    }
  }

  async function uploaded(assetId: string) {
    const { url } = await getJson<{ url: string }>("/api/assets/" + assetId + "/url");
    const metadata = await getVideoMetadata(url);
    const response = await fetch("/api/assets/" + assetId, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(metadata),
    });
    if (!response.ok) throw new Error("영상 정보 저장 실패");
    const result = await getJson<{ assets: MediaAsset[] }>("/api/projects/" + projectId + "/assets");
    setAssets(result.assets);
    setUrls((previous) => ({ ...previous, [assetId]: url }));
    edit(appendClip(currentDraft.current, {
      id: crypto.randomUUID(), assetId, durationMs: metadata.durationMs,
    }));
    setSelectedId(null);
  }

  function seek(position: number) {
    setPlayheadMs(Math.max(0, Math.min(position, total)));
    if (position >= total) setPlaying(false);
  }

  function split() {
    if (!selected) return;
    let start = 0;
    for (const clip of timeline.clips) {
      if (clip.id === selected.id) break;
      start += clip.durationMs;
    }
    const offset = playheadMs - start;
    execute(() => splitClip(timeline, selected.id, offset, crypto.randomUUID()));
  }

  function undo() {
    if (!history.length) return;
    const previous = history[history.length - 1];
    setHistory((items) => items.slice(0, -1));
    setFuture((items) => [...items, timeline]);
    currentDraft.current = previous;
    setTimeline(previous);
    setStatus("변경됨");
  }

  function redo() {
    if (!future.length) return;
    const next = future[future.length - 1];
    setFuture((items) => items.slice(0, -1));
    setHistory((items) => [...items, timeline]);
    currentDraft.current = next;
    setTimeline(next);
    setStatus("변경됨");
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-5 text-white lg:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-5">
        <div>
          <Link href="/" className="text-sm text-blue-400 hover:underline">← 프로젝트 목록</Link>
          <h1 className="mt-2 text-xl font-bold">{projectName}</h1>
        </div>
        <div className="flex items-center gap-3">
          <span aria-live="polite" className="text-sm text-zinc-400">{status}</span>
          <button type="button" onClick={() => void save()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold">지금 저장</button>
        </div>
      </header>
      {error && <p role="alert" className="mb-4 rounded-lg border border-red-700 bg-red-950 p-3 text-sm">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)_210px]">
        <aside className="space-y-4 rounded-xl border border-zinc-800 p-3">
          <UploadDropzone projectId={projectId} onUploaded={uploaded}/>
          <h2 className="font-semibold">미디어 라이브러리</h2>
          <div className="space-y-2">
            {assets.map((asset) => (
              <div key={asset.id} className="rounded-lg bg-zinc-900 p-3 text-sm">
                <p className="break-all font-medium">{asset.fileName}</p>
                <p className="mt-1 text-xs text-zinc-400">
                  {asset.durationMs ? formatTime(asset.durationMs) : "길이 확인 중"}
                </p>
                <button disabled={!asset.durationMs} type="button"
                  className="mt-2 text-xs text-blue-400 disabled:opacity-40"
                  onClick={() => {
                    if (!asset.durationMs) return;
                    const id = crypto.randomUUID();
                    execute(() => appendClip(timeline, { id, assetId: asset.id, durationMs: asset.durationMs! }));
                    setSelectedId(id);
                  }}>+ 타임라인에 추가</button>
              </div>
            ))}
            {!assets.length && <p className="text-sm text-zinc-500">업로드한 영상이 없습니다.</p>}
          </div>
        </aside>
        <section className="min-w-0 space-y-4">
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-xl bg-black">
            {active && videoSrc ? (
              <video key={active.clip.id} ref={videoRef} src={videoSrc}
                aria-label="편집 미리보기"
                playsInline preload="auto" className="max-h-full max-w-full"
                onLoadedMetadata={() => {
                  const player = videoRef.current;
                  if (!player || !active) return;
                  player.currentTime = (active.clip.sourceStartMs + playheadMs - active.startMs) / 1000;
                  if (playing) void player.play().catch(() => setPlaying(false));
                }}
                onTimeUpdate={onTimeUpdate}
                onEnded={() => {
                  if (!active) return;
                  setPlayheadMs(active.endMs);
                  if (active.index === timeline.clips.length - 1) setPlaying(false);
                }}
              />
            ) : <p className="text-sm text-zinc-500">영상을 업로드하고 타임라인에 추가하세요.</p>}
          </div>
          <div className="flex items-center justify-center gap-5">
            <button type="button" className="rounded-lg border border-zinc-700 px-3 py-2 text-sm"
              onClick={() => { setPlaying(false); seek(0); }}>처음으로</button>
            <button type="button" disabled={!total} className="rounded-lg bg-blue-600 px-6 py-2 font-semibold disabled:opacity-40"
              onClick={() => {
                if (playheadMs >= total) seek(0);
                setPlaying((previous) => !previous);
              }}>{playing ? "일시정지" : "▶ 재생"}</button>
            <span className="text-sm text-zinc-400">{formatTime(playheadMs)} / {formatTime(total)}</span>
          </div>
          <Timeline timeline={timeline} selectedId={selectedId} playheadMs={playheadMs} names={names}
            onSelect={setSelectedId} onSeek={seek}
            onMove={(id, index) => execute(() => moveClip(timeline, id, index))}/>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" disabled={!history.length} className="rounded border border-zinc-700 px-3 py-2 text-sm disabled:opacity-30"
              onClick={undo}>실행 취소</button>
            <button type="button" disabled={!future.length} className="rounded border border-zinc-700 px-3 py-2 text-sm disabled:opacity-30"
              onClick={redo}>다시 실행</button>
            <button type="button" disabled={!selected} className="rounded border border-zinc-700 px-3 py-2 text-sm disabled:opacity-30"
              onClick={split}>재생 위치에서 분할</button>
            <button type="button" disabled={!selected} className="rounded border border-red-800 px-3 py-2 text-sm text-red-400 disabled:opacity-30"
              onClick={() => {
                if (!selected) return;
                execute(() => removeClip(timeline, selected.id));
                setSelectedId(null);
              }}>클립 삭제</button>
          </div>
        </section>
        <aside className="space-y-3 rounded-xl border border-zinc-800 p-4">
          <h2 className="font-bold">클립 속성</h2>
          {selected ? (
            <>
              <p className="break-all text-sm">{names[selected.assetId] || "비디오"}</p>
              <p className="text-xs text-zinc-400">원본 시작 {formatTime(selected.sourceStartMs)}</p>
              <p className="text-xs text-zinc-400">길이 {formatTime(selected.durationMs)}</p>
              <button type="button" className="w-full rounded-lg border border-zinc-700 p-2 text-sm"
                onClick={() => execute(() => trimClip(timeline, selected.id, 1000, 0))}>앞부분 1초 자르기</button>
              <button type="button" className="w-full rounded-lg border border-zinc-700 p-2 text-sm"
                onClick={() => execute(() => trimClip(timeline, selected.id, 0, 1000))}>뒷부분 1초 자르기</button>
              <p className="text-xs text-zinc-500">클립을 드래그하거나 분할·자르기 버튼으로 편집할 수 있습니다.</p>
            </>
          ) : <p className="text-sm text-zinc-500">타임라인에서 클립을 선택하세요.</p>}
          <p className="border-t border-zinc-800 pt-3 text-xs text-amber-300">
            이번 PR은 컷 편집과 타임라인 저장까지 지원합니다.
            MP4 내보내기는 후속 PR에서 별도 렌더링 Worker로 구현합니다.
          </p>
        </aside>
      </div>
    </main>
  );
}
