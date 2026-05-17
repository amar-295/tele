const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";
const UI_API_KEY = process.env.UI_API_KEY;

export function backendUrl(path: string) {
  return `${FASTAPI_URL.replace(/\/$/, "")}${path}`;
}

export function apiHeaders(extra?: HeadersInit) {
  if (!UI_API_KEY) {
    throw new Error("UI_API_KEY is not configured");
  }

  return {
    "X-API-Key": UI_API_KEY,
    ...extra,
  };
}

export async function proxyJson(path: string, init?: RequestInit) {
  const response = await fetch(backendUrl(path), {
    ...init,
    headers: apiHeaders(init?.headers),
    cache: "no-store",
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
    },
  });
}
