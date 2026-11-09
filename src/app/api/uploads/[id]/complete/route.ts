import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/security";
import { completeUpload, objectSize } from "@/lib/storage";

export const runtime = "nodejs";
type Params = { params: Promise<{ id: string }> };
const schema = z.object({
  parts: z.array(z.object({
    partNumber: z.number().int().min(1).max(10_000),
    etag: z.string().min(1).max(256),
  }).strict()).min(1).max(128),
}).strict();

export async function POST(request: Request, { params }: Params) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return jsonError("Invalid uploaded parts", 400);
  const { id } = await params;
  const session = await prisma.uploadSession.findFirst({
    where: { id, status: "UPLOADING", asset: { project: { ownerId: user.id } } },
    include: { asset: true },
  });
  if (!session) return jsonError("Upload session not found", 404);
  const expected = Math.ceil(Number(session.asset.bytes) / session.partSize);
  const sorted = [...parsed.data.parts].sort((a, b) => a.partNumber - b.partNumber);
  if (sorted.length !== expected || sorted.some((p, i) => p.partNumber !== i + 1)) {
    return jsonError("Missing or duplicate upload part", 400);
  }

  try {
    await completeUpload(session.asset.objectKey, session.uploadId, sorted);
    const size = await objectSize(session.asset.objectKey);
    if (size !== Number(session.asset.bytes)) {
      await prisma.mediaAsset.update({ where: { id: session.asset.id }, data: { status: "FAILED" } });
      return jsonError("Uploaded object size mismatch", 422);
    }
    await prisma.$transaction([
      prisma.mediaAsset.update({ where: { id: session.asset.id }, data: { status: "READY" } }),
      prisma.uploadSession.update({ where: { id }, data: { status: "COMPLETED" } }),
    ]);
    return NextResponse.json({ assetId: session.asset.id, status: "READY" });
  } catch {
    return jsonError("Storage completion failed; please retry", 502);
  }
}
