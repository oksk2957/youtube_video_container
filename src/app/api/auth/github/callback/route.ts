import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import {
  OAUTH_STATE_COOKIE,
  SESSION_COOKIE,
  cookieOptions,
  hashToken,
  newToken,
} from "@/lib/auth";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const appUrl = process.env.APP_URL;
  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;
  if (!appUrl || !clientId || !clientSecret) {
    return NextResponse.json({ error: "OAuth is not configured" }, { status: 503 });
  }
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const expectedState = request.cookies.get(OAUTH_STATE_COOKIE)?.value;
  if (!code || !state || !expectedState || state !== expectedState) {
    return NextResponse.json({ error: "Invalid OAuth state" }, { status: 400 });
  }

  const tokenResponse = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: new URL("/api/auth/github/callback", appUrl).toString(),
    }),
    cache: "no-store",
  });
  if (!tokenResponse.ok) return NextResponse.json({ error: "OAuth exchange failed" }, { status: 502 });
  const tokenData = (await tokenResponse.json()) as { access_token?: string };
  if (!tokenData.access_token) return NextResponse.json({ error: "OAuth token missing" }, { status: 401 });

  const profileResponse = await fetch("https://api.github.com/user", {
    headers: {
      Authorization: "Bearer " + tokenData.access_token,
      Accept: "application/vnd.github+json",
      "User-Agent": "video-studio",
    },
    cache: "no-store",
  });
  if (!profileResponse.ok) return NextResponse.json({ error: "GitHub profile unavailable" }, { status: 502 });
  const profile = (await profileResponse.json()) as { id?: number; login?: string; avatar_url?: string };
  if (!profile.id || !profile.login) {
    return NextResponse.json({ error: "GitHub profile invalid" }, { status: 502 });
  }
  const user = await prisma.user.upsert({
    where: { githubId: String(profile.id) },
    create: { githubId: String(profile.id), login: profile.login, avatarUrl: profile.avatar_url },
    update: { login: profile.login, avatarUrl: profile.avatar_url },
  });
  const token = newToken();
  await prisma.session.create({
    data: {
      userId: user.id,
      tokenHash: hashToken(token),
      expiresAt: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000),
    },
  });
  const response = NextResponse.redirect(new URL("/", appUrl));
  response.cookies.set(OAUTH_STATE_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  response.cookies.set(SESSION_COOKIE, token, { ...cookieOptions, maxAge: 14 * 24 * 60 * 60 });
  return response;
}
