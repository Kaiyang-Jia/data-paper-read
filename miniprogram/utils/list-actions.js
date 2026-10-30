const library = require('./library');
const articles = require('./articles');
module.exports = {
  openDetail(e) { articles.open(this.data.items[e.currentTarget.dataset.index]); },
  toggleFavorite(e) { this.toggleItem(e, 'favorites'); },
  toggleLater(e) { this.toggleItem(e, 'later'); },
  toggleItem(e, kind) {
    try {
      const selected = library.toggle(this.data.items[e.currentTarget.dataset.index], kind);
      this.setData({ items: this.data.items.map(library.decorate) });
      if (this.refreshLibrary) this.refreshLibrary();
      wx.showToast({ title: selected ? (kind === 'later' ? '已加入稍后读' : '已收藏') : '已移除', icon: 'none' });
    } catch (_) { wx.showToast({ title: '保存失败，请检查手机存储', icon: 'none' }); }
  },
  onShareAppMessage(e) {
    const index = e.target && e.target.dataset.index;
    return index !== undefined && this.data.items[index] ? articles.share(this.data.items[index]) : { title: 'DataPaper · 每天发现几篇数据论文', path: '/pages/index/index' };
  }
};
