export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/private/${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "Không thể tải dữ liệu");
  }
  return response.json() as Promise<T>;
}
