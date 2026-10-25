import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE, GET as getSession, POST } from "../app/api/session/route";
import { GET as proxyGet } from "../app/api/private/[...path]/route";

const password = "test-private-password";
const sessionSecret = "test-session-secret-with-more-than-32-characters";

function request(path: string, init?: ConstructorParameters<typeof NextRequest>[1]): NextRequest {
  return new NextRequest(`http://localhost${path}`, init);
}

async function signInCookie(): Promise<{ value: string; header: string }> {
  const response = await POST(request("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  }));
  const cookie = response.headers.get("set-cookie")?.match(/learning_session=([^;]+)/)?.[1];
  const header = response.headers.get("set-cookie");
  if (!cookie || !header) throw new Error("Session cookie was not set");
  return { value: cookie, header };
}

describe("private web session", () => {
  beforeEach(() => {
    process.env.PRIVATE_WEB_PASSWORD = password;
    process.env.PRIVATE_WEB_SESSION_SECRET = sessionSecret;
    process.env.PRIVATE_API_TOKEN = "server-only-api-token";
    process.env.API_BASE_URL = "http://api.example.test/api/v1";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects invalid passwords and grants a signed HttpOnly session", async () => {
    const rejected = await POST(request("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: "incorrect" }),
    }));
    expect(rejected.status).toBe(401);

    const cookie = await signInCookie();
    const accepted = await getSession(request("/api/session", {
      headers: { Cookie: `learning_session=${cookie.value}` },
    }));
    expect(accepted.status).toBe(200);
    expect(await accepted.json()).toEqual({ authenticated: true });

    const newSession = await signInCookie();
    expect(newSession.header).toContain("HttpOnly");
    expect(newSession.value).not.toContain(password);
  });

  it("blocks private proxy requests without a session and forwards authenticated requests", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const context = { params: Promise.resolve({ path: ["textbooks"] }) };
    const denied = await proxyGet(request("/api/private/textbooks"), context);
    expect(denied.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();

    const cookie = await signInCookie();
    const accepted = await proxyGet(request("/api/private/textbooks", {
      headers: { Cookie: `learning_session=${cookie.value}` },
    }), context);
    expect(accepted.status).toBe(200);
    expect(upstream).toHaveBeenCalledOnce();
    const [, options] = upstream.mock.calls[0];
    expect(options?.headers).toMatchObject({
      Authorization: "Bearer server-only-api-token",
    });
  });


  it("rejects malformed signed cookies without contacting the upstream API", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
    const context = { params: Promise.resolve({ path: ["textbooks"] }) };
    for (const cookie of ["9999999999999.!invalid", "not-a-timestamp.abc", "9999999999999.abc.def", "9999999999999.%"]) {
      const response = await proxyGet(request("/api/private/textbooks", {
        headers: { Cookie: `learning_session=${cookie}` },
      }), context);
      expect(response.status).toBe(401);
    }
    expect(upstream).not.toHaveBeenCalled();
  });

  it("rejects invalid proxy path segments before constructing the upstream URL", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
    const cookie = await signInCookie();
    for (const segments of [["..", "health"], ["https:", "example.com"], [""], ["textbooks", "1?admin=true"]]) {
      const response = await proxyGet(request("/api/private/textbooks", {
        headers: { Cookie: `learning_session=${cookie.value}` },
      }), { params: Promise.resolve({ path: segments }) });
      expect(response.status).toBe(400);
    }
    expect(upstream).not.toHaveBeenCalled();
  });

  it("clears the session cookie on sign-out", async () => {
    const response = await DELETE();
    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });
});
