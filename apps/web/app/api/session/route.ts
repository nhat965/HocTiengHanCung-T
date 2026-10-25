import { createHmac, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const cookieName = "learning_session";
const sessionDurationSeconds = 60 * 60 * 24;

function sessionSignature(expiresAt: string, secret: string): Buffer {
  return createHmac("sha256", secret).update(expiresAt).digest();
}

function validSession(request: NextRequest): boolean {
  const secret = process.env.PRIVATE_WEB_SESSION_SECRET;
  const value = request.cookies.get(cookieName)?.value;
  if (!secret || !value) return false;
  const [expiresAt, signature, extra] = value.split(".");
  if (!expiresAt || !signature || extra !== undefined || Number(expiresAt) <= Date.now()) return false;
  const expected = sessionSignature(expiresAt, secret);
  let supplied: Buffer;
  try {
    supplied = Buffer.from(signature, "base64url");
  } catch {
    return false;
  }
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

export async function GET(request: NextRequest) {
  return NextResponse.json({ authenticated: validSession(request) });
}

export async function POST(request: NextRequest) {
  const configuredPassword = process.env.PRIVATE_WEB_PASSWORD;
  const secret = process.env.PRIVATE_WEB_SESSION_SECRET;
  if (!configuredPassword || !secret || secret.length < 32) {
    return NextResponse.json({ detail: "Private web access is not configured" }, { status: 503 });
  }

  let submitted: unknown;
  try {
    submitted = (await request.json()).password;
  } catch {
    return NextResponse.json({ detail: "A password is required" }, { status: 400 });
  }
  if (typeof submitted !== "string" || submitted.length > 1024) {
    return NextResponse.json({ detail: "Invalid password" }, { status: 400 });
  }
  const expected = Buffer.from(configuredPassword);
  const actual = Buffer.from(submitted);
  if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) {
    return NextResponse.json({ detail: "Incorrect password" }, { status: 401 });
  }

  const expiresAt = String(Date.now() + sessionDurationSeconds * 1000);
  const session = `${expiresAt}.${sessionSignature(expiresAt, secret).toString("base64url")}`;
  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(cookieName, session, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: sessionDurationSeconds,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(cookieName, "", {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return response;
}
