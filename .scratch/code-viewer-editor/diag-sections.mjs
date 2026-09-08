// 诊断 3：各 .page section 真实显示状态（用户反馈「所有栏底部都能看到代码编辑器」）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};

// 1) 生成栏激活时，各 section 的 display（先 reload 拿最新 CSS——旧 CSS 下
// #tab-code display:flex 常驻，页面内存状态不是修复后行为）
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await new Promise((r) => setTimeout(r, 400));
const states = await Eval(`[...document.querySelectorAll('section.page')].map((s) => ({
  id: s.id,
  display: getComputedStyle(s).display,
  active: s.classList.contains('active'),
  height: s.getBoundingClientRect().height,
}))`);
console.log(JSON.stringify(states, null, 1));

// 2) 生成栏页脚有没有代码三明治/编辑器结构
const footerCheck = await Eval(`(() => {
  const gen = document.getElementById('tab-generate');
  const codeTa = gen.querySelector('.code-ta, textarea');
  const hl = gen.querySelector('.code-hl, .hl-layer');
  const bottom = gen.querySelector('#code-viewer, [class*="code-edit"]');
  const last = gen.lastElementChild;
  return {
    codeTaInsideGenerate: !!codeTa,
    hlInsideGenerate: !!hl,
    codeViewerInsideGenerate: !!bottom,
    lastChildClass: last ? String(last.className) : null,
    lastChildHTML: last ? last.outerHTML.slice(0, 160) : null,
  };
})()`);
console.log(JSON.stringify(footerCheck, null, 1));

// 3) 截图生成栏底部
await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await Eval(`document.getElementById('tab-generate').scrollIntoView()`);
await Eval(`window.scrollTo(0, document.body.scrollHeight)`);
await new Promise((r) => setTimeout(r, 600));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const { writeFileSync } = await import("node:fs");
writeFileSync(".scratch/code-viewer-editor/diag-generate-bottom.png", Buffer.from(shot.result.data, "base64"));
console.log("shot saved");
ws.close();
