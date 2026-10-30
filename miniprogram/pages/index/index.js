const { request } = require('../../utils/request');
const { present } = require('../../utils/articles');
const { decorate } = require('../../utils/library');
const actions = require('../../utils/list-actions');
const CACHE = 'datapaper-mobile-daily';
Page({
  ...actions,
  data: { loading: false, items: [], date: '', error: '', offline: false, totalCount: 0 },
  onLoad() { this.loadDaily(); },
  onShow() {
    this.setData({ items: this.data.items.map(decorate) });
    const today = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
    if (this.data.date && this.data.date !== today && !this.data.loading) this.loadDaily();
  },
  onPullDownRefresh() { this.loadDaily().finally(() => wx.stopPullDownRefresh()); },
  async loadDaily() {
    this.setData({ loading: true, error: '', offline: false });
    try {
      const result = await request('/api/miniprogram/feed?mode=daily');
      this.setData({ items: result.articles.map(present).map(decorate), date: result.date, totalCount: result.summary.totalCount });
      try { wx.setStorageSync(CACHE, result); } catch (_) {}
    } catch (_) {
      const cached = wx.getStorageSync(CACHE);
      if (cached && Array.isArray(cached.articles)) this.setData({ items: cached.articles.map(present).map(decorate), date: cached.date, offline: true });
      else this.setData({ error: '暂时无法加载，点击重试' });
    } finally { this.setData({ loading: false }); }
  },
  goSearch() { wx.switchTab({ url: '/pages/search/search' }); }
});
