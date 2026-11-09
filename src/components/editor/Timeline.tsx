"use client";

import type { Timeline as TimelineData } from "@/features/editor/timeline.mjs";
import { durationMs } from "@/features/editor/timeline.mjs";

export function formatTime(ms: number) {
  const seconds = Math.floor(ms / 1000);
  return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" +
    String(seconds % 60).padStart(2, "0");
}

export default function Timeline({
  timeline,
  selectedId,
  playheadMs,
  names,
  onSelect,
  onMove,
  onSeek,
}: {
  timeline: TimelineData;
  selectedId: string | null;
  playheadMs: number;
  names: Record<string, string>;
  onSelect: (id: string) => void;
  onMove: (id: string, index: number) => void;
  onSeek: (ms: number) => void;
}) {
  const total = durationMs(timeline);
  return (
    <section aria-label="편집 타임라인" className="rounded-xl border border-zinc-700 bg-zinc-900 p-4 text-white">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-bold">타임라인</h2>
        <span className="text-sm text-zinc-300">{formatTime(playheadMs)} / {formatTime(total)}</span>
      </div>
      <input aria-label="재생 위치" type="range" min={0} max={Math.max(total, 1)}
        step={100} value={Math.min(playheadMs, total)} disabled={!total}
        className="mb-4 w-full accent-blue-500"
        onChange={(event) => onSeek(Number(event.target.value))} />
      <div className="flex min-h-24 items-center gap-1 overflow-x-auto rounded-lg bg-zinc-800 p-2">
        {timeline.clips.map((clip, index) => (
          <button key={clip.id} type="button" draggable
            title="클립을 끌어서 순서를 변경할 수 있습니다."
            onDragStart={(event) => event.dataTransfer.setData("text/plain", clip.id)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const sourceId = event.dataTransfer.getData("text/plain");
              if (sourceId) onMove(sourceId, index);
            }}
            aria-pressed={selectedId === clip.id}
            onClick={() => onSelect(clip.id)}
            className={"h-20 min-w-20 shrink-0 truncate rounded-md border-2 px-2 text-left text-xs " +
              (selectedId === clip.id ? "border-yellow-300 bg-blue-600" : "border-blue-700 bg-blue-900")}
            style={{ width: Math.max(80, total ? (clip.durationMs / total) * 550 : 80) + "px" }}>
            <span className="block truncate font-semibold">{names[clip.assetId] || "비디오"}</span>
            <span className="mt-2 block opacity-80">{formatTime(clip.durationMs)}</span>
          </button>
        ))}
        {!timeline.clips.length && <p className="px-2 text-sm text-zinc-400">왼쪽의 영상을 추가하면 타임라인에 나타납니다.</p>}
      </div>
    </section>
  );
}
