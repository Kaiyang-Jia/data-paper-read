"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { keyOf, type Article } from "./catalog";
import { useLibrary } from "./use-library";
import { emptyLibrary, localEntries, mergeConflict, normalizeLibrary, type Draft, type Library, type User } from "./account-model";

type Phase = "loading" | "guest" | "member" | "unavailable" | "expired";
type Pending = { owner: number; notes: Record<string, Draft>; favorites: Record<string, { article: Article; favorite: boolean }> };
class AccountError extends Error {
  constructor(message: string, public status: number, public detail: { note?: Draft; code?: string } = {}) { super(message); }
}
const AUTH_EVENT = "datapaper-account-change";
type SessionResponse = { user: User | null; csrfToken: string; message: string };
type Responses = {
  session: SessionResponse; login: SessionResponse; register: SessionResponse; logout: SessionResponse;
  password: SessionResponse; profile: { user: User }; library: Library;
  note: { text: string; revision: number }; favorite: { ok: boolean }; read: { ok: boolean };
  "history/clear": { ok: boolean }; import: { favorites: number; notes: number; conflicts: number };
};

export function useAccountLibrary(articles: Article[], notify: (message: string) => void) {
  const guest = useLibrary(notify);
  const [phase, setPhase] = useState<Phase>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [remote, setRemote] = useState<Library>(emptyLibrary);
  const [pending, setPending] = useState<Pending>({ owner: 0, notes: {}, favorites: {} });
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [importing, setImporting] = useState(false);
  const userRef = useRef<User | null>(null), csrf = useRef("");
  const epoch = useRef(0), writing = useRef(false), mounted = useRef(true);
  const pendingRef = useRef(pending), remoteRef = useRef(remote);
  const draftsByOwner = useRef(new Map<number, Pending>());

  const updatePending = useCallback((next: Pending) => {
    pendingRef.current = next;
    if (next.owner) draftsByOwner.current.set(next.owner, next);
    setPending(next);
  }, []);
  const updateRemote = useCallback((next: Library) => { remoteRef.current = next; setRemote(next); }, []);
  const announce = () => { try { localStorage.setItem(AUTH_EVENT, crypto.randomUUID()); } catch { /* Session remains usable without storage. */ } };

  const api = useCallback(async <P extends keyof Responses>(path: P, body?: object, owner?: number): Promise<Responses[P]> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (body) headers["X-CSRF-Token"] = csrf.current;
    if (owner) headers["X-Account-User"] = String(owner);
    const response = await fetch(`/api/account/${path}`, { method: body ? "POST" : "GET", headers,
      body: body ? JSON.stringify(body) : undefined, cache: "no-store", signal: AbortSignal.timeout(18000) })
      .catch(() => { throw new Error("账户连接中断，未同步的修改仍保留在当前页面，请重试或导出草稿。"); });
    const value = await response.json().catch(() => { throw new Error("账户服务暂时不可用，请重新连接。"); }) as { message?: string; note?: Draft; code?: string };
    if (!response.ok) {
      if ((response.status === 401 || value.code === "account_changed" || value.code === "csrf_expired") && owner) {
        epoch.current++;
        userRef.current = null; setUser(null); updateRemote(emptyLibrary()); setPhase("expired");
      }
      throw new AccountError(value.message || "操作失败，请稍后重试。", response.status, value);
    }
    return value as Responses[P];
  }, [updateRemote]);

  const loadSession = useCallback(async () => {
    let version = epoch.current;
    try {
      const response = await api("session");
      if (!mounted.current || version !== epoch.current) return;
      csrf.current = response.csrfToken;
      const next: User | null = response.user;
      if (next?.id !== userRef.current?.id) {
        epoch.current++;
        updateRemote(emptyLibrary());
      }
      const current = epoch.current;
      version = current;
      userRef.current = next; setUser(next);
      if (!next) {
        setPhase(pendingRef.current.owner && (Object.keys(pendingRef.current.notes).length || Object.keys(pendingRef.current.favorites).length) ? "expired" : "guest");
        return;
      }
      setPhase("loading");
      const library = normalizeLibrary(await api("library", undefined, next.id));
      if (!mounted.current || current !== epoch.current) return;
      updateRemote(library);
      updatePending(draftsByOwner.current.get(next.id) || { owner: next.id, notes: {}, favorites: {} });
      setError("");
      setPhase("member");
    } catch (e) {
      if (mounted.current && version === epoch.current) {
        setError(e instanceof Error ? e.message : "账户服务暂时不可用。");
        setPhase("unavailable");
      }
    }
  }, [api, updatePending, updateRemote]);

  useEffect(() => {
    mounted.current = true;
    const initial = setTimeout(() => void loadSession(), 0);
    const changed = (e: StorageEvent) => { if (e.key === AUTH_EVENT) { epoch.current++; userRef.current = null; setUser(null); updateRemote(emptyLibrary()); setPhase("loading"); void loadSession(); } };
    // Focus checks identities and fetches changes made on another device/tab.
    const focus = () => { if (!writing.current) void loadSession(); };
    window.addEventListener("storage", changed);
    window.addEventListener("focus", focus);
    return () => { clearTimeout(initial); mounted.current = false; window.removeEventListener("storage", changed); window.removeEventListener("focus", focus); };
  }, [loadSession, updateRemote]);

  const hasPending = Object.keys(pending.notes).length > 0 || Object.keys(pending.favorites).length > 0;
  useEffect(() => {
    const beforeLeave = (e: BeforeUnloadEvent) => {
      const unsaved = [...draftsByOwner.current.values()].some(p => Object.keys(p.notes).length || Object.keys(p.favorites).length);
      if (unsaved) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", beforeLeave);
    return () => window.removeEventListener("beforeunload", beforeLeave);
  }, [hasPending]);

  const flush = useCallback(async () => {
    const owner = userRef.current?.id;
    if (!owner || writing.current || pendingRef.current.owner !== owner) return;
    const version = epoch.current;
    writing.current = true; setSyncing(true);
    try {
      for (const [key, item] of Object.entries(pendingRef.current.favorites)) {
        await api("favorite", item, owner);
        if (version !== epoch.current) return;
        const favorites = remoteRef.current.favorites.filter(a => keyOf(a) !== key);
        if (item.favorite) favorites.unshift(item.article);
        updateRemote({ ...remoteRef.current, favorites });
        if (pendingRef.current.favorites[key] === item) {
          const next = { ...pendingRef.current.favorites }; delete next[key];
          updatePending({ ...pendingRef.current, favorites: next });
        }
      }
      for (const [key, draft] of Object.entries(pendingRef.current.notes)) {
        if (draft.conflict) continue;
        try {
          const saved = await api("note", { article: draft.article, text: draft.text, revision: draft.revision }, owner);
          if (version !== epoch.current) return;
          updateRemote({ ...remoteRef.current, notes: { ...remoteRef.current.notes, [key]: { ...saved, article: draft.article } } });
          const next = { ...pendingRef.current.notes };
          if (next[key] === draft) delete next[key];
          else if (next[key]) next[key] = { ...next[key], revision: saved.revision };
          updatePending({ ...pendingRef.current, notes: next });
        } catch (e) {
          if (version !== epoch.current) return;
          if (e instanceof AccountError && e.status === 409 && e.detail.note) {
            updatePending({ ...pendingRef.current, notes: { ...pendingRef.current.notes,
              [key]: { ...pendingRef.current.notes[key], conflict: e.detail.note } } });
          } else throw e;
        }
      }
    } catch (e) {
      if (version === epoch.current) setError(e instanceof Error ? e.message : "同步失败，草稿保留在当前页面。");
    } finally { writing.current = false; if (mounted.current) setSyncing(false); }
  }, [api, updatePending, updateRemote]);

  useEffect(() => {
    const work = Object.keys(pending.favorites).length || Object.values(pending.notes).some(n => !n.conflict);
    if (phase !== "member" || error || !work || syncing) return;
    const timer = setTimeout(() => void flush(), 800);
    return () => clearTimeout(timer);
  }, [phase, pending, error, hasPending, syncing, flush]);

  async function authenticate(mode: "login" | "register", fields: object) {
    const fresh = await api("session");
    csrf.current = fresh.csrfToken;
    const value = await api(mode, fields);
    csrf.current = value.csrfToken;
    epoch.current++; setError("");
    await loadSession(); announce();
  }

  async function logout(discard = false) {
    if (hasPending && !discard) throw new Error("还有未同步的修改，请先同步或导出草稿。");
    const value = await api("logout", {});
    csrf.current = value.csrfToken;
    epoch.current++; if (userRef.current) draftsByOwner.current.delete(userRef.current.id);
    userRef.current = null; setUser(null); updateRemote(emptyLibrary());
    updatePending({ owner: 0, notes: {}, favorites: {} });
    setError(""); setPhase("guest"); announce();
  }

  const editable = phase === "guest" || phase === "member";
  function toggleFavorite(article: Article) {
    if (!editable) { notify("请先恢复账户连接或选择游客模式。"); return; }
    const key = keyOf(article);
    if (!user) { guest.setSaved(saved => saved.includes(key) ? saved.filter(k => k !== key) : [...saved, key]); return; }
    const saved = pendingRef.current.favorites[key]?.favorite ?? remoteRef.current.favorites.some(a => keyOf(a) === key);
    updatePending({ ...pendingRef.current, favorites: { ...pendingRef.current.favorites, [key]: { article, favorite: !saved } } });
    setError("");
  }

  function editNote(article: Article, text: string) {
    if (!editable) return;
    const key = keyOf(article);
    if (!user) { guest.setNotes(n => ({ ...n, [key]: text })); return; }
    const previous = pendingRef.current.notes[key];
    updatePending({ ...pendingRef.current, notes: { ...pendingRef.current.notes, [key]: { article, text,
      revision: previous?.revision ?? remoteRef.current.notes[key]?.revision ?? 0, conflict: previous?.conflict } } });
    setError("");
  }

  function resolveNote(key: string, merge: boolean) {
    const draft = pendingRef.current.notes[key];
    if (!draft?.conflict) return;
    if (merge && mergeConflict(draft.conflict.text, draft.text).length > 20000) {
      notify("合并后超过 20000 字，请先精简上方本地笔记，再合并保存。"); return;
    }
    const next = { ...pendingRef.current.notes };
    if (merge) next[key] = { ...draft, text: mergeConflict(draft.conflict.text, draft.text), revision: draft.conflict.revision, conflict: undefined };
    else {
      updateRemote({ ...remoteRef.current, notes: { ...remoteRef.current.notes, [key]: { ...draft.conflict, article: draft.article } } });
      delete next[key];
    }
    updatePending({ ...pendingRef.current, notes: next }); setError("");
  }

  async function profile(fields: object) {
    if (!userRef.current) return;
    const version = epoch.current;
    const response = await api("profile", fields, userRef.current.id);
    if (version !== epoch.current) return;
    userRef.current = response.user; setUser(response.user);
  }
  async function changePassword(fields: object) {
    if (hasPending) throw new Error("请先保存未同步的修改，再更改密码。");
    if (!userRef.current) return;
    const response = await api("password", fields, userRef.current.id);
    csrf.current = response.csrfToken;
    epoch.current++; draftsByOwner.current.clear(); userRef.current = null; setUser(null);
    updateRemote(emptyLibrary()); updatePending({ owner: 0, notes: {}, favorites: {} }); setPhase("guest"); announce();
    notify(response.message);
  }

  async function recordRead(article: Article) {
    const owner = userRef.current?.id, version = epoch.current;
    if (!owner || phase !== "member") return;
    try {
      await api("read", { article }, owner);
      if (version === epoch.current) updateRemote({ ...remoteRef.current, history: [article, ...remoteRef.current.history.filter(a => keyOf(a) !== keyOf(article))].slice(0, 100) });
    } catch { /* Reading never blocks access to an article. */ }
  }
  async function clearHistory() {
    const owner = userRef.current?.id, version = epoch.current;
    if (!owner) return;
    await api("history/clear", {}, owner);
    if (version === epoch.current) updateRemote({ ...remoteRef.current, history: [] });
  }

  const entries = localEntries(guest, articles);
  async function importLocal() {
    const owner = userRef.current?.id, version = epoch.current;
    if (!owner || importing) return;
    if (hasPending) throw new Error("请先同步当前修改，再导入本地文献。");
    setImporting(true);
    const total = { favorites: 0, notes: 0, conflicts: 0 };
    try {
      // Per-entry idempotency also allows safe resumption after partial failure.
      for (const entry of entries) {
        const result = await api("import", { entries: [entry] }, owner);
        if (version !== epoch.current) return;
        total.favorites += result.favorites; total.notes += result.notes; total.conflicts += result.conflicts;
      }
      const library = normalizeLibrary(await api("library", undefined, owner));
      if (version !== epoch.current) return;
      updateRemote(library);
      notify(`导入完成：新增 ${total.favorites} 篇收藏，处理 ${total.notes} 条笔记${total.conflicts ? `，${total.conflicts} 条冲突已保留两个版本` : ""}。本地原件已保留。`);
    } finally { setImporting(false); }
  }

  function exportDrafts() {
    const content = JSON.stringify(pendingRef.current, null, 2);
    const href = URL.createObjectURL(new Blob([content], { type: "application/json" }));
    const a = document.createElement("a"); a.href = href; a.download = "DataPaper-未同步草稿.json"; a.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }

  const activePending: Pick<Pending, "notes" | "favorites"> = user && pending.owner === user.id ? pending : { notes: {}, favorites: {} };
  const saved = user ? new Set(remote.favorites.map(keyOf)) : new Set(phase === "guest" ? guest.saved : []);
  const noteTexts: Record<string, string> = user ? Object.fromEntries(Object.entries(remote.notes).map(([k, n]) => [k, n.text])) : phase === "guest" ? { ...guest.notes } : {};
  for (const [key, value] of Object.entries(activePending.favorites)) { if (value.favorite) saved.add(key); else saved.delete(key); }
  for (const [key, value] of Object.entries(activePending.notes)) noteTexts[key] = value.text;
  return { user, phase, error, syncing, importing, hasPending, editable, saved: [...saved], notes: noteTexts,
    favorites: user ? remote.favorites : [], history: user ? remote.history : [],
    drafts: activePending.notes, entries, remoteNotes: remote.notes,
    toggleFavorite, editNote, resolveNote, authenticate, logout, profile, changePassword, recordRead, clearHistory, importLocal, exportDrafts,
    retry: () => { setError(""); if (phase === "member") void flush(); else void loadSession(); },
    useGuest: () => { epoch.current++; userRef.current = null; setUser(null); updateRemote(emptyLibrary()); setPhase("guest"); setError(""); },
  };
}

export type AccountLibrary = ReturnType<typeof useAccountLibrary>;
