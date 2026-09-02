// 冒烟（工单 code-editor-shortcut-help/01）：状态栏「快捷键」按钮 → 帮助弹窗
// 三路关闭（Esc / × / 遮罩）+ 内容齐全（三组标题 + Ctrl+Shift+[ 键帽 + 关闭后
// 焦点还给按钮）。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-shortcut-help", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
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

await Eval(`window.__smokeMarker = 1; true`);
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

// 打开目录（按钮存在性不依赖目录，但目录让状态栏完整呈现——与真实使用一致）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);

// ================= 按钮存在 + 点击弹出 =================
check("状态栏「快捷键」按钮存在（#btn-code-shortcuts）", await Eval(
  `!!document.getElementById('btn-code-shortcuts')`));
await Eval(`document.getElementById('btn-code-shortcuts')?.click()`);
check("点击 → 帮助弹窗出现", await waitFor(
  `!!document.querySelector('.code-shortcuts-overlay .code-shortcuts-modal')`));

// ================= 内容齐全 =================
const contentText = await Eval(
  `document.querySelector('.code-shortcuts-modal')?.innerText || ''`);
check("标题「键盘快捷键」+ 三组标题", contentText.includes("键盘快捷键")
  && contentText.includes("编辑") && contentText.includes("查找") && contentText.includes("视图"));
check("键帽 Ctrl+Shift+[ 渲染且说明齐全", await Eval(`
  (() => {
    const m = document.querySelector('.code-shortcuts-modal');
    return !!m && m.querySelector('.code-kbd') !== null
      && document.querySelector('.code-shortcuts-modal').innerText.includes('折叠光标所在代码块');
  })()`));

// ================= Esc 关闭（焦点回按钮） =================
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
check("Esc → 弹窗关闭", await waitFor(
  `!document.querySelector('.code-shortcuts-overlay')`));
check("关闭后焦点回到「快捷键」按钮", await Eval(
  `document.activeElement === document.getElementById('btn-code-shortcuts')`));

// ================= × 关闭 =================
await Eval(`document.getElementById('btn-code-shortcuts')?.click()`);
await waitFor(`!!document.querySelector('.code-shortcuts-overlay')`);
await Eval(`document.querySelector('.code-shortcuts-close')?.click()`);
check("× 按钮 → 弹窗关闭", await waitFor(
  `!document.querySelector('.code-shortcuts-overlay')`));

// ================= 遮罩点击关闭 =================
await Eval(`document.getElementById('btn-code-shortcuts')?.click()`);
await waitFor(`!!document.querySelector('.code-shortcuts-overlay')`);
await Eval(`document.querySelector('.code-shortcuts-overlay')?.click()`);
check("点击遮罩 → 弹窗关闭", await waitFor(
  `!document.querySelector('.code-shortcuts-overlay')`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
