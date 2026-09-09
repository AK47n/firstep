// 冒烟（code-editor-refine/02 快捷键补位）：真实浏览器验证
// Ctrl+W 关标签（干净直关 / 脏 tab 弹确认——取消保留、确认关闭 / 模态开启不
// 并发截获 / 输入框聚焦仍拦截防浏览器关页）；
// Ctrl+B 侧栏开合（body 焦点切换；查找输入框聚焦不抢键）；
// 快捷键帮助弹窗含新条目。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-02");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "a.c"), "int a = 1;\n");
writeFileSync(join(SAMPLE, "b.c"), "int b = 2;\n");

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
const setText = (text) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const pressOn = (sel, opts) => Eval(`(() => {
  const el = document.querySelector(${JSON.stringify(sel)});
  if (!el) return false;
  el.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)}));
  return true;
})()`);
const tabCount = () => Eval(`document.querySelectorAll('#code-tabs .code-tab').length`);
const activeTab = () => Eval(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath ?? null`);
const collapsed = () => Eval(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') ?? null`);
const modalCount = () => Eval(`document.querySelectorAll('.ref-files-overlay').length`);
const modalTitle = () => Eval(`document.querySelector('.ref-files-overlay .ref-files-head strong')?.textContent ?? null`);

// ---- 准备：打开目录 + 两标签（a 干净 / b 改脏）----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`);
await openFile("a.c");
await openFile("b.c");
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 2`);
// 等 b.c 真的成为活动标签（openEditorFile 是 async，两次点击并发时旧请求晚到
// 不再抢活动标签——但脚本仍须等到「用户视角已落在 b.c」再改内容，否则会改到 a.c。
// 2026-09-09 第八轮实测：缺此等待时场景 2 偶发 FAIL，见工单 code-editor-cdp-hang/01）
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "b.c"`);
check("0 两标签就位", await tabCount() === 2);

// ---- 场景 1：Ctrl+W 关脏标签 → 确认（取消保留）----
await setText("int b = 999;\n");
await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelectorAll('.ref-files-overlay').length >= 1`);
check("1a 脏标签 Ctrl+W 弹确认", await modalTitle() === "关闭未保存的标签");
// 模态开启时再按 Ctrl+W：不并发截获（仍只有一个模态）
await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await new Promise((r) => setTimeout(r, 300));
check("1b 模态开启不并发弹第二个", await modalCount() === 1);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click(); true`);
await waitFor(`document.querySelectorAll('.ref-files-overlay').length === 0`);
check("1c 取消后标签保留", await tabCount() === 2);
check("1d 取消后仍脏（b 活动）", await Eval(`document.querySelector('#code-tabs .code-tab.on .code-tab-dirty') !== null`));

// ---- 场景 2：Ctrl+W 再按 → 确认关闭 ----
await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelectorAll('.ref-files-overlay').length === 1`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]')?.click(); true`);
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 1
  && document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "a.c"`);
if (await activeTab() !== "a.c") {
  console.log(JSON.stringify(await Eval(`({
    tabs: Array.from(document.querySelectorAll('#code-tabs .code-tab')).map((t) => t.dataset.tabPath + (t.classList.contains('on') ? '*' : '')),
    ta: !!document.querySelector('#code-viewer .code-ta'),
    modal: document.querySelectorAll('.ref-files-overlay').length,
  })`)));
}
check("2 确认关闭后剩 1 标签（a 活动）", await activeTab() === "a.c");

// ---- 场景 3：Ctrl+W 关干净标签（直关）----
await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 0`);
check("3 干净标签直关", await tabCount() === 0);

// ---- 场景 4：Ctrl+B 侧栏开合（body 焦点）----
check("4a 初始未收起", await collapsed() === false);
await pressOn('body', { key: "b", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === true`);
check("4b Ctrl+B 收起", await collapsed() === true);
await pressOn('body', { key: "b", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === false`);
check("4c Ctrl+B 展开", await collapsed() === false);

// ---- 场景 5：查找输入框聚焦 Ctrl+B 不抢键 ----
await Eval(`document.getElementById('code-find-input')?.focus(); true`);
await pressOn('#code-find-input', { key: "b", ctrlKey: true, bubbles: true, cancelable: true });
await new Promise((r) => setTimeout(r, 300));
check("5 输入框 Ctrl+B 不切换", await collapsed() === false);

// ---- 场景 6：编辑区聚焦 Ctrl+B 生效（VSCode 同义：编辑中也能切侧栏）----
await openFile("a.c");
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 1`);
await pressOn('#code-viewer .code-ta', { key: "b", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === true`);
check("6a 编辑区 Ctrl+B 收起", await collapsed() === true);
await pressOn('#code-viewer .code-ta', { key: "b", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed') === false`);
check("6b 编辑区 Ctrl+B 展开", await collapsed() === false);

// ---- 场景 7：输入框聚焦 Ctrl+W 仍拦截（防浏览器关页）----
await pressOn('#code-find-input', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 0`);
check("7 输入框 Ctrl+W 仍关标签（拦截保护）", await tabCount() === 0);

// ---- 场景 8：帮助弹窗新条目 ----
await Eval(`document.getElementById('btn-code-shortcuts')?.click(); true`);
const helpOk = await waitFor(`(document.body.textContent || '').includes('关闭当前标签（脏标签先确认）')
  && (document.body.textContent || '').includes('收起 / 展开右侧栏')`);
check("8 帮助弹窗含新条目", helpOk);
await Eval(`document.querySelector('.code-shortcuts-modal [data-close], .code-shortcuts-modal .modal-close')?.click(); true`);

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
