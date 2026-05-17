import { proxyJson } from "../backend";

export async function GET() {
  return proxyJson("/memory");
}

export async function POST(request: Request) {
  return proxyJson("/memory", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
}
