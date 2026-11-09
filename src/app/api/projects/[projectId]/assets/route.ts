import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { ownedProject } from "@/lib/projects";
import { jsonError } from "@/lib/security";

export const runtime = "nodejs";
type Params = { params: Promise<{ projectId: string }> };

export async function GET(_: Request, { params }: Params) {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { projectId } = await params;
  if (!(await ownedProject(projectId, user.id))) return jsonError("Project not found", 404);
  const assets = await prisma.mediaAsset.findMany({
    where: { projectId, status: "READY" },
    select: {
      id: true, fileName: true, contentType: true,
      durationMs: true, width: true, height: true,
    },
    orderBy: { createdAt: "asc" },
  });
  return NextResponse.json({ assets });
}
