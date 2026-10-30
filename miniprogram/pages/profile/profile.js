const { read, decorate } = require('../../utils/library');
const { present } = require('../../utils/articles');
const actions = require('../../utils/list-actions');
Page({
  ...actions,
  data: { items: [], activeTab: 'favorites', favoriteCount: 0, laterCount: 0 },
  onShow() { this.refreshLibrary(); },
  selectTab(e) { this.setData({ activeTab: e.currentTarget.dataset.tab }); this.refreshLibrary(); },
  refreshLibrary() {
    const library = read();
    this.setData({ items: library[this.data.activeTab].map(present).map(decorate), favoriteCount: library.favorites.length, laterCount: library.later.length });
  }
});
