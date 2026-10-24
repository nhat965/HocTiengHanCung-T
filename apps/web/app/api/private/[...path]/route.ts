import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "node:crypto";

const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000/api/v1";
const sessionCookieName = "learning_session";

function hasValidSession(request: NextRequest): boolean {
  const secret = process.env.PRIVATE_WEB_SESSION_SECRET;
  const value = request.cookies.get(sessionCookieName)?.value;
  if (!secret || !value) return false;
  const [expiresAt, signature, extra] = value.split(".");
  if (!expiresAt || !signature || extra !== undefined || Number(expiresAt) <= Date.now()) return false;
  const expected = createHmac("sha256", secret).update(expiresAt).digest();
  const supplied = Buffer.from(signature, "base64url");
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const token = process.env.PRIVATE_API_TOKEN;
  const target = new URL(`${apiBase}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));
  const isHealth = path.length === 1 && path[0] === "health";
  if (!isHealth && !hasValidSession(request)) {
    return NextResponse.json({ detail: "Sign in to access private learning data" }, { status: 401 });
  }
  if (!token && !isHealth) {
    return NextResponse.json({ detail: "Private API token is not configured on the web server" }, { status: 503 });
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(request.headers.get("content-type") ? { "Content-Type": request.headers.get("content-type")! } : {}),
      },
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });
    return new NextResponse(await response.arrayBuffer(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Private API is unavailable" }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
