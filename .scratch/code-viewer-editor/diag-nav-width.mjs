// 诊断 7c：导航激活态宽度漂移——用户反馈「点 pdf 这个栏泡泡变宽了一点，
// 把左边栏目挤到更左，不点又变窄回来」。根因 = .active 的 font-weight
// 500→600（粗体文字更宽，按钮宽度自适应，激活瞬间整排左移）。
// 断言：激活前/后 PDF 按钮 getBoundingClientRect().width 相等、左邻按钮
// left 不变。零依赖 CDP（9251）。
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
await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker && !!document.querySelector('nav button[data-tab="pdf"]')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
const snap = () => Eval(`(() => {
  const pdf = document.querySelector('nav button[data-tab="pdf"]');
  const ref = document.querySelector('nav button[data-tab="reference"]');
  const gen = document.querySelector('nav button[data-tab="generate"]');
  const r = (el) => Math.round(el.getBoundingClientRect().width * 10) / 10;
  return { pdfW: r(pdf), pdfLeft: Math.round(pdf.getBoundingClientRect().left),
           refLeft: Math.round(ref.getBoundingClientRect().left),
           genRight: Math.round(gen.getBoundingClientRect().right) };
})()`);
const before = await snap();
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
await new Promise((r) => setTimeout(r, 300));
const after = await snap();
console.log("激活前:", JSON.stringify(before));
console.log("激活后:", JSON.stringify(after));
const wOk = before.pdfW === after.pdfW;
const lOk = before.refLeft === after.refLeft && before.genRight === after.genRight;
console.log(wOk ? "PASS PDF 按钮宽度不变 (500→600 已去除)" : "FAIL 宽度漂移 " + before.pdfW + "→" + after.pdfW);
console.log(lOk ? "PASS 左侧按钮位置不变" : "FAIL 左移 " + before.refLeft + "→" + after.refLeft);
process.exit(wOk && lOk ? 0 : 1);
