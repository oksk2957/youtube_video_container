import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { ownedProject } from "@/lib/projects";
import { isSameOrigin, jsonError } from "@/lib/security";
import { timelineSchema } from "@/features/editor/validation";

export const runtime = "nodejs";
type Params = { params: Promise<{ projectId: string }> };

const saveSchema = z.object({
  revision: z.number().int().min(0),
  timeline: timelineSchema,
}).strict();

export async function GET(_: Request, { params }: Params) {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { projectId } = await params;
  const project = await ownedProject(projectId, user.id);
  if (!project) return jsonError("Project not found", 404);
  return NextResponse.json({ project });
}

export async function PATCH(request: Request, { params }: Params) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { projectId } = await params;
  const body = await request.json().catch(() => null);
  const parsed = saveSchema.safeParse(body);
  if (!parsed.success) return jsonError("Invalid timeline", 400);
  const project = await ownedProject(projectId, user.id);
  if (!project) return jsonError("Project not found", 404);

  const ids = [...new Set(parsed.data.timeline.clips.map((clip) => clip.assetId))];
  const assets = await prisma.mediaAsset.findMany({
    where: { id: { in: ids }, projectId, status: "READY" },
    select: { id: true, durationMs: true },
  });
  if (assets.length !== ids.length) return jsonError("Timeline references unavailable media", 400);
  const byId = new Map(assets.map((asset) => [asset.id, asset]));
  for (const clip of parsed.data.timeline.clips) {
    const asset = byId.get(clip.assetId)!;
    // Client-reported duration is a convenience until server-side probing is enabled.
    if (asset.durationMs && clip.sourceStartMs + clip.durationMs > asset.durationMs + 1000) {
      return jsonError("Timeline clip exceeds source duration", 400);
    }
  }

  const result = await prisma.project.updateMany({
    where: { id: projectId, ownerId: user.id, revision: parsed.data.revision },
    data: { timeline: parsed.data.timeline, revision: { increment: 1 } },
  });
  if (!result.count) return jsonError("Revision conflict: reload project before saving", 409);
  return NextResponse.json({ revision: parsed.data.revision + 1 });
}
