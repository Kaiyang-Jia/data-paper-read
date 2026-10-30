const { API_BASE_URL } = require("../config");

function request(path, options = {}) {
  const token = wx.getStorageSync("token");
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || "GET",
      data: options.data,
      timeout: 30000,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.header || {})
      },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        if (response.statusCode === 401) {
          wx.removeStorageSync("token");
          wx.removeStorageSync("user");
          getApp().globalData.user = null;
        }
        reject(new Error(response.data?.message || `请求失败 (${response.statusCode})`));
      },
      fail(error) {
        reject(new Error(error.errMsg || "网络连接失败"));
      }
    });
  });
}

function articleSnapshot(article) {
  return {
    doi: article.doi || "",
    url: article.url || "",
    title: article.title || "",
    titleCn: article.titleCn || "",
    journal: article.journal || "",
    Subject: article.Subject || "",
    publishDate: article.publishDate || article.date || ""
  };
}

function articleKey(article) {
  if (article.doi) return `doi:${article.doi.trim().toLowerCase()}`;
  if (article.url) return `url:${article.url.trim()}`;
  const title = (article.titleCn || article.title || "").trim().toLowerCase();
  return title ? `title:${title}` : "";
}

module.exports = { request, articleSnapshot, articleKey };
