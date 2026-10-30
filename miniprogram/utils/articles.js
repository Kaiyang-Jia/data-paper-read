function contentText(value) {
  const text = String(value || '').trim();
  if (/^(暂无数据|未提供|未识别|未分类|待核实|未知|N\/A|null|none|-)$/i.test(text)) return '';
  return text.split(/([。！？\n])/).reduce((out, part, i, all) => {
    if (i % 2) return out;
    if (/仅依据标题|当前缺少摘要|尚未人工复核|模型整理|信息尚未验证|待核实|待复核|需复核|需核验|仅元数据|AI整理|AI解读|智能提取|模型判断/.test(part)) return out;
    return out + part + (all[i + 1] || '');
  }, '').trim();
}
function present(a) {
  return { ...a, id: a.id || a.doi || a.url || String(a.title || '').toLowerCase(),
    displayTitle: contentText(a.titleCn) || a.title,
    displayIntro: a.chineseProcessing && a.chineseProcessing.basis === 'title' ? '' : contentText(a.interpretationCn) || contentText(a.abstract),
    publishDate: a.publishDate || a.date || '' };
}
function pathOf(a) { return '/pages/detail/detail?id=' + encodeURIComponent(a.id); }
function open(a) { wx.navigateTo({ url: pathOf(a) }); }
function share(a) { return { title: a.displayTitle || a.titleCn || a.title, path: pathOf(a) }; }
module.exports = { present, pathOf, open, share };
