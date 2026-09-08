// 诊断（code-ide-flow/02）：复现 smoke 失败——查看 check 全链路状态
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-flow", "sample-proj");

const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), "int main(void){ return 0; }\n", "utf8");
  writeFileSync(join(SAMPLE, "src", "app.h"), "#pragma once\n", "utf8");
};
resetSample();

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"));
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
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
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

await cdp("Page.navigate", { url: pageUrl });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
await Eval(`localStorage.clear()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
console.log("树出现:", await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length > 0`));
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await new Promise((r) => setTimeout(r, 800));
console.log("tab 打开:", await Eval(`document.querySelector('#code-tabs .code-tab')?.dataset.tabPath`));
console.log("ta 内容:", await Eval(`document.querySelector('#code-viewer .code-ta')?.value`));

// 外部写盘
writeFileSync(join(SAMPLE, "main.c"), "int main(void){ return 42; }\n", "utf8");
writeFileSync(join(SAMPLE, "src", "oled.c"), "// oled\n", "utf8");

// 调 check（不经 tab 钩子，直接看函数行为）
console.log("check 返回值:", await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges().then(() => 'done'))`));
await new Promise((r) => setTimeout(r, 1500));
console.log("ta 内容(期望 42):", await Eval(`document.querySelector('#code-viewer .code-ta')?.value`));
console.log("toast:", await Eval(`[...document.querySelectorAll('#toast-root .toast-text')].map(t=>t.textContent)`));
console.log("树徽章:", await Eval(`[...document.querySelectorAll('#code-tree .code-tree-badge')].map(b=>b.className+'/'+b.closest('[data-code-file]')?.dataset.codeFile)`));
console.log("localStorage 基线:", await Eval(`localStorage.getItem('firstep.codeBaseline')?.slice(0, 300)`));
// 再 check 一次
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges().then(() => 'done'))`);
await new Promise((r) => setTimeout(r, 1200));
console.log("二次 check 后 ta:", await Eval(`document.querySelector('#code-viewer .code-ta')?.value`));
console.log("二次 toast:", await Eval(`[...document.querySelectorAll('#toast-root .toast-text')].map(t=>t.textContent)`));
console.log("二次树徽章:", await Eval(`[...document.querySelectorAll('#code-tree .code-tree-badge')].map(b=>b.className+'/'+b.closest('[data-code-file]')?.dataset.codeFile)`));
process.exit(0);
