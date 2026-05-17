import { apiHeaders, backendUrl } from "../backend";

export async function POST(request: Request) {
  const body = await request.text();
  const response = await fetch(backendUrl("/chat/stream"), {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body,
    cache: "no-store",
  });

  if (!response.body) {
    return Response.json(
      { error: "Backend did not return a stream" },
      { status: 502 },
    );
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream; charset=utf-8",
      "X-Accel-Buffering": "no",
    },
  });
}
