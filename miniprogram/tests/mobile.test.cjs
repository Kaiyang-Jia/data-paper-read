const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const storage = new Map();
let failSave = false;
let network;
global.getApp = () => ({ globalData: {} });
global.wx = {
  getStorageSync: key => storage.get(key),
  setStorageSync: (key, value) => { if (failSave) throw Error('full'); storage.set(key, structuredClone(value)); },
  showToast() {}, removeStorageSync: key => storage.delete(key),
  request: options => network(options),
  navigateTo: options => { global.openedPath = options.url; }
};
const library = require('../utils/library');
const articles = require('../utils/articles');
function loadPage(file) {
  let definition;
  const filename = path.resolve(__dirname, '..', file);
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    Page: value => { definition = value; }, wx: global.wx,
    require: require('node:module').createRequire(filename)
  });
  definition.data = structuredClone(definition.data);
  definition.setData = function(value) { Object.assign(this.data, value); };
  return definition;
}

test('favorites and later persist independently; failed writes cannot lose existing data', () => {
  storage.clear();
  const a = articles.present({ id: '10.1/a', title: 'A' });
  library.toggle(a, 'favorites'); library.toggle(a, 'later');
  assert.equal(library.decorate(a).favorite, true);
  library.toggle(a, 'later');
  assert.equal(library.read().later.length, 0);
  assert.equal(library.read().favorites.length, 1);
  failSave = true;
  assert.throws(() => library.toggle(a, 'favorites'));
  failSave = false;
  assert.equal(library.read().favorites.length, 1);
});

test('shared detail opens cold without sender storage and retains encoded DOI', async () => {
  storage.clear();
  const a = articles.present({ id: '10.1234/a/b', title: 'Original', titleCn: '中文标题', doi: '10.1234/a/b' });
  const share = articles.share(a);
  const id = new URL('https://test.invalid' + share.path).searchParams.get('id');
  assert.equal(id, a.id);
  network = o => { assert.equal(o.data.id, id); o.success({ statusCode: 200, data: { article: a } }); };
  const page = loadPage('pages/detail/detail.js');
  page.onLoad({ id });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.data.article.displayTitle, '中文标题');
  assert.equal(page.onShareAppMessage().path, share.path);
});

test('title-only introduction is suppressed and API errors reach caller', async () => {
  assert.equal(articles.present({ title: 'A', interpretationCn: 'invented details', chineseProcessing: { basis: 'title' } }).displayIntro, '');
  const { request } = require('../utils/request');
  network = o => o.success({ statusCode: 404, data: { message: 'missing' } });
  await assert.rejects(request('/api/miniprogram/article'), /missing/);
});

test('search ignores an older response that arrives after a newer search', async () => {
  const pending = [];
  network = o => pending.push(o);
  const page = loadPage('pages/search/search.js');
  page.data.keyword = 'old'; const old = page.search();
  page.data.keyword = 'new'; const newer = page.search();
  const result = title => ({ statusCode: 200, data: { articles: [{ id: title, title }], total: 1, hasMore: false } });
  pending[1].success(result('new')); await newer;
  pending[0].success(result('old')); await old;
  assert.equal(page.data.items[0].title, 'new');
});

test('offline daily feed keeps its original date and reports it as cached', async () => {
  storage.clear();
  network = o => o.success({ statusCode: 200, data: { date: '2026-10-02', articles: [{ id: 'a', title: 'A' }], summary: { totalCount: 1 } } });
  const page = loadPage('pages/index/index.js');
  await page.loadDaily();
  network = o => o.fail({ errMsg: 'offline' });
  await page.loadDaily();
  assert.equal(page.data.date, '2026-10-02');
  assert.equal(page.data.offline, true);
  assert.equal(page.data.items.length, 1);
});
