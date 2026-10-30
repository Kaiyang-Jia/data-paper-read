"use client";
import { useEffect, useRef, useState } from "react";
import type { AccountLibrary } from "../lib/use-account-library";
import { keyOf } from "../lib/catalog";

export function AccountPanel({ account, open, close, initialMode = "profile" }: { account: AccountLibrary; open: boolean; close: () => void; initialMode?: "profile" | "import" }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<"login" | "register" | "profile" | "password" | "import">(initialMode);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [discard, setDiscard] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [importComplete, setImportComplete] = useState(false);
  useEffect(() => {
    if (open) dialog.current?.showModal(); else dialog.current?.close();
  }, [open]);
  const activeMode = account.user ? (["profile", "password", "import"].includes(mode) ? mode : "profile") : mode === "register" ? "register" : "login";
  function select(next: typeof mode) { setMode(next); setError(""); setMessage(""); setDiscard(false); }
  async function perform(work: () => Promise<void>, success = "") {
    setBusy(true); setError(""); setMessage("");
    try { await work(); setMessage(success); } catch (e) { setError(e instanceof Error ? e.message : "操作失败，请稍后重试。"); }
    finally { setBusy(false); }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    if (activeMode === "login" || activeMode === "register") {
      await perform(async () => { await account.authenticate(activeMode, fields); close(); });
    } else if (activeMode === "profile") {
      await perform(() => account.profile(fields), "个人资料已保存。");
    } else if (activeMode === "password") {
      await perform(async () => { await account.changePassword(fields); setMode("login"); }, "密码已修改，请使用新密码登录。");
    }
  }
  const conflicts = account.entries.filter(e => e.note && account.remoteNotes[keyOf(e.article)]?.text && account.remoteNotes[keyOf(e.article)].text !== e.note).length;
  return <dialog ref={dialog} className="account-dialog" aria-labelledby="account-title" onCancel={e => { if (busy || account.importing) e.preventDefault(); else close(); }}>
    <div className="dialog-toolbar"><span>DataPaper 账户</span><button className="dialog-close" aria-label="关闭账户面板" disabled={busy || account.importing} onClick={close}>×</button></div>
    <div className="account-content">
      <h2 id="account-title">{({ login: "登录", register: "创建账号", profile: "个人资料", password: "修改密码", import: "导入本地文献" })[activeMode]}</h2>
      {account.user ? <>
        <p className="account-email">{account.user.email}</p>
        <nav className="account-tabs" aria-label="账户设置">
          <button disabled={busy || account.importing} aria-current={activeMode === "profile" ? "page" : undefined} onClick={() => select("profile")}>个人资料</button>
          <button disabled={busy || account.importing} aria-current={activeMode === "password" ? "page" : undefined} onClick={() => select("password")}>修改密码</button>
          <button disabled={busy || account.importing} aria-current={activeMode === "import" ? "page" : undefined} onClick={() => select("import")}>本地文献导入</button>
        </nav>
      </> : <p className="account-description">登录后，收藏、笔记和阅读记录将保存到你的账号。</p>}
      {error && <p className="account-error" role="alert">{error}</p>}
      {message && <p className="account-message" role="status">{message}</p>}
      {account.phase === "unavailable" && <div className="account-error"><p>{account.error}</p><button className="secondary" onClick={account.retry}>重新连接</button></div>}
      {activeMode === "import" ? <div className="import-review">
        <p>当前浏览器有 <strong>{account.entries.filter(e => e.favorite).length}</strong> 篇收藏、<strong>{account.entries.filter(e => e.note).length}</strong> 条笔记。将导入到 <strong>{account.user?.email}</strong>。</p>
        {!!conflicts && <p>{conflicts} 条笔记与账号中的版本不同，导入后将保留两个版本，供你整理。</p>}
        <p>请确认这些内容属于你。原本地记录会保留；重复导入同一条内容不会重复添加。</p>
        <ul className="import-list">{account.entries.slice(0, 8).map(e => <li key={keyOf(e.article)}>{e.article.titleCn || e.article.title}{e.note && <span> · 含笔记</span>}</li>)}</ul>
        {account.entries.length > 8 && <p>另有 {account.entries.length - 8} 条。</p>}
        <button className="primary" disabled={busy || account.importing || !account.entries.length} onClick={() => void perform(async () => { await account.importLocal(); setImportComplete(true); }, "导入完成，已保留本地原件。")}>{account.importing ? "正在导入，请保持页面打开…" : importComplete ? "再次核对并导入" : "确认导入到此账号"}</button>
      </div> : <form key={`${activeMode}-${account.user?.id || "guest"}`} className="account-form" onSubmit={submit}>
        {(activeMode === "login" || activeMode === "register") && <label>邮箱<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>}
        {(activeMode === "register" || activeMode === "profile") && <label>昵称<input name="displayName" autoComplete="nickname" minLength={2} maxLength={100} required defaultValue={account.user?.displayName || ""} /></label>}
        {activeMode === "profile" && <label>研究方向（选填）<textarea name="researchField" maxLength={500} defaultValue={account.user?.researchField || ""} placeholder="例如：遥感、城市气候、土地利用" /></label>}
        {activeMode === "password" && <label>当前密码<input name="currentPassword" type="password" autoComplete="current-password" required maxLength={128} /></label>}
        {activeMode !== "profile" && <label>{activeMode === "password" ? "新密码" : "密码"}<input name="password" type="password" autoComplete={activeMode === "login" ? "current-password" : "new-password"} required minLength={8} maxLength={128} placeholder="8–128 位" /></label>}
        {(activeMode === "register" || activeMode === "password") && <label>确认密码<input name="confirmPassword" type="password" autoComplete="new-password" required minLength={8} maxLength={128} /></label>}
        {activeMode === "password" && <p className="account-description">修改后所有设备需重新登录。请先保存未同步的笔记。</p>}
        <button className="primary" disabled={busy || account.phase === "loading" || account.phase === "unavailable"}>{busy ? "正在处理…" : activeMode === "register" ? "注册并登录" : activeMode === "login" ? "登录" : "保存更改"}</button>
      </form>}
      {!account.user && <button className="account-switch" disabled={busy} onClick={() => select(activeMode === "login" ? "register" : "login")}>{activeMode === "login" ? "没有账号？创建账号" : "已有账号？返回登录"}</button>}
      {account.user && <div className="account-bottom">
        <button className="secondary" disabled={busy || account.importing} onClick={() => setConfirmClear(!confirmClear)}>清空阅读记录</button>
        <button className="secondary" disabled={busy || account.importing || account.syncing} onClick={() => account.hasPending ? setDiscard(true) : void perform(async () => { await account.logout(); close(); })}>退出登录</button>
        {confirmClear && <div className="inline-confirm"><p>清空账号中的最近阅读记录？收藏和笔记会保留。</p><button className="secondary" disabled={busy} onClick={() => void perform(async () => { await account.clearHistory(); setConfirmClear(false); }, "阅读记录已清空。")}>确认清空</button><button onClick={() => setConfirmClear(false)}>取消</button></div>}
        {discard && <div className="inline-confirm"><p>还有未同步的修改。你可以先导出草稿，或返回页面继续同步。</p><button className="secondary" onClick={account.exportDrafts}>导出未同步草稿</button><button className="secondary" disabled={busy} onClick={() => void perform(async () => { await account.logout(true); close(); })}>放弃未同步修改并退出</button></div>}
      </div>}
    </div>
  </dialog>;
}
