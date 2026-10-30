"use client";
import { useMemo, useSyncExternalStore } from "react";

const KEY = "datapaper-workspace-v1";
const EVENT = "datapaper-library-change";
let sessionFallback = "{}";
let sessionOnly = false;
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT, callback);
  };
}
function snapshot() {
  try {
    return sessionOnly ? sessionFallback : localStorage.getItem(KEY) || "{}";
  } catch {
    return sessionFallback;
  }
}

/** Browser-local state with SSR-safe hydration and cross-tab synchronization. */
export function useLibrary(notify: (message: string) => void) {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "{}");
  const value = useMemo(() => {
    try {
      const parsed = JSON.parse(raw);
      return {
        saved: Array.isArray(parsed?.saved)
          ? (parsed.saved.filter(
              (s: unknown) => typeof s === "string",
            ) as string[])
          : [],
        notes:
          parsed?.notes && typeof parsed.notes === "object"
            ? (Object.fromEntries(
                Object.entries(parsed.notes).filter(
                  ([, n]) => typeof n === "string",
                ),
              ) as Record<string, string>)
            : {},
      };
    } catch {
      return { saved: [] as string[], notes: {} as Record<string, string> };
    }
  }, [raw]);
  function write(next: typeof value) {
    sessionFallback = JSON.stringify(next);
    try {
      localStorage.setItem(KEY, sessionFallback);
    } catch {
      sessionOnly = true;
      notify("无法写入浏览器存储，本次笔记暂存于页面，请及时导出。");
    }
    window.dispatchEvent(new Event(EVENT));
  }
  return {
    ...value,
    setSaved: (update: (saved: string[]) => string[]) =>
      write({ ...value, saved: update(value.saved) }),
    setNotes: (
      update: (notes: Record<string, string>) => Record<string, string>,
    ) => write({ ...value, notes: update(value.notes) }),
  };
}
