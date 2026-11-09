import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { isSameOrigin, jsonError } from "@/lib/security";
import { encryptApiKey, validateProviderUrl } from "@/lib/ai-provider";

export const runtime = "nodejs";
const settingsSchema = z.object({
  baseUrl: z.string().min(1).max(500),
  chatModel: z.string().trim().min(1).max(120),
  transcriptionModel: z.string().trim().min(1).max(120),
  apiKey: z.string().max(4096).optional(),
}).strict();

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const config = await prisma.aiProviderConfig.findUnique({
    where: { userId: user.id },
    select: { baseUrl: true, chatModel: true, transcriptionModel: true },
  });
  return NextResponse.json({ config: config ? { ...config, hasApiKey: true } : null },
    { headers: { "Cache-Control": "no-store" } });
}

export async function PUT(request: Request) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const data = await request.json().catch(() => null);
  const parsed = settingsSchema.safeParse(data);
  if (!parsed.success) return jsonError("Invalid provider settings", 400);
  let url: string;
  try { url = validateProviderUrl(parsed.data.baseUrl); }
  catch (e) { return jsonError(e instanceof Error ? e.message : "Invalid URL", 400); }
  const current = await prisma.aiProviderConfig.findUnique({ where: { userId: user.id } });
  const apiKey = parsed.data.apiKey?.trim();
  if (!current && !apiKey) return jsonError("Initial setup requires an API key", 400);
  let encryptedApiKey: string;
  try { encryptedApiKey = apiKey ? encryptApiKey(apiKey) : current!.encryptedApiKey; }
  catch { return jsonError("Encryption key is not configured on the server", 503); }

  await prisma.aiProviderConfig.upsert({
    where: { userId: user.id },
    create: {
      userId: user.id, baseUrl: url, chatModel: parsed.data.chatModel,
      transcriptionModel: parsed.data.transcriptionModel, encryptedApiKey,
    },
    update: {
      baseUrl: url, chatModel: parsed.data.chatModel,
      transcriptionModel: parsed.data.transcriptionModel, encryptedApiKey,
    },
  });
  return NextResponse.json({ ok: true });
}
