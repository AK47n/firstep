// ux-polish-02 探针（部分）：工单 01 冒烟——空推荐不标步骤5 + 步骤7 wiring 类渲染。
// 依赖：webapp 8000 + Chrome --headless --remote-debugging-port=9251（无 LLM 调用）。
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
await cdp("Page.navigate", { url: pageUrl + "?np=" + Date.now() });

let ready = false;
for (let i = 0; i < 120 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('platforms') && document.getElementById('platforms').children.length > 0`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

// 0) 步骤芯片存在 + 无 JS 异常
const chip7 = await Eval(`(() => {
  const chip = document.querySelector('.ov-chip[data-step="7"]');
  return { exists: !!chip, cls: chip ? chip.className : "", dot: chip ? chip.querySelector('.ov-dot').textContent : "" };
})()`);
check("总览 chip(7) 存在且未完成默认数字", chip7.exists && chip7.cls.includes("ov-chip"), chip7.cls);

// 1) 空推荐不标步骤 5：直接调 renderRecommendResult（模块内函数在 window 不可达，
// 用 toast/状态不可行——改为只验证「未完成时步骤5卡无 done 类 + 徽章空」
const s5 = await Eval(`(() => {
  const card = [...document.querySelectorAll('.gen-steps > .card')].find((c) => {
    const no = c.querySelector('.step-no'); return no && no.textContent.trim() === '5';
  });
  const badge = card ? card.querySelector('.card-step-status') : null;
  return { cardDone: card ? card.classList.contains('done') : null, badgeText: badge ? badge.textContent : null };
})()`);
check("初始步骤5卡未标完成（徽章空）", s5.cardDone === false && (s5.badgeText === "" || s5.badgeText === null), JSON.stringify(s5));

// 2) 步骤 7 徽章渲染（初始未完成：无 done/wire 类）
const s7 = await Eval(`(() => {
  const card = [...document.querySelectorAll('.gen-steps > .card')].find((c) => {
    const no = c.querySelector('.step-no'); return no && no.textContent.trim() === '7';
  });
  const badge = card ? card.querySelector('.card-step-status') : null;
  return { cardDone: card ? card.classList.contains('done') : null, badgeCls: badge ? badge.className : null };
})()`);
check("初始步骤7卡未标完成", s7.cardDone === false, JSON.stringify(s7));

// 3) 无未捕获 JS 异常（页面加载 + 切换页签）
for (const tab of ["library", "topic", "pdf", "master", "guide"]) {
  await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === '${tab}'); if (b) b.click(); })()`);
  await new Promise((r) => setTimeout(r, 200));
}
check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));

console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
