import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/security";
import { emptyTimeline } from "@/features/editor/timeline.mjs";

export const runtime = "nodejs";

const createSchema = z.object({ name: z.string().trim().min(1).max(80) }).strict();

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const projects = await prisma.project.findMany({
    where: { ownerId: user.id },
    orderBy: { updatedAt: "desc" },
    select: { id: true, name: true, revision: true, updatedAt: true },
  });
  return NextResponse.json({ projects });
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const body = await request.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return jsonError("Invalid project name", 400);
  const project = await prisma.project.create({
    data: { ownerId: user.id, name: parsed.data.name, timeline: emptyTimeline() },
    select: { id: true, name: true },
  });
  return NextResponse.json({ project }, { status: 201 });
}
