/** Optional starter binding. No D1 database is required by the research workspace. */
declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    DATAPAPER_API_URL?: string;
  }
}
