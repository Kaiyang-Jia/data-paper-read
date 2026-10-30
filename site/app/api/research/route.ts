import { backendUrl } from "../../lib/backend";
export async function POST(request: Request) {
  const backend = backendUrl();
  if (!backend)
    return Response.json(
      { message: "当前未连接 AI 后端，请使用快照匹配。" },
      { status: 503 },
    );
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin)
    return Response.json({ message: "请求来源不匹配" }, { status: 403 });
  try {
    const raw = await request.text();
    if (raw.length > 16000)
      return Response.json({ message: "请求过长" }, { status: 413 });
    const payload = JSON.parse(raw);
    if (
      typeof payload?.message !== "string" ||
      payload.message.trim().length < 4 ||
      payload.message.length > 1000
    )
      return Response.json(
        { message: "请用 4–1000 字描述研究需求" },
        { status: 400 },
      );
    const response = await fetch(`${backend}/api/research-assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: payload.message, requirements: payload.requirements }),
      signal: AbortSignal.timeout(45000),
    });
    return Response.json(await response.json(), {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { message: "AI 服务暂不可用，可继续使用快照匹配。" },
      { status: 503 },
    );
  }
}
