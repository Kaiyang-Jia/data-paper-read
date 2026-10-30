import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
const source = await readFile(
  new URL("../app/lib/catalog.ts", import.meta.url),
  "utf8",
);
const js = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const { normalizeCatalog, sourceUrl, matchScore, localResearch, exportBrief } =
  await import(
    `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`
  );
const paper = {
  title: "Urban temperature observations in China",
  doi: "10.1234/test",
  abstract: "Satellite observations of urban temperature.",
  publishDate: "2026-01-01",
};
test("deduplicates articles and tolerates missing tags", () => {
  assert.equal(
    normalizeCatalog({ articles: [paper, paper], summary: {} }).articles.length,
    1,
  );
});
test("Chinese concepts find English records without claiming AI", () => {
  assert.ok(matchScore(paper, "中国城市热岛") > 0);
  const result = localResearch([paper], "中国城市热岛");
  assert.equal(result.mode, "offline");
  assert.equal(result.recommendations.length, 1);
  assert.ok(paper.abstract.includes(result.recommendations[0].evidence.text));
});
test("irrelevant query has no manufactured result", () => {
  assert.equal(localResearch([paper], "zzxyxyzzz").recommendations.length, 0);
});
test("unsafe URLs never become source links", () => {
  assert.equal(sourceUrl({ title: "x", url: "javascript:alert(1)" }), "");
  assert.equal(sourceUrl(paper), "https://doi.org/10.1234/test");
});
test("export preserves abstract, note and DOI without placeholders", () => {
  const text = exportBrief([paper], "城市研究", {
    "10.1234/test": "核实空间分辨率",
  });
  for (const value of [
    paper.title,
    paper.doi,
    paper.abstract,
    "城市研究",
    "核实空间分辨率",
  ])
    assert.ok(text.includes(value));
});
test("actual snapshot is usable and has unique DOI records", async () => {
  const data = normalizeCatalog(
    JSON.parse(
      await readFile(
        new URL("../public/data/articles.json", import.meta.url),
        "utf8",
      ),
    ),
  );
  assert.ok(data.articles.length > 1000);
  assert.equal(
    new Set(data.articles.map((a) => a.doi)).size,
    data.articles.length,
  );
});
test('export keeps requested conditions and omits unknown assessment', () => {
  const req = {version: '1.0', domains: ['medicine'], conditions: [{field: 'medicine.participants', value: 100, priority: 'required'}]};
  const article = {...paper, requirementsAssessment: {status: 'unknown', note: '待核实', conditions: [{...req.conditions[0], label: '最低参与者人数', status: 'unknown', reason: '尚无核验属性'}]}};
  const text = exportBrief([article], '临床数据', {}, req, {'medicine.participants': '最低参与者人数（人）'});
  assert.ok(text.includes('最低参与者人数（人）（必须）：100'));
  assert.ok(!text.includes('未知；尚无核验属性'));
  assert.ok(!text.includes('未提供'));
});

 test('catalog hides title-only introductions and processing notices', () => {
  const article = {...paper, interpretationCn: '仅依据标题：城市数据。当前缺少摘要，具体内容需查看原文核实。', journal: '未提供'};
  const result = normalizeCatalog({articles: [article], summary: {}}).articles[0];
  assert.equal(result.interpretationCn, '');
  assert.equal(result.journal, '');
  assert.equal(result.abstract, paper.abstract);
 });
