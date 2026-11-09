import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth";
import { ownedAsset } from "@/lib/projects";
import { getReadUrl } from "@/lib/storage";
import { jsonError } from "@/lib/security";

export const runtime = "nodejs";
type Params = { params: Promise<{ assetId: string }> };

export async function GET(_: Request, { params }: Params) {
  const user = await getCurrentUser();
  if (!user) return jsonError("Login required", 401);
  const { assetId } = await params;
  const asset = await ownedAsset(assetId, user.id);
  if (!asset || asset.status !== "READY") return jsonError("Asset not found", 404);
  const url = await getReadUrl(asset.objectKey);
  return NextResponse.json({ url }, { headers: { "Cache-Control": "no-store" } });
}
