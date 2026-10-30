App({
  globalData: {
    user: null
  },

  onLaunch() {
    this.globalData.user = wx.getStorageSync("user") || null;
  }
});
