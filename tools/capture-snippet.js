/**
 * 豆包签到接口抓包脚本（浏览器控制台用）
 * ---------------------------------------------------------------
 * 用法：
 *   1. 电脑上打开 https://www.doubao.com 并确认已登录
 *   2. 按 F12 → Console，粘贴本文件全部内容，回车
 *   3. 回到豆包页面，正常点一次「签到」
 *   4. 控制台会打印抓到的请求和可直接粘贴的配置，复制即可
 *
 * 原理：临时劫持 fetch / XMLHttpRequest，把请求原样记录下来，不修改任何数据。
 * 刷新页面即失效，不影响正常使用。
 */
(() => {
  const PATTERN = /checkin|sign|signin|daily|task|reward|credit|quota|activity/i;
  const captured = [];
  const oldFetch = window.fetch;

  const record = (url, method, reqHeaders, reqBody, resText) => {
    let hit = false;
    try {
      hit = PATTERN.test(String(url));
    } catch (_) {}
    if (!hit) return;

    captured.push({ url, method, headers: reqHeaders, body: reqBody, response: resText });
    console.clear();
    console.log(`%c抓包成功！共 ${captured.length} 条命中`, "color:#0a0;font-weight:bold");

    const last = captured[captured.length - 1];
    console.log("%c① 复制到 .env / GitHub Secrets 的配置：", "color:#07c;font-weight:bold");
    console.log({
      DOUBAO_CHECKIN_URL: last.url,
      DOUBAO_CHECKIN_METHOD: last.method,
      DOUBAO_CHECKIN_BODY: last.body || "",
      DOUBAO_EXTRA_HEADERS: JSON.stringify(last.headers || {}),
    });
    console.log("%c② 接口原始响应（用来确认成功关键词）：", "color:#07c;font-weight:bold");
    console.log(last.response);
    console.log(
      "%c③ 如果确认这条不对，把 PATTERN 改宽一点再重试一次。",
      "color:#888"
    );
    window.__doubaoCaptured = captured;
  };

  window.fetch = async function (...args) {
    const response = await oldFetch.apply(this, args);
    try {
      const req = args[0];
      const url = typeof req === "string" ? req : req.url;
      const init = args[1] || {};
      const headers = {};
      const rawHeaders = init.headers || (typeof req !== "string" ? req.headers : null);
      if (rawHeaders) {
        if (typeof rawHeaders.forEach === "function" && !Array.isArray(rawHeaders)) {
          rawHeaders.forEach((v, k) => (headers[k] = v));
        } else if (Array.isArray(rawHeaders)) {
          rawHeaders.forEach(([k, v]) => (headers[k] = v));
        } else {
          Object.assign(headers, rawHeaders);
        }
      }
      const body = typeof init.body === "string" ? init.body : null;
      response
        .clone()
        .text()
        .then((text) => record(url, (init.method || "GET").toUpperCase(), headers, body, text))
        .catch(() => {});
    } catch (_) {}
    return response;
  };

  const oldOpen = XMLHttpRequest.prototype.open;
  const oldSend = XMLHttpRequest.prototype.send;
  const oldSetHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__meta = { method: (method || "GET").toUpperCase(), url, headers: {} };
    return oldOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.setRequestHeader = function (key, value) {
    if (this.__meta) this.__meta.headers[key] = value;
    return oldSetHeader.call(this, key, value);
  };
  XMLHttpRequest.prototype.send = function (body) {
    this.addEventListener("load", () => {
      const meta = this.__meta || {};
      record(meta.url, meta.method, meta.headers, typeof body === "string" ? body : null, this.responseText);
    });
    return oldSend.call(this, body);
  };

  console.log(
    "%c已开始监听，请回到页面点一下「签到」…",
    "color:#07c;font-weight:bold;font-size:14px"
  );
})();
