// 冒烟（code-editor-vscode-polish/05）：选中词高亮——
// 光标移入「main」→ 全文同词 2 处 .code-mark-word（main_c 不算词边界命中）→
// 光标移到符号/空白 → 标记消失 → 与查找高亮并存互不覆盖。零写库；CDP 9251。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "int main(void) {",
  "    return 0;",
  "}",
  "int main_c = 1;",
  "int main(void) {",
  "    return 0;",
  "}",
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

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer') && !!document.getElementById('code-tabs')`);
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
check("打开 main.c → 三明治就绪", await waitFor(`
  !!document.querySelector('#code-viewer .code-ta')`));

// ================= 光标移入 main → 2 处同词标记 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const pos = ta.value.indexOf('main') + 2;   // 第一个 main 词内
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return true;
})()`);
check("光标在 main 内 → .code-mark-word 2 处（main_c 不算）", await waitFor(`
  document.querySelectorAll('#code-viewer .code-mark-word').length === 2`));

// ================= 光标移开 → 标记消失 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('{'), ta.value.indexOf('{'));
  // 在 '{' 上（前为空格后为 ')' 类符号）——不成词
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return true;
})()`);
check("光标移到 '{' 符号位 → 选中词标记消失", await waitFor(`
  document.querySelectorAll('#code-viewer .code-mark-word').length === 0`));

// ================= 与查找高亮并存 =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.value = 'main';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("查找 main → 命中 1 current + 2 hit（子串含 main_c），词标记 0", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return box.querySelectorAll('.code-mark-current').length === 1
      && box.querySelectorAll('.code-mark-hit').length === 2
      && box.querySelectorAll('.code-mark-word').length === 0;
  })()`));
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  return true;
})()`);
check("收尾 Esc → 查找标记清除（词标记照常跟随光标）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !box.querySelector('.code-mark-current') && !box.querySelector('.code-mark-hit');
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
