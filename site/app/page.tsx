"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Article,
  Catalog,
  ResearchResult,
  exportBrief,
  keyOf,
  localResearch,
  matchScore,
  normalizeCatalog,
  presentArticle,
  sourceUrl,
} from "./lib/catalog";
import { useAccountLibrary } from "./lib/use-account-library";
import { AccountPanel } from "./components/AccountPanel";
import { Icon } from "./components/Icon";
import { RequirementsForm } from './components/RequirementsForm';
import { AttributeAssessment, DatasetAttributes } from './components/AttributeAssessment';
import { buildRequirements, emptyDraft, offlineAssessment, framework } from './lib/requirements';
import type { Requirements } from './lib/requirements';
import { PaperCard } from "./components/PaperCard";
const PAGE_SIZE = 12;
type View = "discover" | "research" | "library" | "history" | "about";
const examples = [
  "糖尿病患者的长期随访与临床测量数据",
  "小鼠单细胞基因表达与细胞类型数据",
  "中文文本分类与人工标注数据",
];
export default function Home() {
  const [data, setData] = useState<Catalog | null>(null),
    [loadError, setLoadError] = useState(""),
    [retry, setRetry] = useState(0);
  const [view, setView] = useState<View>("discover"),
    [query, setQuery] = useState(""),
    [subject, setSubject] = useState(""),
    [journal, setJournal] = useState(""),
    [sort, setSort] = useState("newest"),
    [year, setYear] = useState(""),
    [density, setDensity] = useState<"comfortable" | "compact">("comfortable"),
    [page, setPage] = useState(1);
  const [need, setNeed] = useState(""),
    [result, setResult] = useState<ResearchResult | null>(null),
    [submittedNeed, setSubmittedNeed] = useState(""),
    [busy, setBusy] = useState(false);
  const [compare, setCompare] = useState<string[]>([]);
  const [requirementDraft, setRequirementDraft] = useState(emptyDraft);
  const [submittedRequirements, setSubmittedRequirements] = useState<Requirements>();
  const [selected, setSelected] = useState<Article | null>(null),
    [comparing, setComparing] = useState(false),
    [notice, setNotice] = useState("");
  const [known, setKnown] = useState<Article[]>([]);
  const articles = useMemo(() => data?.articles || [], [data]);
  const account = useAccountLibrary(known, setNotice);
  const { saved, notes } = account;
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountTab, setAccountTab] = useState<"profile" | "import">("profile");
  const dialog = useRef<HTMLDialogElement>(null),
    trigger = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (view === "library") return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({page: String(page), size: String(PAGE_SIZE), q: query, subject, journal, year, sort});
        const response = await fetch(`/api/catalog/page?${params}`, {signal: controller.signal, cache: "no-store"});
        if (!response.ok) throw new Error();
        const payload = normalizeCatalog(await response.json());
        if (controller.signal.aborted) return;
        setData(payload);
        setKnown(old => [...new Map([...old, ...payload.articles].map(a => [keyOf(a), a])).values()]);
        setLoadError("");
      } catch {
        if (!controller.signal.aborted) setLoadError("论文库暂时无法加载，请检查连接后重试。");
      }
    }, query ? 300 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [retry, page, query, subject, journal, year, sort, view]);
  const savedKey = JSON.stringify(saved);
  useEffect(() => {
    const keys = JSON.parse(savedKey) as string[];
    if (!keys.length) return;
    const controller = new AbortController();
    (async () => {
      try {
        const responses = await Promise.all(Array.from({length: Math.ceil(keys.length / 500)}, (_, i) =>
          fetch('/api/catalog/lookup', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({keys: keys.slice(i * 500, (i + 1) * 500)}), signal: controller.signal})));
        if (responses.some(r => !r.ok)) throw new Error();
        const results = await Promise.all(responses.map(r => r.json() as Promise<{articles: Article[]}>));
        if (!controller.signal.aborted) setKnown(old => [...new Map([...old, ...results.flatMap(r => r.articles).map(presentArticle)].map(a => [keyOf(a), a])).values()]);
      } catch { if (!controller.signal.aborted) setNotice('部分收藏论文暂时无法读取，请稍后重试。'); }
    })();
    return () => controller.abort();
  }, [savedKey]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(t);
  }, [notice]);
  useEffect(() => {
    if (selected || comparing) {
      trigger.current = document.activeElement as HTMLElement;
      dialog.current?.showModal();
    } else {
      dialog.current?.close();
      trigger.current?.focus();
    }
  }, [selected, comparing]);
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      const editing = target.matches('input, textarea, select, [contenteditable="true"]');
      if (dialog.current?.open || !((event.key.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)) || (event.key === '/' && !editing))) return;
      event.preventDefault();
      setView('discover');
      requestAnimationFrame(() => document.getElementById('catalog-search')?.focus());
    }
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  const subjects = data?.summary.subjects || [];
  const journals = data?.summary.journals || [];
  const years = data?.summary.years || [];
  const subjectCounts = subjects.map(name => ({name, count: data?.summary.subjectCounts?.[name] || 0})).sort((a,b) => b.count - a.count);
  const latest = data?.summary.latestPublishDate || "";
  const library = useMemo(() => {
    const all = new Map([...account.favorites, ...known].map(a => [keyOf(a), a]));
    return saved.map(key => all.get(key)).filter((a): a is Article => !!a);
  }, [known, saved, account.favorites]);
  const comparison = known.filter(a => compare.includes(keyOf(a)));
  const filtered = useMemo(() => library.filter(a =>
      (!year || a.publishDate?.startsWith(year)) && (!subject || a.Subject === subject) &&
      (!journal || a.journal === journal) && (!query.trim() || matchScore(a, query) > 0))
    .sort((a,b) => sort === "relevance" && query ? matchScore(b,query) - matchScore(a,query) :
      sort === "oldest" ? (a.publishDate || "").localeCompare(b.publishDate || "") : (b.publishDate || "").localeCompare(a.publishDate || "")),
    [library, query, subject, journal, sort, year]);
  const total = view === "library" ? filtered.length : data?.pagination?.total || 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = view === "library" ? Math.min(page, pages) : data?.pagination?.page || 1;
  const visible = view === "library" ? filtered.slice((currentPage-1)*PAGE_SIZE, currentPage*PAGE_SIZE) : articles;
  function navigate(next: View) {
    setView(next);
    setPage(1);
    setQuery("");
    setSubject("");
    setJournal("");
    setYear("");
  }
  function toggleSaved(a: Article) {
    setKnown(old => [...new Map([...old, a].map(item => [keyOf(item), item])).values()]);
    account.toggleFavorite(a);
  }
  function openArticle(a: Article) {
    setSelected(a);
    void account.recordRead(a);
  }
  function toggleCompare(a: Article) {
    setKnown(old => [...new Map([...old, a].map(item => [keyOf(item), item])).values()]);
    const key = keyOf(a);
    if (!compare.includes(key) && compare.length >= 4) {
      setNotice("最多同时比较 4 篇论文，请先移除一篇。");
      return;
    }
    setCompare((s) =>
      s.includes(key) ? s.filter((k) => k !== key) : [...s, key],
    );
  }
  function download(items: Article[]) {
    if (!items.length) {
      setNotice("请先将候选论文加入研究清单。");
      return;
    }
    const labels = Object.fromEntries([...framework.common, ...framework.domains.flatMap(d => d.fields)].map(f => [f.id, f.label]));
    const blob = new Blob([exportBrief(items, submittedNeed || need, notes, submittedRequirements, labels)], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = "DataPaper-研究数据清单.md";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function research(event: React.FormEvent) {
    event.preventDefault();
    if (!data || busy) return;
    const text = need.trim();
    if (text.length < 4) {
      setNotice("请用至少 4 个字描述你的研究需求。");
      return;
    }
    let requirements: Requirements;
    try { requirements = buildRequirements(requirementDraft); }
    catch (error) { setNotice(error instanceof Error ? error.message : '请检查需求条件'); return; }
    function fallback() {
      const response = localResearch(known, text);
      return {...response, requirements, recommendations: response.recommendations.map(a => ({...a, requirementsAssessment: offlineAssessment(requirements)}))};
    }
    setBusy(true);
    setResult(null);
    setSubmittedNeed(text);
    setSubmittedRequirements(requirements);
    try {
      if (!data.capabilities?.assistant) {
        setResult(fallback());
        return;
      }
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, requirements }),
        signal: AbortSignal.timeout(48000),
      });
      if (!response.ok) {
        if (response.status === 400) { const error = await response.json() as {message?: string}; setNotice(typeof error.message === 'string' ? error.message : '需求条件格式不正确'); return; }
        throw new Error();
      }
      const answer = (await response.json()) as ResearchResult;
      if (!Array.isArray(answer.recommendations)) throw new Error();
      setResult({...answer, recommendations: answer.recommendations.map(presentArticle)});
    } catch {
      setResult(fallback());

    } finally {
      setBusy(false);
    }
  }
  function card(a: Article, index: number) {
    return (
      <PaperCard
        key={keyOf(a)}
        a={a}
        index={view === "research" ? index : (currentPage - 1) * PAGE_SIZE + index}
        compare={compare}
        saved={saved}
        setSelected={openArticle}
        toggleCompare={toggleCompare}
        toggleSaved={toggleSaved}
        research={view === "research"}
      />
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到内容</a>
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => navigate("discover")}
          aria-label="DataPaper 首页"
        >
          <span className="brand-icon">
            <Icon name="book" />
          </span>
          <span>
            DataPaper<small>科研文献数据库</small>
          </span>
        </button>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="工作台导航">
          {(
            [
              ["discover", "search", "文献检索"],
              ["research", "sliders", "研究检索"],
              ["library", "folder", "我的文献库"],
              ["history", "clock", "最近阅读"],
              ["about", "info", "数据库概览"],
            ] as const
          ).map(([id, icon, label]) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              aria-current={view === id ? "page" : undefined}
              onClick={() => navigate(id)}
            >
              <Icon name={icon} />
              {label}
              {id === "library" && (
                <span className="count">{library.length}</span>
              )}
            </button>
          ))}
        </nav>
        {!!library.length && <div className="sidebar-collection">
          <span className="nav-label">收藏速览</span>
          {library.slice(0, 3).map(a => <button key={keyOf(a)} onClick={() => openArticle(a)} title={a.titleCn || a.title}><Icon name="bookmark" /><span>{a.titleCn || a.title}</span></button>)}
        </div>}
        <div className="sidebar-foot">
          DataPaper · Research workspace
          <br />
          <span>Research Intelligence</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            工作台 <span className="slash">/</span>{" "}
            {
              {
                discover: "文献检索",
                research: "研究检索",
                library: "我的文献库",
                history: "最近阅读",
                about: "数据库概览",
              }[view]
            }
          </span>
          <div className="topbar-actions"><button className="search-shortcut" onClick={() => {navigate('discover'); requestAnimationFrame(() => document.getElementById('catalog-search')?.focus());}}><Icon name="search" /><span>搜索文献</span><kbd>Ctrl K</kbd></button><button className="account-trigger" onClick={() => setAccountOpen(true)}><Icon name="user" /><span>{account.user?.displayName || "登录 / 注册"}</span></button></div>
        </header>
        <main id="main-content">
          <div className="account-status" aria-live="polite">
            <span>{account.phase === "loading" ? "正在连接账户…" : account.phase === "guest" ? "游客文献库 · 仅保存在此浏览器" : account.phase === "expired" ? "登录已失效，请重新登录后继续同步" : account.phase === "unavailable" ? "账户连接暂不可用" : account.syncing ? "正在同步修改…" : account.hasPending ? "有尚未同步的修改" : "个人文献库 · 已连接账户"}</span>
            {account.error && <span className="sync-error">{account.error}</span>}
            {(account.error || account.phase === "expired") && <button onClick={account.retry}>重新连接</button>}
            {account.hasPending && account.user && <><button onClick={account.retry}>重试同步</button><button onClick={account.exportDrafts}>导出未同步草稿</button></>}
            {account.phase === "unavailable" && !account.user && <button onClick={account.useGuest}>使用游客模式</button>}
            {(account.phase === "guest" || account.phase === "expired") && <button onClick={() => setAccountOpen(true)}>登录账号</button>}
            {account.user && !!account.entries.length && <button onClick={() => {setAccountTab("import"); setAccountOpen(true);}}>导入本地文献（{account.entries.length}）</button>}
          </div>
          {view === "history" && <section className="history-section"><div className="page-intro"><h1>最近阅读</h1><p>按最近打开顺序，保留最近 100 篇。</p></div>{!account.user ? <div className="empty"><p>登录后可保存和查看阅读记录。</p><button className="primary" onClick={() => setAccountOpen(true)}>登录账号</button></div> : !account.history.length ? <div className="empty"><p>打开一篇文献详情，即可在这里继续阅读。</p></div> : <div className="catalog-section">{account.history.map((a, i) => card(articles.find(item => keyOf(item) === keyOf(a)) || a, i))}</div>}</section>}
          {view === "discover" && (
            <section className="hero">
              <div><div className="eyebrow">THE RESEARCH INDEX</div><h1>发现研究数据<span className="title-dot">.</span></h1><p>连接研究问题与数据，建立你的文献收藏。</p></div>
              {data && <div className="catalog-meta"><div><strong>{(data.summary.totalCount || 0).toLocaleString()}</strong><span>数据论文</span></div><div><strong>{journals.length.toString().padStart(2, "0")}</strong><span>来源期刊</span></div></div>}
            </section>
          )}
          {view === "research" && (
            <section className="page-intro">
              <div className="eyebrow">RESEARCH DISCOVERY</div>
              <h1>研究检索</h1>
              <p>
                按研究问题、数据对象和学科条件查找文献。
              </p>
            </section>
          )}
          {view === "library" && (
            <section className="page-intro">
              <div className="eyebrow">YOUR RESEARCH COLLECTION</div>
              <h1>我的文献库</h1>
              <p>
                管理收藏、记录笔记并导出文献。
              </p>
              <button
                className="primary"
                onClick={() => download(library)}
                disabled={!library.length}
              >
                导出研究清单（Markdown） <Icon name="arrow" />
              </button>
            </section>
          )}
          {loadError ? (
            <div className="empty" role="alert">
              <h2>暂时无法读取论文库</h2>
              <p>{loadError}</p>
              <button
                className="primary"
                onClick={() => {
                  setLoadError("");
                  setRetry((n) => n + 1);
                }}
              >
                重新加载
              </button>
            </div>
          ) : !data ? (
            <div className="loading" role="status">
              <span className="loader" />
              正在读取论文与来源信息…
            </div>
          ) : (
            <>

              {(view === "discover" || view === "library") && (
                <div className="catalog-layout">
                <section className={`catalog-section density-${density}`}>
                  <div className="section-heading">
                    <div>
                      <div className="eyebrow">
                        {view === "library" ? "COLLECTION" : "THE DATA CATALOG"}
                      </div>
                      <h2>
                        {view === "library" ? "收藏文献" : "浏览数据论文"}{" "}
                        <span>{total.toLocaleString()}</span>
                      </h2>
                    </div>
                    <div className="list-controls"><div className="density-switch" role="group" aria-label="列表密度"><button aria-label="摘要视图" title="摘要视图" aria-pressed={density === "comfortable"} onClick={() => setDensity("comfortable")}><Icon name="list" /></button><button aria-label="紧凑视图" title="紧凑视图" aria-pressed={density === "compact"} onClick={() => setDensity("compact")}><Icon name="compact" /></button></div>
                    <label className="sort-label">
                      排序
                      <select
                        value={sort}
                        onChange={(e) => {
                          setSort(e.target.value);
                          setPage(1);
                        }}
                      >
                        <option value="newest">发表日期 · 从新到旧</option>
                        <option value="oldest">发表日期 · 从旧到新</option>
                        <option value="relevance">关键词相关度</option>
                      </select>
                    </label></div>
                  </div>
                  <div className="filters">
                    <label className="search-field">
                      <Icon name="search" />
                      <input
                        id="catalog-search"
                        aria-label="搜索数据论文"
                        placeholder="搜索研究主题、变量或数据名称，中英文均可"
                        value={query}
                        onChange={(e) => {
                          setQuery(e.target.value);
                          setPage(1);
                        }}
                      />
                      {query && (
                        <button
                          aria-label="清空搜索"
                          onClick={() => {
                            setQuery("");
                            setPage(1);
                          }}
                        >
                          ×
                        </button>
                      )}
                    </label>
                    <div className="filter-selects"><Icon name="sliders" /><select
                      aria-label="学科筛选"
                      value={subject}
                      onChange={(e) => {
                        setSubject(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">全部学科</option>
                      {subjects.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                    <select
                      aria-label="期刊筛选"
                      value={journal}
                      onChange={(e) => {
                        setJournal(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">全部来源期刊</option>
                      {journals.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                    <select aria-label="发表年份" value={year} onChange={e => {setYear(e.target.value); setPage(1);}}><option value="">全部年份</option>{years.map(y => <option key={y}>{y}</option>)}</select></div>
                  </div>
                  <div className="quick-topics">
                    <span>研究主题</span>
                    {["城市", "气候", "水文", "生态", "基因"].map((q) => (
                      <button
                        key={q}
                        className={query === q ? "chosen" : ""}
                        onClick={() => {
                          setQuery(q);
                          setPage(1);
                        }}
                      >
                        {q}
                      </button>
                    ))}
                    {(query || subject || journal || year) && (
                      <button
                        onClick={() => {
                          setQuery("");
                          setSubject("");
                          setJournal("");
                          setYear("");
                          setPage(1);
                        }}
                      >
                        重置筛选
                      </button>
                    )}
                  </div>
                  <div className="results-caption" aria-live="polite"><span>{query ? `“${query}” · ` : ""}{total.toLocaleString()} 篇文献{subject ? ` · ${subject}` : ""}{year ? ` · ${year}` : ""}</span><span>{density === "compact" ? "紧凑视图" : "摘要视图"}</span></div>
                  {visible.length ? (
                    <div className="paper-grid">{visible.map(card)}</div>
                  ) : (
                    <div className="empty">
                      <Icon name="folder" />
                      <h2>
                        {view === "library" && !library.length
                          ? "你的研究清单，从一篇论文开始"
                          : "暂时没有匹配结果"}
                      </h2>
                      <p>
                        {view === "library" && !library.length
                          ? "浏览数据论文，点击“加入清单”，再进行比较和记录。"
                          : "尝试减少筛选条件，或换用更具体的英文研究词。"}
                      </p>
                      {view === "library" && !library.length && (
                        <button
                          className="primary"
                          onClick={() => navigate("discover")}
                        >
                          去发现论文
                        </button>
                      )}
                    </div>
                  )}
                  {!!total && (
                    <div className="pagination">
                      <span>
                        显示 {(currentPage - 1) * PAGE_SIZE + 1}–
                        {Math.min(currentPage * PAGE_SIZE, total)} /{" "}
                        {total} 篇
                      </span>
                      <div>
                        <button
                          disabled={currentPage === 1}
                          onClick={() => setPage(currentPage - 1)}
                        >
                          上一页
                        </button>
                        <span>
                          {currentPage} / {pages}
                        </span>
                        <button
                          disabled={currentPage === pages}
                          onClick={() => setPage(currentPage + 1)}
                        >
                          下一页
                        </button>
                      </div>
                    </div>
                  )}
                </section>
                <aside className="catalog-rail" aria-label="文献浏览导航">
                  {view === "discover" ? <>
                  <section className="rail-section"><div className="rail-heading"><h2>学科浏览</h2><span>{subjects.length} 个领域</span></div>
                    <div className="subject-list">{subjectCounts.map(({name, count}) => <button key={name} aria-pressed={subject === name} onClick={() => {setSubject(subject === name ? '' : name); setPage(1);}}><span>{name}</span><span>{count.toLocaleString()}</span></button>)}</div>
                  </section>
                  <section className="rail-section journal-section"><div className="rail-heading"><h2>来源期刊</h2></div>{journals.map((name) => <button key={name} aria-pressed={journal === name} onClick={() => {setJournal(journal === name ? '' : name); setPage(1);}}><span className="journal-monogram">{name.charAt(0)}</span><span>{name}</span><Icon name="arrow" /></button>)}</section>
                  <section className="research-entry"><span className="eyebrow">RESEARCH WORKSPACE</span><h3>从一个问题开始</h3><p>描述研究对象、变量与范围，查找相关数据论文。</p><button onClick={() => navigate('research')}>研究检索 <Icon name="arrow" /></button></section>
                  {latest && <p className="index-date">最新论文日期 <time>{latest}</time></p>}
                  </> : <section className="rail-section library-summary"><div className="rail-heading"><h2>我的收藏</h2></div><dl><dt>收藏文献</dt><dd>{library.length}</dd><dt>阅读笔记</dt><dd>{library.filter(a => notes[keyOf(a)]?.trim()).length}</dd></dl><button className="secondary" disabled={!library.length} onClick={() => download(library)}>导出文献与笔记 <Icon name="arrow" /></button></section>}
                </aside>
                </div>
              )}
              {view === "research" && (
                <section className="research-layout">
                  <div>
                    <form className="research-form" onSubmit={research}>
                      <div className="form-heading">
                        <Icon name="search" />
                        <h2>检索条件</h2>

                      </div>
                      <label htmlFor="research-need">研究需求</label>
                      <textarea
                        id="research-need"
                        value={need}
                        onChange={(e) => setNeed(e.target.value)}
                        maxLength={1000}
                        minLength={4}
                        required
                        placeholder="例如：我想比较糖尿病患者的长期健康变化，需要随访数据、临床测量和人群说明。也可以描述实验、调查、组学或机器学习任务。"
                      />
                      <RequirementsForm draft={requirementDraft} onChange={setRequirementDraft} />
                      <div className="form-footer">
                        <span>{need.length}/1000</span>
                        <button
                          className="primary"
                          disabled={busy}
                          type="submit"
                        >
                          {busy ? "正在检索…" : "寻找候选数据"}
                          <Icon name="arrow" />
                        </button>
                      </div>
                    </form>
                    {busy && (
                      <div className="loading" role="status">
                        <span className="loader" />
                        正在检索文献…
                      </div>
                    )}
                    {result && (
                      <div className="research-results" aria-live="polite">
                        <div className="result-summary">

                          <h2>
                            为这个问题找到 {result.recommendations.length}{" "}
                            条线索
                          </h2>
                          <p className="submitted-need">
                            研究需求：{submittedNeed}
                          </p>
                          {!result.recommendations.length && <p>尝试调整关键词或筛选条件。</p>}
                        </div>
                        <div className="paper-grid single">
                          {result.recommendations.map(card)}
                        </div>
                      </div>
                    )}
                  </div>
                  <aside className="research-examples"><div className="rail-heading"><h2>检索示例</h2></div><p>选择示例，再按研究方向调整。</p>{examples.map((example, i) => <button key={example} onClick={() => {setNeed(example); document.getElementById('research-need')?.focus();}}><span>0{i + 1}</span><b>{example}</b><Icon name="arrow" /></button>)}<div className="research-tip"><Icon name="book" /><p>可以同时设置多个学科条件，并区分必须条件与偏好。</p></div></aside>
                </section>
              )}
              {view === "about" && (
                <section className="about">
                  <div className="page-intro"><h1>数据库概览</h1><p>DataPaper · Research Intelligence</p></div>
                  <div className="about-grid">
                    <article><h2>文献收录</h2><dl><dt>文献数量</dt><dd>{(data.summary.totalCount || 0).toLocaleString()}</dd><dt>来源期刊</dt><dd>{journals.length}</dd>{latest && <><dt>最新发表</dt><dd>{latest}</dd></>}</dl></article>
                    <article><h2>期刊来源</h2><a href="https://www.nature.com/sdata/" target="_blank" rel="noreferrer">Scientific Data ↗</a><a href="https://essd.copernicus.org/" target="_blank" rel="noreferrer">Earth System Science Data ↗</a></article>
                    <article><h2>文献管理</h2><p>收藏文献，记录研究笔记，并导出 Markdown 清单。</p><p>收藏与笔记保存在当前浏览器。</p></article>
                  </div>
                </section>
              )}
            </>
          )}
          <footer className="footer">
            <span>
              DataPaper <b> / </b> 为研究发现数据
            </span>
            <span>Research Intelligence</span>
          </footer>
        </main>
      </div>
      {!!compare.length && (
        <div className="compare-bar">
          <span>
            <b>{compare.length}</b> 篇候选论文
          </span>
          <button onClick={() => setCompare([])}>清空</button>
          <button
            className="primary"
            disabled={compare.length < 2}
            onClick={() => setComparing(true)}
          >
            比较论文 <Icon name="arrow" />
          </button>
        </div>
      )}
      {notice && (
        <div className="toast" role="status">
          {notice}
        </div>
      )}
      <dialog
        ref={dialog}
        onCancel={() => {
          setSelected(null);
          setComparing(false);
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            setSelected(null);
            setComparing(false);
          }
        }}
        aria-labelledby="dialog-title"
      >
        <div className="dialog-toolbar"><span>{comparing ? "文献比较" : "文献详情"}</span>
          <button
            className="dialog-close"
            aria-label="关闭详情"
            onClick={() => {
              setSelected(null);
              setComparing(false);
            }}
          >
            ×
          </button>
        </div>
        <div className="dialog-content">
          {selected && (
            <>
              <div className="eyebrow">ARTICLE</div>
              <h2 id="dialog-title">{selected.titleCn || selected.title}</h2>
              {selected.titleCn && <p>{selected.title}</p>}
              <div className="detail-meta">
                {(selected.journal || selected.publishDate) && <p>{[selected.journal, selected.publishDate].filter(Boolean).join(' · ')}</p>}
                {selected.doi && <p>DOI: {selected.doi}</p>}
                {selected.authors && <p>{selected.authors}</p>}
              </div>
              <div className="detail-actions">
                {sourceUrl(selected) && (
                  <a
                    className="primary"
                    target="_blank"
                    rel="noreferrer"
                    href={sourceUrl(selected)}
                  >
                    前往原文 <Icon name="link" />
                  </a>
                )}
                <button
                  className="secondary"
                  onClick={() => toggleSaved(selected)}
                >
                  {saved.includes(keyOf(selected))
                    ? "移出研究清单"
                    : "加入研究清单"}
                </button>
                <button
                  className="secondary"
                  onClick={() => toggleCompare(selected)}
                >
                  {compare.includes(keyOf(selected)) ? "取消比较" : "加入比较"}
                </button>
              </div>
              {selected.interpretationCn && (
                <>
                  <h3>内容简介</h3>
                  <p>{selected.interpretationCn}</p>

                </>
              )}
              {selected.abstract && <><h3>摘要</h3><p className="full-abstract">{selected.abstract}</p></>}
              <DatasetAttributes profile={selected.dataProfile} />
              <AttributeAssessment assessment={selected.requirementsAssessment} />
              <label className="note-label" htmlFor="paper-note">
                我的研究笔记 <span>{account.user ? account.drafts[keyOf(selected)] ? "尚未同步" : "保存至账号" : "仅保存至此浏览器"}</span>
              </label>
              <textarea
                id="paper-note"
                maxLength={account.user ? 20000 : 5000}
                disabled={!account.editable}
                value={notes[keyOf(selected)] || ""}
                onChange={(e) =>
                  account.editNote(selected, e.target.value)
                }
                placeholder="记录研究思路、引用和阅读笔记…"
              />
              {account.error && account.user && <div className="account-error" role="alert"><p>{account.error}</p><button className="secondary" onClick={account.retry}>重试同步</button><button className="secondary" onClick={account.exportDrafts}>导出未同步草稿</button></div>}
              {account.drafts[keyOf(selected)]?.conflict && <div className="note-conflict" role="alert"><p>另一处已更新这篇笔记。你的编辑仍保留在上方，请核对服务器版本：</p><pre>{account.drafts[keyOf(selected)].conflict?.text || "（笔记已清空）"}</pre><button className="secondary" onClick={() => account.resolveNote(keyOf(selected), true)}>合并两版并保存</button><button className="secondary" onClick={() => account.resolveNote(keyOf(selected), false)}>使用服务器版本</button></div>}
              <button
                className="secondary"
                onClick={() => download([selected])}
              >
                导出这篇论文与笔记
              </button>
            </>
          )}
          {comparing && (
            <>
              <div className="eyebrow">COMPARE</div>
              <h2 id="dialog-title">文献比较</h2>

              <div className="table-scroll">
                <table style={{minWidth: 110 + comparison.length * 280}}>
                  <thead>
                    <tr>
                      <th>比较维度</th>
                      {comparison.map((a) => (
                        <th key={keyOf(a)}>{a.titleCn || a.title}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      "期刊",
                      "发表日期",
                      "学科",
                      "中文介绍",
                      "原文摘要",
                      "原文",
                    ].filter(row => comparison.some(a => ({'期刊': a.journal, '发表日期': a.publishDate, '学科': a.Subject, '中文介绍': a.interpretationCn, '原文摘要': a.abstract, '原文': sourceUrl(a)})[row])).map((row) => (
                      <tr key={row}>
                        <th>{row}</th>
                        {comparison.map((a) => (
                          <td key={keyOf(a)}>
                            {row === "期刊" ? (
                              a.journal
                            ) : row === "发表日期" ? (
                              a.publishDate
                            ) : row === "学科" ? (
                              a.Subject
                            ) : row === "中文介绍" ? (
                              a.interpretationCn
                            ) : row === "原文摘要" ? (
                              a.abstract
                            ) : row === "原文" ? (
                              sourceUrl(a) ? (
                                <a
                                  href={sourceUrl(a)}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  查看原文 ↗
                                </a>
                              ) : (
                                null
                              )
                            ) : (
                              null
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="primary" onClick={() => download(comparison)}>
                导出这些候选论文
              </button>
            </>
          )}
        </div>
      </dialog>
      <AccountPanel key={`${account.user?.id || "guest"}-${accountTab}`} account={account} open={accountOpen} initialMode={accountTab} close={() => {setAccountOpen(false); setAccountTab("profile");}} />
    </div>
  );
}
