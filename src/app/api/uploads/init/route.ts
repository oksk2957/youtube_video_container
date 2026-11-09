import { NextResponse } from "next/server";
import { z } from "zod";
import { randomUUID } from "node:crypto";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { ownedProject } from "@/lib/projects";
import { isSameOrigin, jsonError } from "@/lib/security";
import { initiateUpload, PART_SIZE, MAX_FILE_SIZE } from "@/lib/storage";

export const runtime = "nodejs";

const allowed = {
  "video/mp4": "mp4",
  "video/quicktime": "mov",
  "video/webm": "webm",
} as const;
const schema = z.object({
  projectId: z.string().min(1),
  fileName: z.string().trim().min(1).max(255),
  contentType: z.enum(["video/mp4", "video/quicktime", "video/webm"]),
  bytes: z.number().int().min(1).max(MAX_FILE_SIZE),
}).strict();

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return jsonError("Unsupported type or file size (maximum 1 GiB)", 400);
  const { projectId, fileName, contentType, bytes } = parsed.data;
  if (!(await ownedProject(projectId, user.id))) return jsonError("Project not found", 404);

  const key = "users/" + user.id + "/projects/" + projectId + "/media/" +
    randomUUID() + "." + allowed[contentType];
  const asset = await prisma.mediaAsset.create({
    data: { projectId, objectKey: key, fileName, contentType, bytes: BigInt(bytes) },
  });
  try {
    const uploadId = await initiateUpload(key, contentType);
    const session = await prisma.uploadSession.create({
      data: { assetId: asset.id, uploadId, partSize: PART_SIZE },
    });
    return NextResponse.json({
      upload: { id: session.id, assetId: asset.id, partSize: PART_SIZE, parts: Math.ceil(bytes / PART_SIZE) },
    }, { status: 201 });
  } catch {
    await prisma.mediaAsset.update({ where: { id: asset.id }, data: { status: "FAILED" } });
    return jsonError("Unable to start object storage upload", 502);
  }
}
