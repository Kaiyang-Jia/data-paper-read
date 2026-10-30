const { request } = require('../../utils/request');
const { present } = require('../../utils/articles');
const { decorate } = require('../../utils/library');
const actions = require('../../utils/list-actions');
Page({
  ...actions,
  data: { items: [], keyword: '', loading: false, total: 0, hasMore: false, page: 0, error: '' },
  onLoad() { this.search(); },
  onShow() { this.setData({ items: this.data.items.map(decorate) }); },
  onInput(e) { this.setData({ keyword: e.detail.value }); },
  search() {
    this.query = this.data.keyword.trim();
    this.sequence = (this.sequence || 0) + 1;
    this.setData({ items: [], page: 0, error: '', hasMore: false });
    return this.loadPage(1, this.sequence);
  },
  clearSearch() { this.setData({ keyword: '' }); this.search(); },
  onReachBottom() { if (this.data.hasMore && !this.data.loading) this.loadPage(this.data.page + 1, this.sequence); },
  async loadPage(page, sequence) {
    this.setData({ loading: true, error: '' });
    try {
      const result = await request('/api/miniprogram/feed', { data: { mode: 'search', q: this.query, page } });
      if (sequence !== this.sequence) return;
      this.setData({ items: (page === 1 ? [] : this.data.items).concat(result.articles.map(present).map(decorate)), page, total: result.total, hasMore: result.hasMore });
    } catch (_) {
      if (sequence === this.sequence) this.setData({ error: '搜索暂时不可用，点击重试' });
    } finally { if (sequence === this.sequence) this.setData({ loading: false }); }
  },
  retry() { this.loadPage(this.data.page + 1, this.sequence); }
});
