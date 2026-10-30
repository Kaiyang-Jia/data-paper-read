const { request } = require('../../utils/request');
Page({
  data: { items: [], loading: false, error: '' },
  onLoad() { this.loadUpdates(); },
  onPullDownRefresh() { this.loadUpdates().finally(() => wx.stopPullDownRefresh()); },
  async loadUpdates() {
    this.setData({ loading: true, error: '' });
    try { const result = await request('/api/miniprogram/updates'); this.setData({ items: result.updates }); }
    catch (_) { this.setData({ error: '更新记录暂时无法加载，点击重试' }); }
    finally { this.setData({ loading: false }); }
  },
  onShareAppMessage() { return { title: 'DataPaper · 项目更新', path: '/pages/updates/updates' }; }
});
