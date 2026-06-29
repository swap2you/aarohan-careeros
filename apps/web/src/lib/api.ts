export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

let sessionExpiredHandler: (() => void) | null = null;

export function registerSessionExpiredHandler(handler: () => void) {
  sessionExpiredHandler = handler;
}

export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (response.status === 401 && response.headers.get("X-Aarohan-Auth") === "session-required") {
    sessionExpiredHandler?.();
  }
  return response;
}

export async function authJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(path, init);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail || `API error ${response.status}`);
  }
  return response.json() as Promise<T>;
}
