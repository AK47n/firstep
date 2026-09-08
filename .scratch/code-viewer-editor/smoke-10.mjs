// 冒烟（code-viewer-editor/07g）：PDF 栏切换闪动——用户反馈「点 pdf 资料库
// 微微变大、左栏被挤、闪一下」。根因：PDF 栏是唯一空态不满一屏的栏，加载中
// （空态 ~310px）无页面滚动条拇指 → 内容到达后（63 行 ~4126px）拇指出现，
// 触发「无滚→有滚」视觉突变；深滚动位置切到短页还会被浏览器钳位跳变。
// 断言：① 切 PDF 加载中 scrollH > clientH（拇指常驻）；② 加载完成仍 >；
// ③ 从生成页深滚动(≈4789)切 PDF 后 scrollY === 0（显式回顶，无钳位跳变）；
// ④ 切回代码栏滚回顶部（scrollY 0 无残留）；⑤ 与其他栏对照（切 topic/settings
// 后 scrollY 0）；⑥ 往返后 tab 结构完好。零依赖 CDP（9251）。
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
const waitFor = async (expr, ms = 6000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-pdf')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// 导航激活态宽度漂移（07g-2）：.active 曾 font-weight 500→600 使按钮变宽、
// 左侧整排被推；断言激活前/后 PDF 按钮宽度与左邻按钮 left 不变。
const navSnap = () => Eval(`(() => {
  const r = (el) => Math.round(el.getBoundingClientRect().width * 10) / 10;
  const g = (el) => Math.round(el.getBoundingClientRect().left);
  const pdf = document.querySelector('nav button[data-tab="pdf"]');
  const ref = document.querySelector('nav button[data-tab="reference"]');
  return { pdfW: r(pdf), refLeft: g(ref) };
})()`);
const navBefore = await navSnap();

// ① 切 PDF 加载中（空态占位）：scrollH > clientH → 页面滚动条拇指常驻
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
check("切 PDF → 导航激活态宽度恒定（无 500→600 加粗漂移，左侧栏不被推）",
  await waitFor(`(() => {
    const nav = ${JSON.stringify(navBefore)};
    const r = (el) => Math.round(el.getBoundingClientRect().width * 10) / 10;
    const g = (el) => Math.round(el.getBoundingClientRect().left);
    const pdf = document.querySelector('nav button[data-tab="pdf"]');
    const ref = document.querySelector('nav button[data-tab="reference"]');
    return r(pdf) === nav.pdfW && g(ref) === nav.refLeft;
  })()`));
check("切 PDF → 加载中 scrollH > clientH（拇指常驻，无消失-出现闪）",
  await waitFor(`(() => {
    const de = document.documentElement;
    return de.scrollHeight > de.clientHeight && !!document.getElementById('pdf-rows').innerHTML.includes('正在读取');
  })()`),
  JSON.stringify(await Eval(`({ sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight })`)));

// ② 加载完成后仍超视口
check("切 PDF → 加载完成 scrollH > clientH",
  await waitFor(`document.querySelectorAll('#pdf-rows tr').length > 5
    && document.documentElement.scrollHeight > document.documentElement.clientHeight`));

// ③ 深滚动位置切 PDF → scrollY 显式回 0（无钳位跳变）
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-generate')).display !== 'none'`);
await Eval(`window.scrollTo(0, document.documentElement.scrollHeight)`);
await new Promise((r) => setTimeout(r, 150));
const deepY = await Eval(`window.scrollY`);
check("生成页深滚动（scrollY > 1000）", deepY > 1000, String(deepY));
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
await new Promise((r) => setTimeout(r, 80));
check("深滚动切 PDF → scrollY === 0（显式回顶）", await Eval(`window.scrollY`) === 0);

// ④ 加载完成后仍为 0
await waitFor(`document.querySelectorAll('#pdf-rows tr').length > 5`);
check("PDF 加载完成后 scrollY 仍为 0", await Eval(`window.scrollY`) === 0);

// ⑤ 对照栏：settings 切换同样回顶
await Eval(`document.querySelector('nav button[data-tab="settings"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-settings')).display !== 'none'`);
check("切 settings → scrollY === 0", await Eval(`window.scrollY`) === 0);

// ⑥ 往返代码栏后 scrollY 0 且结构完好
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
check("切代码栏 → scrollY === 0", await waitFor(`window.scrollY === 0
  && getComputedStyle(document.getElementById('tab-code')).display === 'flex'`));

console.log(`---- 冒烟总览 ----`);
console.log(`PASS ${passed} / FAIL ${failed}`);
process.exit(failed ? 1 : 0);
