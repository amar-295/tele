import { proxyJson } from "../backend";

export async function POST() {
  return proxyJson("/clear", { method: "POST" });
}
