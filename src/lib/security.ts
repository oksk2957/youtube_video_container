import { NextResponse } from "next/server";

export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const expected = process.env.APP_URL
    ? new URL(process.env.APP_URL).origin
    : new URL(request.url).origin;
  return origin === expected;
}

export function jsonError(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}
