// 冒烟（code-editor-vscode-polish/03）：标签条增强——
// 中键关闭（活动标签不关 / 非活动关闭；脏标签仍弹确认）→ 拖拽排序
// （mouse 事件链 mousedown/mousemove/mouseup——实现是指针拖拽的 mouse 版）
// → 激活自动 scrollIntoView（Element.prototype 打桩计数）。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(join(SAMPLE, "src"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "#include <stdint.h>\n\nint main(void) {\n    return 0;\n}\n");
writeFileSync(join(SAMPLE, "app.h"), "#pragma once\n");
writeFileSync(join(SAMPLE, "src", "digit.c"), "void digit_init(void) {\n}\n");
writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n\n正文。\n");

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
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
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-tabs') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const tabPaths = () => `[...document.querySelectorAll('#code-tabs .code-tab')].map((t) => t.dataset.tabPath)`;

// ================= 打开 4 个文件（4 标签） =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (const p of ["main.c", "src/digit.c", "app.h", "readme.md"]) {
  await waitFor(`!!document.querySelector('#code-tree [data-code-file="${p}"]')`);
  await Eval(`document.querySelector('#code-tree [data-code-file="${p}"]')?.click()`);
}
check("打开 4 文件 → 4 标签（readme.md 活动）", await waitFor(`
  (() => {
    const t = ${tabPaths()};
    return t.length === 4 && t[3] === 'readme.md'
      && document.querySelector('#code-tabs .code-tab.on').dataset.tabPath === 'readme.md';
  })()`));

// ================= 中键关闭：非活动关、活动不关 =================
await Eval(`(() => {
  const tab = document.querySelector('#code-tabs .code-tab[data-tab-path="app.h"]');
  tab.dispatchEvent(new MouseEvent('auxclick', { button: 1, bubbles: true, cancelable: true }));
  return true;
})()`);
check("中键关闭非活动标签 app.h → 剩 3 标签", await waitFor(`
  document.querySelectorAll('#code-tabs .code-tab').length === 3`));
await Eval(`(() => {
  const on = document.querySelector('#code-tabs .code-tab.on');
  on.dispatchEvent(new MouseEvent('auxclick', { button: 1, bubbles: true, cancelable: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
check("中键点击活动标签 → 不关闭（剩 3 标签）", await Eval(`
  document.querySelectorAll('#code-tabs .code-tab').length === 3`));

// ================= 拖拽排序：main.c 拖到 digit.c 后 =================
// 实现是指针拖拽的 **mouse 事件**版本（mousedown 于标签 / mousemove+mouseup
// 于 document，位移 > DRAG_THRESHOLD=5 才启动；见 ui/codeeditor.js:2856-2899）。
// 2026-09-09 在途盘点修正：原脚本派发 DragEvent（dragstart/dragover/drop），
// 全仓已无 dragstart 监听 → 该段断言恒真但什么都没测。
await Eval(`(() => {
  const strip = document.getElementById('code-tabs');
  const from = strip.querySelector('.code-tab[data-tab-path="main.c"]');
  const r = from.getBoundingClientRect();
  from.dispatchEvent(new MouseEvent('mousedown', {
    bubbles: true, button: 0, clientX: r.left + r.width / 2, clientY: r.top + 4,
  }));
  return true;
})()`);
await Eval(`(() => {
  const strip = document.getElementById('code-tabs');
  const from = strip.querySelector('.code-tab[data-tab-path="main.c"]');
  const digit = strip.querySelector('.code-tab[data-tab-path="src/digit.c"]');
  const readme = strip.querySelector('.code-tab[data-tab-path="readme.md"]');
  const r = from.getBoundingClientRect();
  const dc = digit.getBoundingClientRect();
  const rc = readme.getBoundingClientRect();
  // 目标：被拖标签中心落在 digit 与 readme 中心之间 → 插到 readme 之前
  const x = (dc.left + dc.width / 2 + rc.left + rc.width / 2) / 2;
  document.dispatchEvent(new MouseEvent('mousemove', {
    bubbles: true, clientX: x, clientY: r.top + 4,
  }));
  document.dispatchEvent(new MouseEvent('mouseup', {
    bubbles: true, clientX: x, clientY: r.top + 4,
  }));
  return true;
})()`);
check("拖拽排序：main.c 到 src/digit.c 之后 → 顺序 [digit, main, readme]", await waitFor(`
  JSON.stringify(${tabPaths()}) === JSON.stringify(['src/digit.c', 'main.c', 'readme.md'])`));

// ================= 空白区拖放 = 追加末尾 =================
await Eval(`(() => {
  const strip = document.getElementById('code-tabs');
  const from = strip.querySelector('.code-tab[data-tab-path="src/digit.c"]');
  const r = from.getBoundingClientRect();
  from.dispatchEvent(new MouseEvent('mousedown', {
    bubbles: true, button: 0, clientX: r.left + r.width / 2, clientY: r.top + 4,
  }));
  return true;
})()`);
await Eval(`(() => {
  const strip = document.getElementById('code-tabs');
  const from = strip.querySelector('.code-tab[data-tab-path="src/digit.c"]');
  const r = from.getBoundingClientRect();
  const sr = strip.getBoundingClientRect();
  const x = sr.right + 40;   // 越过全部兄弟中心 → atEnd
  document.dispatchEvent(new MouseEvent('mousemove', {
    bubbles: true, clientX: x, clientY: r.top + 4,
  }));
  document.dispatchEvent(new MouseEvent('mouseup', {
    bubbles: true, clientX: x, clientY: r.top + 4,
  }));
  return true;
})()`);
check("空白区拖放 → 追加末尾 [main, readme, digit]", await waitFor(`
  JSON.stringify(${tabPaths()}) === JSON.stringify(['main.c', 'readme.md', 'src/digit.c'])`));

// ================= 从关闭钮按下不启动拖动 =================
await Eval(`(() => {
  const close = document.querySelector('#code-tabs .code-tab[data-tab-path="readme.md"] .code-tab-close');
  const r = close.getBoundingClientRect();
  close.dispatchEvent(new MouseEvent('mousedown', {
    bubbles: true, button: 0, clientX: r.left + r.width / 2, clientY: r.top + 2,
  }));
  document.dispatchEvent(new MouseEvent('mousemove', {
    bubbles: true, clientX: r.left + 120, clientY: r.top + 2,
  }));
  document.dispatchEvent(new MouseEvent('mouseup', {
    bubbles: true, clientX: r.left + 120, clientY: r.top + 2,
  }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 200));
check("从关闭钮 mousedown → 无 .dragging（不启动拖动）", await Eval(`
  document.querySelectorAll('#code-tabs .code-tab.dragging').length === 0`));
check("关闭钮 mousedown 后顺序不变", await Eval(`
  JSON.stringify(${tabPaths()}) === JSON.stringify(['main.c', 'readme.md', 'src/digit.c'])`));

// ================= 激活自动 scrollIntoView（打桩计数） =================
await Eval(`(() => {
  window.__sivCount = 0;
  const orig = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (...a) {
    window.__sivCount += 1;
    return orig.apply(this, a);
  };
  return true;
})()`);
await Eval(`document.querySelector('#code-tabs .code-tab[data-tab-path="src/digit.c"]')?.click()`);
check("激活标签 → scrollIntoView 被调用（≥1）", await waitFor(`window.__sivCount >= 1`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
