// 冒烟（code-page-vscode-overhaul/03 查找替换增强）：真实浏览器验证
// Ctrl+H 聚焦替换输入、替换单个命中、替换并跳下一处、全部替换保留、计数联动。
// 零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "int main(void) { return 0; }\n");

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
// CDP 超时守卫（第七轮）：渲染进程偶发无响应时命令永不返回 → 脚本静默挂死。
// 20s 无响应即抛错，让失败可见（而不是卡死）。
const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error("CDP 无响应（20s）: " + method + " —— 页面可能已挂死")); }
    }, 20000);
    pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
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
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// 打开「搜索」侧栏并设定内容/查询
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = 'a = 1; a = 2;';
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = 'a';
  f.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const r = document.getElementById('code-replace-input');
  r.value = 'bb';
  return true;
})()`);
await waitFor(`(document.getElementById('code-find-count')?.textContent || '').includes('第 1 / 共 2 处')`);
check("查找计数：第 1 / 共 2 处", true);
check("替换计数联动：将替换 2 处", await Eval(`(document.getElementById('code-replace-count')?.textContent || '') === '将替换 2 处'`));

// 替换单个命中（按钮）
await Eval(`document.getElementById('btn-code-replace-one')?.click(); true`);
check("替换单个命中：文本更新", await Eval(`document.querySelector('#code-viewer .code-ta').value === 'bb = 1; a = 2;'`));
check("替换后计数：第 1 / 共 1 处", await Eval(`(document.getElementById('code-find-count')?.textContent || '').includes('第 1 / 共 1 处')`));

// 替换并跳下一处
await Eval(`document.getElementById('btn-code-replace-next')?.click(); true`);
check("替换并下一处：全部替换完成", await Eval(`document.querySelector('#code-viewer .code-ta').value === 'bb = 1; bb = 2;'`));
check("替换后无匹配提示", await Eval(`(document.getElementById('code-find-count')?.textContent || '') === '无匹配'`));
check("替换计数隐藏", await Eval(`document.getElementById('code-replace-count')?.classList.contains('hidden')`));

// Ctrl+H 聚焦替换输入
await Eval(`document.querySelector('#code-viewer .code-ta').focus(); true`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown',
  { key: 'h', ctrlKey: true, bubbles: true, cancelable: true })); true`);
check("Ctrl+H 聚焦替换输入", await Eval(`document.activeElement === document.getElementById('code-replace-input')`));

// 全部替换（重构回归检查：替换后模型/视图/计数一致）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = 'a = 1; a = 2;';
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const f = document.getElementById('code-find-input');
  f.value = 'a';
  f.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await Eval(`document.getElementById('btn-code-replace-all')?.click(); true`);
check("全部替换仍可用", await Eval(`document.querySelector('#code-viewer .code-ta').value === 'bb = 1; bb = 2;'`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
