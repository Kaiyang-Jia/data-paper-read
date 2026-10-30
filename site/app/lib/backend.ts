import { env } from "cloudflare:workers";

/** Set by the operator, never from a browser-controlled request parameter. */
export function backendUrl(): string | undefined {
  return (
    (env as unknown as { DATAPAPER_API_URL?: string }).DATAPAPER_API_URL ||
    process.env.DATAPAPER_API_URL
  );
}
