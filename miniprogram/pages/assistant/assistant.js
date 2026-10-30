const { request } = require("../../utils/request");

Page({
  data: {
    question: "",
    loading: false,
    answer: "",
    recommendations: [],
    examples: [
      "我想研究中国城市热岛与极端高温，需要长期遥感数据",
      "我想分析全球海洋微塑料污染分布，需要可比较的观测数据库",
      "我正在做蛋白质结构预测，需要开放的机器学习训练数据"
    ]
  },

  onInput(event) {
    this.setData({ question: event.detail.value });
  },

  useExample(event) {
    this.setData({ question: event.currentTarget.dataset.question });
  },

  async submit() {
    const question = this.data.question.trim();
    if (question.length < 4) {
      wx.showToast({ title: "请更详细地描述研究需求", icon: "none" });
      return;
    }
    this.setData({ loading: true, answer: "", recommendations: [] });
    try {
      const result = await request("/api/research-assistant", {
        method: "POST",
        data: { message: question }
      });
      const recommendations = (result.recommendations || []).map((article, index) => ({
        ...article,
        _key: article.doi || article.url || `recommendation-${index}`,
        displayTitle: article.titleCn || article.title || "未命名论文"
      }));
      this.setData({ answer: result.answer || "", recommendations });
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  openDetail(event) {
    const article = this.data.recommendations[event.currentTarget.dataset.index];
    wx.setStorageSync("activeArticle", article);
    wx.navigateTo({ url: "/pages/detail/detail" });
  }
});
