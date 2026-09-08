// 冒烟（code-editor-refine/03 大纲符号过滤 + Ctrl+Shift+O 速达）：真实浏览器验证
// Ctrl+Shift+O 展开侧栏切大纲并聚焦过滤框全选；输入即时过滤（精确/前缀优先、
// 大小写不敏感）；Enter 跳首个命中；无匹配空态；Esc 清空恢复；过滤与跳转随
// 活动标签。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-03");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "a.c"), [
  '#include "app.h"',
  "#define LED_PIN 5",
  "#define led_delay_ms 100",
  "void setup(void) { }",
  "void setup_timer(void) { }",
  "void main(void) { }",
  "int helper(void) { return 0; }",
  "#define setup_mask 0x01",
  "",
].join("\n"));

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

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
const openFile = (name) => Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
const pressOn = (sel, opts) => Eval(`(() => {
  const el = document.querySelector(${JSON.stringify(sel)});
  if (!el) return false;
  el.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)}));
  return true;
})()`);
const setFilter = (q) => Eval(`(() => {
  const f = document.getElementById('code-outline-filter');
  if (!f) return false;
  f.focus();
  f.value = ${JSON.stringify(q)};
  f.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const collapsed = () => Eval(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') ?? null`);
const outlineOn = () => Eval(`document.querySelector('.code-side-tabs [data-code-side="outline"]')?.classList.contains('on') ?? false`);
const outlineVisible = () => Eval(`!document.querySelector('[data-code-side-panel="outline"]')?.classList.contains('hidden') ?? false`);
const filterFocused = () => Eval(`document.activeElement === document.getElementById('code-outline-filter')`);
const rowNames = () => Eval(`Array.from(document.querySelectorAll('#code-outline .code-outline-item')).map((b) => b.querySelector('.code-outline-name').textContent)`);
const cursorLine = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return -1;
  const s = ta.value.slice(0, ta.selectionStart);
  return (s.match(/\\n/g) || []).length + 1;
})()`);

// ---- 准备：打开目录 + 打开 a.c ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`);
await openFile("a.c");
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 1
  && document.querySelectorAll('#code-outline .code-outline-item').length >= 4`);
check("0 打开 a.c 大纲就位（≥4 符号）", (await rowNames()).length >= 4);

// ---- 场景 1：Ctrl+Shift+O → 展开 + 切大纲 + 聚焦过滤框全选 ----
await Eval(`document.querySelector('.code-side-collapse')?.click(); true`);   // 先收起
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === true`);
await pressOn('body', { key: "o", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === false
  && document.activeElement === document.getElementById('code-outline-filter')`);
check("1a Ctrl+Shift+O 展开侧栏", await collapsed() === false);
check("1b 大纲面板激活", await outlineOn() && await outlineVisible());
check("1c 过滤框聚焦", await filterFocused());

// ---- 场景 2：输入过滤（函数优先 + 精确/前缀，大小写不敏感）----
await setFilter("MAIN");
await waitFor(`document.querySelectorAll('#code-outline .code-outline-item').length === 1`);
check("2a 过滤 MAIN 只剩 main", JSON.stringify(await rowNames()) === JSON.stringify(["main"]));
await setFilter("setup");
await waitFor(`document.querySelectorAll('#code-outline .code-outline-item').length === 3`);
check("2b setup 函数优先（define 最后）",
  JSON.stringify(await rowNames()) === JSON.stringify(["setup", "setup_timer", "setup_mask"]));

// ---- 场景 3：当前选中（默认首个）+ ↑/↓ 移动 + Enter 跳选中 ----
check("3a 默认选中首个（setup）",
  await Eval(`document.querySelector('#code-outline .code-outline-item.on .code-outline-name')?.textContent`) === "setup");
await pressOn('#code-outline-filter', { key: "ArrowDown", bubbles: true, cancelable: true });
await waitFor(`document.querySelector('#code-outline .code-outline-item.on .code-outline-name')?.textContent === "setup_timer"`);
await pressOn('#code-outline-filter', { key: "Enter", bubbles: true, cancelable: true });
await waitFor(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  const s = ta.value.slice(0, ta.selectionStart);
  return (s.match(/\\n/g) || []).length + 1 === 5;
})()`);
check("3b ↑↓ 移动后 Enter 跳到 setup_timer（第 5 行）", await cursorLine() === 5);
await pressOn('#code-outline-filter', { key: "ArrowUp", bubbles: true, cancelable: true });
await pressOn('#code-outline-filter', { key: "ArrowUp", bubbles: true, cancelable: true });
await waitFor(`document.querySelector('#code-outline .code-outline-item.on .code-outline-name')?.textContent === "setup_mask"`);
check("3c ↑ 循环回到末项", await Eval(`document.querySelector('#code-outline .code-outline-item.on .code-outline-name')?.textContent`) === "setup_mask");

// ---- 场景 4：无匹配空态 + Esc 清空恢复 ----
await setFilter("zzz");
await waitFor(`document.querySelector('#code-outline')?.textContent.includes('无匹配符号')`);
check("4a 无匹配空态", (await Eval(`document.querySelector('#code-outline')?.textContent.includes('无匹配符号')`)) === true);
await pressOn('#code-outline-filter', { key: "Escape", bubbles: true, cancelable: true });
await waitFor(`document.querySelectorAll('#code-outline .code-outline-item').length >= 4`);
check("4b Esc 清空恢复全量", (await rowNames()).length >= 4
  && (await Eval(`document.getElementById('code-outline-filter').value`)) === "");

// ---- 场景 5：过滤后点击条目仍跳行（委托不受影响）----
await setFilter("helper");
await waitFor(`document.querySelectorAll('#code-outline .code-outline-item').length === 1`);
await Eval(`document.querySelector('#code-outline .code-outline-item')?.click(); true`);
await waitFor(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  const s = ta.value.slice(0, ta.selectionStart);
  return (s.match(/\\n/g) || []).length + 1 === 7;
})()`);
check("5 过滤后点击条目跳行（第 7 行）", await cursorLine() === 7);

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
