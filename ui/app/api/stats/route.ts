import { proxyJson } from "../backend";

export async function GET() {
  return proxyJson("/stats");
}
