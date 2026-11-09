import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/security";
import { abortUpload } from "@/lib/storage";

export const runtime = "nodejs";
type Params = { params: Promise<{ id: string }> };

export async function POST(request: Request, { params }: Params) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { id } = await params;
  const session = await prisma.uploadSession.findFirst({
    where: { id, status: "UPLOADING", asset: { project: { ownerId: user.id } } },
    include: { asset: true },
  });
  if (!session) return jsonError("Upload session not found", 404);
  await abortUpload(session.asset.objectKey, session.uploadId).catch(() => {});
  await prisma.$transaction([
    prisma.uploadSession.update({ where: { id }, data: { status: "ABORTED" } }),
    prisma.mediaAsset.update({ where: { id: session.asset.id }, data: { status: "FAILED" } }),
  ]);
  return NextResponse.json({ ok: true });
}
