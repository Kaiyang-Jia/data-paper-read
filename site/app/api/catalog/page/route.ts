import { backendUrl } from "../../../lib/backend";
export async function GET(request: Request) {
  const backend = backendUrl();
  if (!backend) return Response.json({message: "论文服务暂不可用"}, {status: 503});
  try {
    const response = await fetch(`${backend}/api/catalog/page${new URL(request.url).search}`, {cache: "no-store", signal: AbortSignal.timeout(15000)});
    return Response.json(await response.json(), {status: response.status, headers: {"Cache-Control": "no-store"}});
  } catch { return Response.json({message: "论文服务暂不可用"}, {status: 503}); }
}
