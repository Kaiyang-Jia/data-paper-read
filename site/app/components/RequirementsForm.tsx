import { Draft, Field, framework } from '../lib/requirements';

export function RequirementsForm({draft, onChange}: {draft: Draft; onChange: (draft: Draft) => void}) {
  function fieldRow(field: Field) {
    const entry = draft.values[field.id] || {text: '', priority: 'required' as const};
    return <div className="condition-row" key={field.id}>
      <label htmlFor={`condition-${field.id}`}>{field.label}{field.unit ? `（${field.unit}）` : ''}</label>
      <input id={`condition-${field.id}`} value={entry.text} maxLength={120} placeholder={field.placeholder}
        onChange={e => onChange({...draft, values: {...draft.values, [field.id]: {...entry, text: e.target.value}}})} />
      <select aria-label={`${field.label}优先级`} value={entry.priority}
        onChange={e => onChange({...draft, values: {...draft.values, [field.id]: {...entry, priority: e.target.value as 'required' | 'preferred'}}})}>
        <option value="required">必须满足</option><option value="preferred">偏好</option>
      </select>
    </div>;
  }
  return <section className="requirements-editor" aria-label="研究需求条件">
    <h3>补充需求条件（可选）</h3>
    <p>多值用逗号分隔；变量与内容需全部具备，类型、格式等可填写可接受的备选值。</p>
    <details><summary>通用属性：对象、内容、类型与获取方式</summary>
      <div className="condition-fields">{framework.common.map(fieldRow)}</div>
    </details>
    <fieldset><legend>选择学科模板（可多选，也可不选）</legend>
      <div className="domain-options">{framework.domains.map(domain => <label key={domain.id}>
        <input type="checkbox" checked={draft.domains.includes(domain.id)} onChange={e => onChange({...draft, domains: e.target.checked ? [...draft.domains, domain.id] : draft.domains.filter(d => d !== domain.id)})} />{domain.label}
      </label>)}</div>
    </fieldset>
    {framework.domains.filter(domain => draft.domains.includes(domain.id)).map(domain => <details open key={domain.id}>
      <summary>{domain.label}属性</summary><div className="condition-fields">{domain.fields.map(fieldRow)}</div>
    </details>)}
    {draft.custom.map((entry, index) => <div className="condition-row custom-condition" key={index}>
      <input aria-label={`自定义属性名${index + 1}`} maxLength={60} placeholder="属性名，如：测量精度" value={entry.label} onChange={e => onChange({...draft, custom: draft.custom.map((c, i) => i === index ? {...c, label: e.target.value} : c)})} />
      <input aria-label={`自定义条件值${index + 1}`} maxLength={120} placeholder="需满足的值（逗号分隔）" value={entry.text} onChange={e => onChange({...draft, custom: draft.custom.map((c, i) => i === index ? {...c, text: e.target.value} : c)})} />
      <select aria-label={`自定义条件优先级${index + 1}`} value={entry.priority} onChange={e => onChange({...draft, custom: draft.custom.map((c, i) => i === index ? {...c, priority: e.target.value as 'required' | 'preferred'} : c)})}><option value="required">必须满足</option><option value="preferred">偏好</option></select>
      <button type="button" onClick={() => onChange({...draft, custom: draft.custom.filter((_, i) => i !== index)})}>移除</button>
    </div>)}
    <button type="button" className="secondary" disabled={draft.custom.length >= 5} onClick={() => onChange({...draft, custom: [...draft.custom, {label: '', text: '', priority: 'required'}]})}>＋ 自定义属性</button>

  </section>;
}
