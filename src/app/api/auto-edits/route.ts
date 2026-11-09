import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { isSameOrigin, jsonError } from "@/lib/security";

export const runtime = "nodejs";
const schema = z.object({
  projectId: z.string().min(1),
  assetId: z.string().min(1),
  format: z.enum(["shorts", "wide"]),
  style: z.enum(["auto", "news", "dynamic", "calm"]),
  targetSeconds: z.union([z.literal(30), z.literal(45), z.literal(60), z.literal(120)]),
}).strict();

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid auto-edit request", 400);
  const { projectId, assetId, format, style, targetSeconds } = parsed.data;
  const [asset, config] = await Promise.all([
    prisma.mediaAsset.findFirst({
      where: { id: assetId, projectId, status: "READY", project: { ownerId: user.id } },
      select: { id: true },
    }),
    prisma.aiProviderConfig.findUnique({ where: { userId: user.id }, select: { userId: true } }),
  ]);
  if (!asset) return jsonError("Video not available", 404);
  if (!config) return jsonError("Configure an AI provider first", 400);
  const pending = await prisma.autoEditJob.count({
    where: { ownerId: user.id, status: { in: ["QUEUED", "RUNNING"] } },
  });
  if (pending >= 2) return jsonError("Maximum two concurrent jobs per user", 429);
  const job = await prisma.autoEditJob.create({
    data: { projectId, assetId, ownerId: user.id, format, style, targetSeconds },
    select: { id: true, status: true, progress: true },
  });
  return NextResponse.json({ job }, { status: 201 });
}
