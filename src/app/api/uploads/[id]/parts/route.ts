import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/security";
import { getPartUrl } from "@/lib/storage";

export const runtime = "nodejs";
type Params = { params: Promise<{ id: string }> };
const schema = z.object({ partNumber: z.number().int().min(1).max(10_000) }).strict();

export async function POST(request: Request, { params }: Params) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return jsonError("Invalid part number", 400);
  const { id } = await params;
  const session = await prisma.uploadSession.findFirst({
    where: { id, status: "UPLOADING", asset: { project: { ownerId: user.id } } },
    include: { asset: true },
  });
  if (!session) return jsonError("Upload session not found", 404);
  const totalParts = Math.ceil(Number(session.asset.bytes) / session.partSize);
  if (parsed.data.partNumber > totalParts) return jsonError("Part number exceeds file size", 400);
  const url = await getPartUrl(session.asset.objectKey, session.uploadId, parsed.data.partNumber);
  return NextResponse.json({ url });
}
