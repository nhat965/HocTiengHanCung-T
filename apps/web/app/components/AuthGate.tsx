"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

type SessionState = "loading" | "signed-out" | "signed-in" | "unavailable";

export default function AuthGate({ children }: Readonly<{ children: React.ReactNode }>) {
  const [state, setState] = useState<SessionState>("loading");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Không thể kiểm tra phiên đăng nhập.");
        const result = (await response.json()) as { authenticated: boolean };
        setState(result.authenticated ? "signed-in" : "signed-out");
      })
      .catch(() => setState("unavailable"));
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const result = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "Đăng nhập thất bại.");
      setPassword("");
      setState("signed-in");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Đăng nhập thất bại.");
    }
  }

  async function signOut() {
    await fetch("/api/session", { method: "DELETE" });
    setState("signed-out");
  }

  if (state === "loading") {
    return <main className="auth-shell" aria-live="polite">Đang kiểm tra phiên cá nhân…</main>;
  }
  if (state === "unavailable") {
    return <main className="auth-shell"><section className="auth-card"><h1>Không thể xác minh phiên</h1><p>Kiểm tra cấu hình phiên đăng nhập ở máy chủ web.</p></section></main>;
  }
  if (state === "signed-out") {
    return (
      <main className="auth-shell">
        <form className="auth-card" onSubmit={signIn}>
          <p className="eyebrow">Không gian học riêng tư</p>
          <h1>Góc học tiếng Hàn</h1>
          <p>Dữ liệu học chỉ khả dụng sau khi đăng nhập vào máy chủ cá nhân.</p>
          <label htmlFor="web-password">Mật khẩu</label>
          <input
            id="web-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button type="submit">Đăng nhập</button>
        </form>
      </main>
    );
  }

  return (
    <>
      <div className="session-bar">
        <Link href="/books">Thư viện</Link>
        <Link href="/review">Duyệt dữ liệu</Link>
        <span>Không gian học riêng tư</span>
        <button type="button" onClick={signOut}>Đăng xuất</button>
      </div>
      {children}
    </>
  );
}
