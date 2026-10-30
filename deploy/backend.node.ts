/** Node.js self-hosted backend binding; copy to site/app/lib/backend.ts. */
export function backendUrl(): string | undefined {
  return process.env.DATAPAPER_API_URL;
}
