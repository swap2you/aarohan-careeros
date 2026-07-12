function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  // On the server (SSR/build) window is undefined — use the configured base.
  if (typeof window === "undefined") {
    return configured;
  }
  // In the browser, when the API is on loopback we must call it on the SAME
  // hostname the page was opened with (localhost vs 127.0.0.1). Otherwise the
  // session cookie is treated as cross-site (not sent) and CORS rejects it,
  // which produces an infinite login/redirect loop.
  try {
    const configuredUrl = new URL(configured);
    const configuredIsLoopback =
      configuredUrl.hostname === "localhost" || configuredUrl.hostname === "127.0.0.1";
    const pageIsLoopback =
      window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    if (configuredIsLoopback && pageIsLoopback) {
      const port = configuredUrl.port || "8000";
      return `${window.location.protocol}//${window.location.hostname}:${port}`;
    }
  } catch {
    // Fall through to the configured base on any parse error.
  }
  return configured;
}

export const API_BASE = resolveApiBase();

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
