// 冒烟（新手指引更新）：补「代码」tab 教程条目 + 修正导航分组描述。
// 断言：① build 章优先渲染新小节「代码栏：IDE 式代码编辑器」；
// ② 小节内容含关键事实（文件树 / 多标签 / Ctrl+S / 脏点 / 大纲 / 搜索 / 保存冲突 / 第 8 步联动）；
// ③ jump 按钮 data-jump-tab="code" 存在且点击跳到代码栏；
// ④ 顶部导航「做题」组文案含「代码」；⑤ 12 步表第 8 步含「加载为编辑内容」。
// 零依赖 CDP（9251）。
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
const { writeFileSync } = await import("node:fs");
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker && !!document.getElementById('tab-guide')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// 打开新手指引 → 做题主线章
await Eval(`document.querySelector('nav button[data-tab="guide"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-guide')).display !== 'none'`);
await Eval(`document.querySelector('.guide-tab[data-guide-tab="build"]')?.click()`);
const got = await waitFor(`document.getElementById('guide-panel-build')?.innerText.includes('代码栏：IDE 式代码编辑器')`);
check("build 章渲染「代码栏：IDE 式代码编辑器」小节", got);
const txt = await Eval(`document.getElementById('guide-panel-build').innerText`);
const facts = ["文件树", "多标签", "Ctrl+S", "脏点", "大纲", "搜索", "保存冲突", "加载为编辑内容"];
const miss = facts.filter((f) => !txt.includes(f));
check("小节关键事实齐备（8 项）", miss.length === 0, miss.join("/"));
const jumpOk = await Eval(`!!document.querySelector('#guide-panel-build .guide-jump[data-jump-tab="code"]')`);
check("「打开代码栏逛逛」jump → data-jump-tab=code", jumpOk);
await Eval(`document.querySelector('#guide-panel-build .guide-jump[data-jump-tab="code"]')?.click()`);
check("点击 jump → 切到代码栏激活", await waitFor(`getComputedStyle(document.getElementById('tab-code')).display === 'flex'`));

// 回指南看导航分组文案与 12 步第 8 行（在 build 章内）
await Eval(`document.querySelector('nav button[data-tab="guide"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-guide')).display !== 'none'`);
await Eval(`document.querySelector('.guide-tab[data-guide-tab="build"]')?.click()`);
await waitFor(`document.getElementById('guide-panel-build')?.innerText.includes('代码栏：IDE 式代码编辑器')`);
const txt2 = await Eval(`document.getElementById('guide-panel-build').innerText`);
const p1 = await Eval(`document.querySelector('.guide-tab[data-guide-tab="build"]') && (() => {
  const p = document.getElementById('guide-panel-build');
  const navIdx = p.innerText.indexOf('「做题」组');
  return p.innerText.slice(navIdx, navIdx + 240);
})()`);
check("「做题」组条目含代码栏描述", p1.includes('代码') && p1.includes('IDE 式'), "");
check("12 步第 8 行含「加载为编辑内容」", txt2.includes("加载为编辑内容"));

const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-viewer-editor/shot-guide-build.png", Buffer.from(shot.result.data, "base64"));
console.log(`---- 冒烟总览 ----`);
console.log(`PASS ${passed} / FAIL ${failed}`);
process.exit(failed ? 1 : 0);
