import { backendUrl } from "../../../lib/backend";

const routes = new Set(["session", "register", "login", "logout", "profile", "password", "library", "favorite", "note", "read", "history/clear", "import"]);

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!routes.has(route)) return Response.json({ message: "接口不存在" }, { status: 404 });
  const read = route === "session" || route === "library";
  if ((request.method === "GET") !== read) return new Response(null, { status: 405 });
  const url = new URL(request.url);
  if (request.method !== "GET" && request.headers.get("origin") !== url.origin)
    return Response.json({ message: "请求来源不匹配，请刷新后重试。" }, { status: 403 });
  const backend = backendUrl();
  if (!backend) return Response.json({ message: "当前未连接账户服务，可继续使用游客文献库。" }, { status: 503 });
  try {
    const body = request.method === "GET" ? undefined : await request.text();
    if (body && new TextEncoder().encode(body).length > 64000)
      return Response.json({ message: "提交内容过长，请分批导入。" }, { status: 413 });
    // Only the Flask session cookie goes to the configured account backend.
    const cookie = (request.headers.get("cookie") || "").split(";").map(v => v.trim()).find(v => v.startsWith("session="));
    const headers = new Headers({ "Content-Type": "application/json" });
    if (cookie) headers.set("Cookie", cookie);
    const csrf = request.headers.get("x-csrf-token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
    const owner = request.headers.get("x-account-user");
    if (owner) headers.set("X-Account-User", owner);
    const response = await fetch(`${backend}/api/account/${route}`, {
      method: request.method, headers, body, redirect: "manual", cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    const output = new Headers({ "Content-Type": "application/json", "Cache-Control": "no-store, private", "Vary": "Cookie" });
    const sessionCookie = response.headers.get("set-cookie");
    if (sessionCookie) output.set("Set-Cookie", url.protocol === "https:" && !/;\s*secure/i.test(sessionCookie) ? `${sessionCookie}; Secure` : sessionCookie);
    return new Response(await response.text(), { status: response.status, headers: output });
  } catch {
    return Response.json({ message: "账户服务暂时不可用，请稍后重试。" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export const GET = proxy;
export const POST = proxy;
