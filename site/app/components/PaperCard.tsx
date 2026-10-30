import { Article, keyOf, contentText, sourceUrl } from "../lib/catalog";
import { Icon } from "./Icon";
import { AttributeAssessment } from './AttributeAssessment';

export function PaperCard({
  a,
  index,
  compare,
  saved,
  setSelected,
  toggleCompare,
  toggleSaved,
  research,
}: {
  a: Article;
  index: number;
  compare: string[];
  saved: string[];
  setSelected: (a: Article) => void;
  toggleCompare: (a: Article) => void;
  toggleSaved: (a: Article) => void;
  research: boolean;
}) {
  const key = keyOf(a);
  return (
    <article className={`paper${compare.includes(key) ? " is-compared" : ""}`} key={key}>
      <span className="paper-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
      <div className="paper-body">
      <div className="paper-top">
        {a.journal && <span className="journal">{a.journal}</span>}
        {a.publishDate && <time>{a.publishDate}</time>}
      </div>
      <button className="paper-title" onClick={() => setSelected(a)}>
        {a.titleCn || a.title}
      </button>
      {a.authors && <p className="paper-authors" title={a.authors}>{a.authors}</p>}
      {(a.interpretationCn || a.abstract) && <p className="paper-abstract">{a.interpretationCn || a.abstract}</p>}
      {a.evidence && (
        <details className="evidence">
          <summary><span>
            原文摘录
          </span></summary>
          <p>{a.evidence.text}</p>
        </details>
      )}
      {research && contentText(a.reason) && <p className="reason">{contentText(a.reason)}</p>}
      <AttributeAssessment assessment={a.requirementsAssessment} compact />
      <div className="paper-bottom">
        <div className="tags">
          <span className="type-label">Article</span>
          {a.Subject && <span>{a.Subject}</span>}
        </div>
        <div className="paper-actions">
          {sourceUrl(a) && <a href={sourceUrl(a)} target="_blank" rel="noreferrer" aria-label={`查看原文：${a.title}`}>原文 <Icon name="link" /></a>}
          <button
            aria-pressed={compare.includes(key)}
            onClick={() => toggleCompare(a)}
          >
            {compare.includes(key) ? "已选比较" : "＋ 比较"}
          </button>
          <button
            className={saved.includes(key) ? "is-saved" : ""}
            aria-label={`${saved.includes(key) ? "移出" : "加入"}研究清单：${a.title}`}
            aria-pressed={saved.includes(key)}
            onClick={() => toggleSaved(a)}
          >
            <Icon name={saved.includes(key) ? "check" : "bookmark"} />
            <span>{saved.includes(key) ? "已加入" : "加入清单"}</span>
          </button>
        </div>
      </div>
      </div>
    </article>
  );
}
