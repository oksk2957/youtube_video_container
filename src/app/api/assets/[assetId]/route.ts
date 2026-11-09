import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { ownedAsset } from "@/lib/projects";
import { isSameOrigin, jsonError } from "@/lib/security";

export const runtime = "nodejs";
type Params = { params: Promise<{ assetId: string }> };
const schema = z.object({
  durationMs: z.number().int().min(100).max(14_400_000),
  width: z.number().int().min(1).max(16_384),
  height: z.number().int().min(1).max(16_384),
}).strict();

export async function PATCH(request: Request, { params }: Params) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { assetId } = await params;
  const asset = await ownedAsset(assetId, user.id);
  if (!asset || asset.status !== "READY") return jsonError("Asset not found", 404);
  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return jsonError("Invalid video metadata", 400);
  await prisma.mediaAsset.update({ where: { id: assetId }, data: parsed.data });
  return NextResponse.json({ ok: true });
}
