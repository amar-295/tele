import { proxyJson } from "../../backend";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ keyword: string }> },
) {
  const { keyword } = await params;
  return proxyJson(`/memory/${encodeURIComponent(keyword)}`, {
    method: "DELETE",
  });
}
