import { keyOf, type Article } from "./catalog";

export type User = { id: number; email: string; displayName: string; researchField: string };
export type Note = { text: string; revision: number; article: Article };
export type Library = { favorites: Article[]; notes: Record<string, Note>; history: Article[] };
export type Draft = { article: Article; text: string; revision: number; conflict?: { text: string; revision: number } };
export type Guest = { saved: string[]; notes: Record<string, string> };
export const emptyLibrary = (): Library => ({ favorites: [], notes: {}, history: [] });

/** The database uses prefixed keys; the existing browser uses unprefixed keys.
 * Resolve through the stored article rather than guessing or lowercasing URLs.
 */
export function normalizeLibrary(value: Library): Library {
  return { ...value, notes: Object.fromEntries(Object.values(value.notes).map(n => [keyOf(n.article), n])) };
}

export function localEntries(guest: Guest, articles: Article[]) {
  const byKey = new Map(articles.map(a => [keyOf(a), a]));
  return [...new Set([...guest.saved, ...Object.keys(guest.notes).filter(k => guest.notes[k])])].sort().map(key => {
    // Preserve references whose articles are no longer in the current catalog.
    const article = byKey.get(key) || (/^10\.\d{4,9}\//.test(key)
      ? { title: key, doi: key } : /^https?:\/\//.test(key) ? { title: key, url: key } : { title: key });
    return { article, favorite: guest.saved.includes(key), note: guest.notes[key] || "" };
  });
}

export function mergeConflict(server: string, local: string) {
  if (server === local || !local) return server;
  return server ? `${server}\n\n—— 本地编辑版本 ——\n${local}` : local;
}
