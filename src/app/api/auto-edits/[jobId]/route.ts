import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { jsonError } from "@/lib/security";

export const runtime = "nodejs";
type Params = { params: Promise<{ jobId: string }> };

export async function GET(_: Request, { params }: Params) {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { jobId } = await params;
  const job = await prisma.autoEditJob.findFirst({
    where: { id: jobId, ownerId: user.id },
    select: {
      id: true, status: true, progress: true, title: true,
      plan: true, error: true, resultKey: true,
    },
  });
  if (!job) return jsonError("Job not found", 404);
  const { resultKey, ...safe } = job;
  return NextResponse.json({ job: { ...safe, hasDownload: job.status === "DONE" && !!resultKey } },
    { headers: { "Cache-Control": "no-store" } });
}
