import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { SESSION_COOKIE, cookieOptions, hashToken } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/security";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return jsonError("Invalid request origin", 403);
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token && /^[0-9a-f]{64}$/.test(token)) {
    await prisma.session.deleteMany({ where: { tokenHash: hashToken(token) } });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  return response;
}
