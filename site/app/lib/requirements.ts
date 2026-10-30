import registry from '../../public/data/requirements-framework.json';

export type Field = { id: string; label: string; type: 'set' | 'number' | 'range'; operator: string; placeholder: string; unit?: string };
export const framework = registry as { version: string; common: Field[]; domains: {id: string; label: string; fields: Field[]}[] };
export type Condition = {field: string; priority: 'required' | 'preferred'; value: string[] | number | number[]};
export type Requirements = {version: string; domains: string[]; conditions: Condition[]};
export type Draft = {domains: string[]; values: Record<string, {text: string; priority: 'required' | 'preferred'}>; custom: {label: string; text: string; priority: 'required' | 'preferred'}[]};
export type Assessment = {status: 'match' | 'mismatch' | 'unknown' | 'not-assessed'; note: string; conditions: (Condition & {label: string; unit?: string; status: string; reason: string; actual?: unknown; source?: {url: string; quote: string; checkedAt: string; status: string}})[]};
export type DataProfile = {datasetId: string; name?: string; version?: string; paperDois?: string[]; attributes: Record<string, {value: unknown; unit?: string; status: string; checkedAt?: string; source?: {url: string; quote: string}}>};
export const emptyDraft = (): Draft => ({domains: [], values: {}, custom: []});
export function activeFields(draft: Draft): Field[] {
  return [...framework.common, ...framework.domains.filter(d => draft.domains.includes(d.id)).flatMap(d => d.fields)];
}
export function buildRequirements(draft: Draft): Requirements {
  const conditions: Condition[] = [];
  for (const field of activeFields(draft)) {
    const entry = draft.values[field.id];
    if (!entry?.text.trim()) continue;
    let value: Condition['value'];
    if (field.type === 'number') {
      value = Number(entry.text);
      if (!Number.isFinite(value) || value < 0) throw new Error(`${field.label}应填写非负数字（${field.unit}）`);
    } else if (field.type === 'range') {
      const parts = entry.text.trim().match(/^(\d{4})\s*[-–—至到]\s*(\d{4})$/);
      if (!parts || Number(parts[1]) < 1 || Number(parts[1]) > Number(parts[2])) throw new Error(`${field.label}请按起止年份填写，例如2010-2022`);
      value = [Number(parts[1]), Number(parts[2])];
    } else {
      value = entry.text.split(/[,，;；\n]+/).map(v => v.trim()).filter(Boolean);
      if (!value.length || value.length > 12) throw new Error(`${field.label}需填写1至12个值`);
    }
    conditions.push({field: field.id, priority: entry.priority, value});
  }
  for (const entry of draft.custom) {
    if (!entry.label.trim() && !entry.text.trim()) continue;
    if (!entry.label.trim() || !entry.text.trim()) throw new Error('自定义条件需要同时填写属性名和条件值');
    const value = entry.text.split(/[,，;；\n]+/).map(v => v.trim()).filter(Boolean);
    if (!value.length || value.length > 12) throw new Error('自定义条件需填写1至12个值');
    conditions.push({field: `custom:${entry.label.trim()}`, priority: entry.priority, value});
  }
  if (conditions.length > 32) throw new Error('最多提交32项条件');
  if (new Set(conditions.map(c => c.field)).size !== conditions.length) throw new Error('自定义属性名称不能重复');
  return {version: framework.version, domains: draft.domains, conditions};
}
export function offlineAssessment(requirements: Requirements): Assessment {
  const fields = activeFields({domains: requirements.domains, values: {}, custom: []});
  return {status: requirements.conditions.some(c => c.priority === 'required') ? 'unknown' : 'not-assessed', note: '离线模式只提供线索，条件需由后端基于核验属性判断。', conditions: requirements.conditions.map(c => ({...c, label: fields.find(f => f.id === c.field)?.label || c.field.slice(7), status: 'unknown', reason: '离线模式未执行属性核验'}))};
}
