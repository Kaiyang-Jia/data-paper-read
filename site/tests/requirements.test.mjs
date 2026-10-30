import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const registry = JSON.parse(await readFile(new URL('../public/data/requirements-framework.json', import.meta.url), 'utf8'));
const source = (await readFile(new URL('../app/lib/requirements.ts', import.meta.url), 'utf8')).replace("import registry from '../../public/data/requirements-framework.json';", `const registry = ${JSON.stringify(registry)};`);
const js = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}}).outputText;
const {emptyDraft, buildRequirements, offlineAssessment} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
test('no default domain or constraints', () => { assert.deepEqual(buildRequirements(emptyDraft()), {version: '1.0', domains: [], conditions: []}); });
test('multiple domains preserve threshold and preference', () => {
  const draft = emptyDraft(); draft.domains = ['medicine', 'computing'];
  draft.values = {'medicine.participants': {text: '100', priority: 'required'}, 'computing.language': {text: '中文，英文', priority: 'preferred'}};
  const req = buildRequirements(draft); assert.equal(req.conditions.length, 2); assert.equal(req.conditions[0].value, 100); assert.equal(req.conditions[1].priority, 'preferred');
  draft.domains = ['computing']; assert.equal(buildRequirements(draft).conditions.length, 1);
});
test('invalid numbers, reversed years and empty comma lists rejected', () => {
  for (const [domain, field, text] of [['medicine', 'medicine.participants', '-1'], ['social', 'social.coverage_years', '2022-2010'], ['computing', 'computing.language', '，，']]) {
    const draft = emptyDraft(); draft.domains = [domain]; draft.values[field] = {text, priority: 'required'}; assert.throws(() => buildRequirements(draft));
  }
});
test('custom names cannot collide and require values', () => {
  const draft = emptyDraft(); draft.custom = [{label: '复核', text: '双人', priority: 'required'}, {label: '复核', text: '双人', priority: 'required'}]; assert.throws(() => buildRequirements(draft));
  draft.custom = [{label: '复核', text: '', priority: 'required'}]; assert.throws(() => buildRequirements(draft));
});
test('offline results never assert verified matches', () => {
  const draft = emptyDraft(); draft.values.format = {text: 'CSV', priority: 'required'};
  const result = offlineAssessment(buildRequirements(draft)); assert.equal(result.status, 'unknown'); assert.equal(result.conditions[0].label, '文件格式');
});
