// ============================================================
// Background Service Worker
// ============================================================

chrome.runtime.onInstalled.addListener(() => {
  console.log("[浏览器操作执行器] 插件已安装");
});

// 截图请求
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "screenshot") {
    chrome.tabs.captureVisibleTab(sender.tab.windowId, { format: "png" }, (dataUrl) => {
      if (dataUrl) {
        chrome.tabs.sendMessage(sender.tab.id, {
          type: "screenshot_result",
          dataUrl,
        });
      }
    });
  }
  return true;
});

// 监听新 tab 打开（用于弹窗自动化场景）
chrome.tabs.onCreated.addListener((tab) => {
  console.log("[浏览器操作执行器] 新 tab 已创建:", tab.id);
});
