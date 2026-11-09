import { createCipheriv, randomBytes } from "node:crypto";
import { isIP } from "node:net";

function cipherKey(): Buffer {
  const hex = process.env.AI_CONFIG_ENCRYPTION_KEY ?? "";
  if (!/^[0-9a-fA-F]{64}$/.test(hex)) throw new Error("AI_CONFIG_ENCRYPTION_KEY must be 64 hex characters");
  return Buffer.from(hex, "hex");
}
export function encryptApiKey(apiKey: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", cipherKey(), iv);
  const encrypted = Buffer.concat([cipher.update(apiKey, "utf8"), cipher.final()]);
  return [iv.toString("base64"), cipher.getAuthTag().toString("base64"), encrypted.toString("base64")].join(".");
}
export function validateProviderUrl(value: string): string {
  let url: URL;
  try { url = new URL(value); }
  catch { throw new Error("AI Base URL이 올바르지 않습니다."); }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("AI Base URL에는 사용자 정보·쿼리·해시를 포함하지 마세요.");
  }
  const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
  const allowed = new Set((process.env.AI_ALLOWED_HOSTS || "api.openai.com")
    .split(",").map(s => s.trim().toLowerCase()).filter(Boolean));
  if (!allowed.has(hostname)) throw new Error("허용되지 않은 도메인입니다. AI_ALLOWED_HOSTS를 확인하세요.");
  const local = hostname === "localhost" || hostname === "127.0.0.1";
  if (url.protocol !== "https:" &&
      !(local && process.env.AI_ALLOW_LOCAL_HTTP === "true" && url.protocol === "http:")) {
    throw new Error("HTTPS 주소만 허용됩니다.");
  }
  if (!local && (isIP(hostname) || hostname.endsWith(".local") || hostname.endsWith(".internal"))) {
    throw new Error("내부 서버 URL은 허용되지 않습니다.");
  }
  return url.toString().replace(/\/$/, "");
}
