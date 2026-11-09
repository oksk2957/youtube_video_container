import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getReadUrl } from "@/lib/storage";
import { jsonError } from "@/lib/security";

export const runtime = "nodejs";
type Params = { params: Promise<{ jobId: string }> };

export async function GET(_: Request, { params }: Params) {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { jobId } = await params;
  const job = await prisma.autoEditJob.findFirst({
    where: { id: jobId, ownerId: user.id, status: "DONE" },
    select: { resultKey: true },
  });
  if (!job?.resultKey) return jsonError("Completed export not found", 404);
  return NextResponse.redirect(await getReadUrl(job.resultKey), {
    headers: { "Cache-Control": "no-store" },
  });
}
