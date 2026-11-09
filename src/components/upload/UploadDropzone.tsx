"use client";

import { useRef, useState } from "react";

type Upload = { id: string; assetId: string; partSize: number; parts: number };

async function api<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "서버 요청에 실패했습니다.");
  return data as T;
}

function fileContentType(file: File): string {
  if (["video/mp4", "video/webm", "video/quicktime"].includes(file.type)) return file.type;
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "mp4") return "video/mp4";
  if (extension === "mov") return "video/quicktime";
  if (extension === "webm") return "video/webm";
  return "";
}

function putPart(
  url: string,
  chunk: Blob,
  onProgress: (bytes: number) => void,
  activeXhr: React.MutableRefObject<XMLHttpRequest | null>,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    activeXhr.current = xhr;
    xhr.open("PUT", url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded);
    };
    xhr.onerror = () => reject(new Error("네트워크 오류: 업로드 실패"));
    xhr.onabort = () => reject(new Error("업로드가 취소되었습니다."));
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error("스토리지 업로드 실패 (" + xhr.status + ")"));
        return;
      }
      const etag = xhr.getResponseHeader("ETag");
      if (!etag) {
        reject(new Error("스토리지의 CORS 설정에서 ETag를 노출해야 합니다."));
        return;
      }
      resolve(etag);
    };
    xhr.send(chunk);
  });
}

export default function UploadDropzone({
  projectId,
  onUploaded,
}: {
  projectId: string;
  onUploaded: (assetId: string) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const activeXhr = useRef<XMLHttpRequest | null>(null);
  const canceled = useRef(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    if (busy) return;
    setError("");
    const contentType = fileContentType(file);
    if (!contentType || file.size === 0 || file.size > 1024 * 1024 * 1024) {
      setError("MP4, MOV, WebM 파일만 지원합니다 (1GiB 이하).");
      return;
    }
    canceled.current = false;
    setBusy(true);
    setProgress(0);
    let session: Upload | null = null;
    try {
      const initiated = await api<{ upload: Upload }>("/api/uploads/init", {
        projectId, fileName: file.name, contentType, bytes: file.size,
      });
      session = initiated.upload;
      const parts: { partNumber: number; etag: string }[] = [];
      let transferred = 0;
      for (let partNumber = 1; partNumber <= session.parts; partNumber += 1) {
        if (canceled.current) throw new Error("업로드가 취소되었습니다.");
        const start = (partNumber - 1) * session.partSize;
        const chunk = file.slice(start, Math.min(start + session.partSize, file.size));
        let lastError: unknown = null;
        let etag: string | null = null;
        for (let attempt = 0; attempt < 3 && !etag; attempt += 1) {
          if (canceled.current) throw new Error("업로드가 취소되었습니다.");
          try {
            const signed = await api<{ url: string }>("/api/uploads/" + session.id + "/parts", { partNumber });
            etag = await putPart(signed.url, chunk, (sent) => {
              setProgress(Math.round((transferred + sent) / file.size * 100));
            }, activeXhr);
          } catch (e) {
            lastError = e;
            if (canceled.current) throw e;
          }
        }
        if (!etag) throw lastError instanceof Error ? lastError : new Error("업로드 실패");
        parts.push({ partNumber, etag });
        transferred += chunk.size;
        setProgress(Math.round(transferred / file.size * 100));
      }
      if (canceled.current) throw new Error("업로드가 취소되었습니다.");
      await api("/api/uploads/" + session.id + "/complete", { parts });
      await onUploaded(session.assetId);
    } catch (e) {
      if (session) {
        await api("/api/uploads/" + session.id + "/abort", {}).catch(() => {});
      }
      setError(e instanceof Error ? e.message : "업로드에 실패했습니다.");
    } finally {
      activeXhr.current = null;
      setBusy(false);
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <section className="rounded-xl border border-dashed border-zinc-500 p-4 text-center"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file) void upload(file);
      }}>
      <input ref={inputRef} type="file" className="hidden" accept=".mp4,.mov,.webm,video/*"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}/>
      <p className="mb-2 text-sm font-semibold">영상 업로드</p>
      <p className="mb-3 text-xs text-zinc-500">MP4 · MOV · WebM / 최대 1GiB</p>
      <button type="button" disabled={busy}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        onClick={() => inputRef.current?.click()}>파일 선택</button>
      {progress !== null && (
        <div aria-label="업로드 진행률" className="mt-3">
          <div className="h-2 rounded bg-zinc-300 dark:bg-zinc-700">
            <div className="h-2 rounded bg-blue-600" style={{ width: progress + "%" }}/>
          </div>
          <p className="mt-1 text-xs">{progress}%</p>
          <button type="button" className="text-xs underline" onClick={() => {
            canceled.current = true;
            activeXhr.current?.abort();
          }}>업로드 취소</button>
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-xs text-red-500">{error}</p>}
    </section>
  );
}
