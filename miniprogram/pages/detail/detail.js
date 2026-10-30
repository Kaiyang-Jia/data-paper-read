const { request } = require('../../utils/request');
const { present, share } = require('../../utils/articles');
const library = require('../../utils/library');
Page({
  data: { article: null, loading: true, error: '' },
  onLoad(options) {
    this.identity = options.id || '';
    this.loadArticle();
  },
  onShow() { if (this.data.article) this.setData({ article: library.decorate(this.data.article) }); },
  async loadArticle() {
    this.setData({ loading: true, error: '' });
    try {
      const result = await request('/api/miniprogram/article', { data: { id: this.identity } });
      this.setData({ article: library.decorate(present(result.article)) });
    } catch (_) {
      const lists = library.read();
      const cached = lists.favorites.concat(lists.later).find(a => a.id === this.identity);
      if (cached) this.setData({ article: library.decorate(present(cached)), error: '暂时离线，显示保存的内容' });
      else this.setData({ error: '暂时无法打开这篇论文，点击重试' });
    } finally { this.setData({ loading: false }); }
  },
  toggleFavorite() { this.toggle('favorites'); },
  toggleLater() { this.toggle('later'); },
  toggle(kind) {
    try {
      library.toggle(this.data.article, kind);
      this.setData({ article: library.decorate(this.data.article) });
    } catch (_) { wx.showToast({ title: '保存失败，请检查手机存储', icon: 'none' }); }
  },
  markRead() { if (this.data.article.later) this.toggle('later'); wx.showToast({ title: '已从稍后读移除', icon: 'none' }); },
  copyDoi() { if (this.data.article.doi) wx.setClipboardData({ data: this.data.article.doi }); },
  openSource() {
    const a = this.data.article;
    const url = /^10\.\d{4,9}\//.test(a.doi || '') ? 'https://doi.org/' + encodeURI(a.doi).replace(/[?#]/g, encodeURIComponent) : a.url;
    if (/^https?:\/\//.test(url || '')) wx.setClipboardData({ data: url });
  },
  onShareAppMessage() { return this.data.article ? share(this.data.article) : { title: 'DataPaper', path: '/pages/index/index' }; },
  onShareTimeline() { return { title: this.data.article ? this.data.article.displayTitle : 'DataPaper', query: 'id=' + encodeURIComponent(this.identity) }; }
});
