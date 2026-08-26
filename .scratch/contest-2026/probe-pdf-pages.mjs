// 页面级验证：赛题库 PDF 页图预览（修复「定位失败→全库 400」后）
// 用法：node probe-pdf-pages.mjs  （需 Chrome CDP 9251 + webapp 8000）
// 断言：赛题库卡片加载；loadTopicPdf(key) 后 #topic-pdf-box 可见、
// #topic-pdf-pages img ≥ 1 且 data:image/png；实测 2026C / 2026H / 2021F。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"))
  || targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

await Eval(`window.__smokeMarkerPdf = 1`);
await cdp("Page.reload", { ignoreCache: true });
// 切赛题库 tab（loadTopics 因此触发，卡片才会填充）
for (let i = 0; i < 20; i++) {
  const clicked = await Eval(`(() => {
    const tab = [...document.querySelectorAll('nav button, header button, .nav button')]
      .find((b) => b.textContent.trim() === '赛题库');
    if (tab) { tab.click(); return true; }
    return false;
  })()`);
  if (clicked) break;
  await new Promise((r) => setTimeout(r, 300));
}
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarkerPdf
      && document.querySelectorAll('#topic-grid .topic-card').length > 0
      && typeof loadTopicPdf === 'function'`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

const cards = await Eval(`document.querySelectorAll('#topic-grid .topic-card').length`);
check("赛题库卡片加载", cards >= 10, "cards=" + cards);

for (const key of ["2026C", "2026H", "2021F"]) {
  const r = await Eval(`(async () => {
    try {
      await loadTopicPdf(${JSON.stringify(key)});
      const box = document.getElementById("topic-pdf-box");
      const imgs = [...document.querySelectorAll("#topic-pdf-pages img")];
      return {
        visible: !!(box && !box.classList.contains("hidden")),
        n: imgs.length,
        allPng: imgs.length > 0 && imgs.every((im) => (im.src || "").startsWith("data:image/png")),
        msg: (document.getElementById("topic-msg") || {}).textContent || "",
      };
    } catch (e) { return { err: String((e && e.message) || e) }; }
  })()`);
  check(`${key} 页图预览`, r && !r.err && r.visible && r.n > 0 && r.allPng,
    r && r.err ? "err=" + r.err : `visible=${r && r.visible} imgs=${r && r.n}`);
}

await Eval(`hideTopicPdfViewer()`);
console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED(${failed})`);
process.exit(failed === 0 ? 0 : 1);
