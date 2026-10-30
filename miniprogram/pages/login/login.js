const { request } = require("../../utils/request");

Page({
  data: {
    mode: "login",
    loading: false,
    form: {
      email: "",
      password: "",
      displayName: "",
      researchField: ""
    }
  },

  switchMode() {
    this.setData({ mode: this.data.mode === "login" ? "register" : "login" });
  },

  onFieldInput(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value });
  },

  async submit() {
    const form = this.data.form;
    if (!form.email || !form.password) {
      wx.showToast({ title: "请填写邮箱和密码", icon: "none" });
      return;
    }
    if (this.data.mode === "register" && (!form.displayName || !form.researchField)) {
      wx.showToast({ title: "请填写昵称和研究领域", icon: "none" });
      return;
    }

    this.setData({ loading: true });
    try {
      const result = await request(`/api/miniprogram/auth/${this.data.mode}`, {
        method: "POST",
        data: form
      });
      wx.setStorageSync("token", result.token);
      wx.setStorageSync("user", result.user);
      getApp().globalData.user = result.user;
      wx.showToast({ title: this.data.mode === "login" ? "登录成功" : "注册成功" });
      setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: "/pages/profile/profile" }) }), 500);
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  }
});
