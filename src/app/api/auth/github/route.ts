import { NextResponse } from "next/server";
import { OAUTH_STATE_COOKIE, cookieOptions, newToken } from "@/lib/auth";

export const runtime = "nodejs";

export async function GET() {
  const clientId = process.env.GITHUB_CLIENT_ID;
  const appUrl = process.env.APP_URL;
  if (!clientId || !appUrl) {
    return NextResponse.json({ error: "GitHub OAuth environment is not configured." }, { status: 503 });
  }

  const state = newToken();
  const url = new URL("https://github.com/login/oauth/authorize");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", new URL("/api/auth/github/callback", appUrl).toString());
  url.searchParams.set("scope", "read:user");
  url.searchParams.set("state", state);

  const response = NextResponse.redirect(url);
  response.cookies.set(OAUTH_STATE_COOKIE, state, { ...cookieOptions, maxAge: 600 });
  return response;
}
