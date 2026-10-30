const KEY = 'datapaper-mobile-library-v2';
const keyOf = a => String(a.id || a.doi || a.url || a.title || '').trim().toLowerCase();
function read() {
  const value = wx.getStorageSync(KEY) || {};
  return { favorites: Array.isArray(value.favorites) ? value.favorites : [], later: Array.isArray(value.later) ? value.later : [] };
}
function decorate(article) {
  const library = read();
  const key = keyOf(article);
  return { ...article, _key: key, favorite: library.favorites.some(a => keyOf(a) === key), later: library.later.some(a => keyOf(a) === key) };
}
function toggle(article, kind) {
  const library = read();
  const key = keyOf(article);
  if (!key) throw new Error('缺少论文标识');
  const selected = !library[kind].some(a => keyOf(a) === key);
  library[kind] = library[kind].filter(a => keyOf(a) !== key);
  if (selected) library[kind].unshift({ ...article, savedAt: new Date().toISOString() });
  wx.setStorageSync(KEY, library);
  return selected;
}
module.exports = { read, decorate, toggle, keyOf };
