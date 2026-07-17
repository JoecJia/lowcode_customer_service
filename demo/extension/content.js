// ============================================================
// Content Script — 命令执行引擎
// 监听来自控制台页面的 postMessage，执行浏览器操作
// ============================================================

(function () {
  // --- 工具函数 -------------------------------------------------

  function waitForSelector(selector, timeout = 10000) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(selector)) return resolve();
      const observer = new MutationObserver(() => {
        if (document.querySelector(selector)) {
          observer.disconnect();
          resolve();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => { observer.disconnect(); reject(new Error(`等待超时: ${selector}`)); }, timeout);
    });
  }

  function wait(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function simulateDrag(sourceSelector, targetSelector) {
    const source = document.querySelector(sourceSelector);
    const target = document.querySelector(targetSelector);
    if (!source || !target) throw new Error("元素未找到");

    const sr = source.getBoundingClientRect();
    const tr = target.getBoundingClientRect();

    const opts = (x, y) => ({
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: x,
      clientY: y,
    });

    source.dispatchEvent(
      new MouseEvent("mousedown", opts(sr.x + sr.width / 2, sr.y + sr.height / 2))
    );
    source.dispatchEvent(
      new MouseEvent("mousemove", opts(sr.x + sr.width / 2, sr.y + sr.height / 2))
    );
    source.dispatchEvent(
      new MouseEvent("mousemove", opts(tr.x + tr.width / 2, tr.y + tr.height / 2))
    );
    target.dispatchEvent(
      new MouseEvent("mousemove", opts(tr.x + tr.width / 2, tr.y + tr.height / 2))
    );
    target.dispatchEvent(
      new MouseEvent("mouseup", opts(tr.x + tr.width / 2, tr.y + tr.height / 2))
    );
  }

  // --- 命令处理器 ------------------------------------------------

  const handlers = {

    click({ selector }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      el.scrollIntoView({ block: "center" });
      el.click();
    },

    fill({ selector, value }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      el.focus();
      el.value = "";
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    },

    select({ selector, value }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      el.value = value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    },

    hover({ selector }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      el.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
      el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    },

    drag({ source, target }) {
      simulateDrag(source, target);
    },

    press({ key }) {
      const el = document.activeElement || document.body;
      el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keypress", { key, bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
    },

    getText({ selector }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      return el.innerText || el.textContent || "";
    },

    getValue({ selector }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      return el.value;
    },

    getAttribute({ selector, attribute }) {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`未找到元素: ${selector}`);
      return el.getAttribute(attribute);
    },

    scroll({ x = 0, y = 0, selector }) {
      if (selector) {
        document.querySelector(selector)?.scrollIntoView({ block: "center", behavior: "smooth" });
      } else {
        window.scrollTo({ left: x, top: y, behavior: "smooth" });
      }
    },

    evaluate({ script }) {
      return eval(script);
    },

    navigate({ url }) {
      window.location.href = url;
    },

    async waitForSelector({ selector, timeout }) {
      await waitForSelector(selector, timeout);
    },

    async wait({ ms }) {
      await wait(ms);
    },

    screenshot() {
      chrome.runtime.sendMessage({ type: "screenshot" });
    },
  };

  // --- 消息监听 -------------------------------------------------

  window.addEventListener("message", async (event) => {
    if (event.source !== window) return;

    const msg = event.data;
    if (!msg) return;

    // 心跳检测
    if (msg.type === "EXTENSION_PING") {
      window.postMessage({ type: "EXTENSION_PONG" }, "*");
      return;
    }

    if (msg.type !== "EXTENSION_COMMAND") return;

    const { steps, commandId } = msg;
    const results = [];

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const { action } = step;

      if (!handlers[action]) {
        results.push({ index: i, action, success: false, error: `未知命令: ${action}` });
        continue;
      }

      try {
        const result = await handlers[action](step);
        results.push({ index: i, action, success: true, data: result });
      } catch (err) {
        results.push({ index: i, action, success: false, error: err.message, selector: step.selector });
      }
    }

    window.postMessage({ type: "EXTENSION_RESULT", commandId, results }, "*");
  });

  console.log("[浏览器操作执行器] Content Script 已就绪");
})();
