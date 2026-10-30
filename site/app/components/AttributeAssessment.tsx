import { contentText } from '../lib/catalog';
import { Assessment, DataProfile, framework } from '../lib/requirements';

function display(value: unknown): string {
  return Array.isArray(value) ? value.map(display).filter(Boolean).join('，') : typeof value === 'number' ? String(value) : typeof value === 'string' ? contentText(value) : '';
}
function safeUrl(value?: string) {
  try { const url = new URL(value || ''); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; }
}
export function AttributeAssessment({assessment, compact = false}: {assessment?: Assessment; compact?: boolean}) {
  const conditions = assessment?.conditions.filter(item => ['match', 'mismatch'].includes(item.status) && display(item.actual)) || [];
  if (!conditions.length) return null;
  return <div className="attribute-assessment">
    <details open={!compact}><summary>条件对照 · {conditions.length}</summary>
      {conditions.map(item => <div className={`condition-result ${item.status}`} key={item.field}>
        <b>{item.label} · {item.status === 'match' ? '符合' : '不符合'}</b>
        <p>需求：{display(item.value)} {item.unit || ''}；文献：{display(item.actual)} {item.unit || ''}</p>
        {item.source?.quote && <blockquote>{item.source.quote}
          {safeUrl(item.source.url) && <a href={safeUrl(item.source.url)} target="_blank" rel="noreferrer"> 来源 ↗</a>}
        </blockquote>}
      </div>)}
    </details>
  </div>;
}
export function DatasetAttributes({profile}: {profile?: DataProfile | null}) {
  const fields = [...framework.common, ...framework.domains.flatMap(d => d.fields)];
  const entries = Object.entries(profile?.attributes || {}).filter(([, fact]) => ['reviewed', 'file-checked', 'source-backed'].includes(fact.status) && display(fact.value));
  if (!entries.length) return null;
  return <section className="dataset-attributes"><h3>数据属性</h3>
    {(profile?.name || profile?.version) && <p>{[profile.name, profile.version].filter(Boolean).join(' · ')}</p>}
    <dl>{entries.map(([key, fact]) => <div className="condition-result" key={key}>
      <dt>{fields.find(f => f.id === key)?.label || key.replace(/^custom:/, '')}</dt>
      <dd>{display(fact.value)} {fact.unit || ''}</dd>
      {fact.source?.quote && <blockquote>{fact.source.quote} {safeUrl(fact.source.url) && <a href={safeUrl(fact.source.url)} target="_blank" rel="noreferrer">来源 ↗</a>}</blockquote>}
    </div>)}</dl>
  </section>;
}
