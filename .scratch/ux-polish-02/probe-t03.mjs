// ux-polish-02 探针：工单 03 冒烟——横幅「去设置/去填写」展开 AI API 卡并聚焦 key。
// 依赖：webapp 8000 + Chrome 9251（无 LLM 调用；横幅强制显示以覆盖「已配置」环境）。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const jsErrors = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Network.clearBrowserCache");   // 模块缓存会残留旧版（t02/t03 教训）：先清缓存再导航

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
// 等待新文档提交：location.href 命中本次 token 且 readyState=complete（旧文档
// 也有 gen-overview，单查元素会把断言跑进导航提交前的旧页面——t02/t03 教训）
const token = "np=" + Date.now();
const waitNewDoc = async () => {
  for (let i = 0; i < 120; i++) {
    try {
      const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
      if (st.href.includes(token) && st.rs === "complete" && st.ov) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
};
await cdp("Page.navigate", { url: pageUrl + "?" + token });
if (!(await waitNewDoc())) { console.error("页面未就绪"); process.exit(1); }

// 前置：手动折叠 AI API 卡（模拟用户折叠过）
await Eval(`(() => {
  const card = document.querySelector('[data-collapse-id="llm-api"]');
  if (!card.classList.contains('collapsed')) {
    const btn = card.querySelector('.card-collapse');
    if (btn) btn.click(); else card.querySelector('h2').click();
  }
})()`);
await new Promise((r) => setTimeout(r, 150));
check("前置：AI API 卡已折叠", await Eval(`document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed')`));

// 1) gen-banner「去设置」：强制显示横幅后点击
await Eval(`document.getElementById('gen-banner').classList.remove('hidden')`);
await Eval(`document.getElementById('btn-banner-goto-settings').click()`);
await new Promise((r) => setTimeout(r, 400));
const st1 = await Eval(`({
  settingsActive: document.getElementById('tab-settings').classList.contains('active'),
  collapsed: document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed'),
  focused: document.activeElement && document.activeElement.id === 'set-api-key',
})`);
check("gen-banner：切到设置页 + AI API 卡展开 + key 聚焦",
  st1.settingsActive && !st1.collapsed && st1.focused, JSON.stringify(st1));

// 2) settings-banner「去填写」：先回生成页、再折叠卡、再点横幅按钮
await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === 'generate'); b.click(); })()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`(() => {
  const card = document.querySelector('[data-collapse-id="llm-api"]');
  if (!card.classList.contains('collapsed')) {
    const btn = card.querySelector('.card-collapse');
    if (btn) btn.click(); else card.querySelector('h2').click();
  }
})()`);
await new Promise((r) => setTimeout(r, 150));
await Eval(`document.getElementById('settings-banner').classList.remove('hidden')`);
await Eval(`document.getElementById('btn-settings-banner-goto').click()`);
await new Promise((r) => setTimeout(r, 400));
const st2 = await Eval(`({
  settingsActive: document.getElementById('tab-settings').classList.contains('active'),
  collapsed: document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed'),
  focused: document.activeElement && document.activeElement.id === 'set-api-key',
})`);
check("settings-banner：切到设置页 + 卡展开 + key 聚焦",
  st2.settingsActive && !st2.collapsed && st2.focused, JSON.stringify(st2));

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
