import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const compile = (source) => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText).toString('base64');
const catalog = compile(await readFile(new URL('../app/lib/catalog.ts', import.meta.url), 'utf8'));
const source = (await readFile(new URL('../app/lib/account-model.ts', import.meta.url), 'utf8')).replace('"./catalog"', JSON.stringify(catalog));
const { normalizeLibrary, localEntries, mergeConflict } = await import(compile(source));
const paper = { title: 'Original title', titleCn: '中文题目', doi: '10.1234/TEST' };

test('database key and existing browser key resolve to the same note', () => {
  const result = normalizeLibrary({ favorites: [paper], notes: { 'doi:10.1234/test': { article: paper, text: 'saved', revision: 2 } }, history: [] });
  assert.equal(result.notes['10.1234/test'].text, 'saved');
  assert.equal(result.notes['10.1234/test'].revision, 2);
});
test('local migration deduplicates while retaining standalone notes and removed papers', () => {
  const guest = { saved: ['10.1234/test', '10.1234/test', '10.5678/removed'], notes: { '10.1234/test': 'note', 'unlisted title': 'standalone' } };
  const snapshot = JSON.stringify(guest);
  const entries = localEntries(guest, [paper]);
  assert.equal(entries.length, 3);
  assert.equal(entries.find(e => e.article.doi === paper.doi).note, 'note');
  assert.ok(entries.some(e => e.article.doi === '10.5678/removed'));
  assert.ok(entries.some(e => e.note === 'standalone' && !e.favorite));
  assert.equal(JSON.stringify(guest), snapshot);
});
test('conflict merge keeps both versions and does not repeat identical text', () => {
  assert.equal(mergeConflict('same', 'same'), 'same');
  const result = mergeConflict('server', 'local');
  assert.ok(result.includes('server') && result.includes('local'));
  assert.equal(mergeConflict('', 'local'), 'local');
});
