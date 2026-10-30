import { backendUrl } from "../../lib/backend";
export async function GET() {
  const backend = backendUrl();
  if (!backend)
    return Response.json({ message: "当前使用论文快照" }, { status: 503 });
  try {
    const response = await fetch(`${backend}/api/catalog`, {
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    if (!response.ok) throw new Error("backend unavailable");
    return Response.json(await response.json(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ message: "实时论文服务暂不可用" }, { status: 503 });
  }
}
