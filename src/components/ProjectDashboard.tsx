"use client";

import Link from "next/link";
import { useState } from "react";

type Project = { id: string; name: string; revision: number; updatedAt: string };

export default function ProjectDashboard({
  login,
  projects,
}: {
  login: string | null;
  projects: Project[];
}) {
  const [name, setName] = useState("새 영상 프로젝트");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "프로젝트 생성 실패");
      window.location.href = "/projects/" + data.project.id + "/edit";
    } catch (e) {
      setError(e instanceof Error ? e.message : "오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-12">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-200 pb-6 dark:border-zinc-800">
        <div>
          <p className="text-sm font-medium text-blue-600">VIDEO STUDIO</p>
          <h1 className="mt-2 text-3xl font-bold">내 영상 프로젝트</h1>
          <p className="mt-2 text-sm text-zinc-500">업로드하고, 자르고, 순서를 변경한 뒤 저장하세요.</p>
        </div>
        {login ? (
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-500">@{login}</span>
            <button
              className="rounded-lg border px-4 py-2 text-sm"
              onClick={async () => {
                await fetch("/api/auth/logout", { method: "POST" });
                window.location.reload();
              }}
            >로그아웃</button>
          </div>
        ) : (
          <a href="/api/auth/github" className="rounded-lg bg-blue-600 px-5 py-3 font-semibold text-white">
            GitHub로 로그인
          </a>
        )}
      </header>
      {!login ? (
        <section className="mt-20 rounded-2xl border border-zinc-200 p-10 text-center dark:border-zinc-800">
          <h2 className="text-xl font-bold">영상 편집을 시작해 보세요</h2>
          <p className="mt-3 text-zinc-500">프로젝트를 안전하게 보관하려면 GitHub 로그인이 필요합니다.</p>
          <a href="/api/auth/github" className="mt-6 inline-block rounded-lg bg-blue-600 px-5 py-3 text-white">
            로그인 후 시작하기
          </a>
        </section>
      ) : (
        <>
          <form onSubmit={createProject} className="mt-10 flex flex-wrap items-center gap-3">
            <label htmlFor="project-name" className="sr-only">프로젝트 이름</label>
            <input id="project-name" value={name} onChange={(e) => setName(e.target.value)}
              maxLength={80} className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-transparent p-3 dark:border-zinc-700" />
            <button disabled={busy || !name.trim()} className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white disabled:opacity-50">
              {busy ? "생성 중..." : "새 프로젝트"}
            </button>
          </form>
          {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {projects.map((p) => (
              <Link key={p.id} href={"/projects/" + p.id + "/edit"}
                className="rounded-xl border border-zinc-200 p-6 transition hover:border-blue-500 dark:border-zinc-800">
                <h2 className="font-semibold">{p.name}</h2>
                <p className="mt-2 text-xs text-zinc-500">
                  수정 {new Date(p.updatedAt).toLocaleString("ko-KR")} · 버전 {p.revision}
                </p>
              </Link>
            ))}
          </div>
          {projects.length === 0 && <p className="mt-10 text-center text-zinc-500">프로젝트가 없습니다. 첫 프로젝트를 만들어 보세요.</p>}
        </>
      )}
    </main>
  );
}
