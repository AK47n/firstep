// 确证（工单 code-editor-cdp-hang/01）：dirty + beforeunload 对话框被 CDP 应答后，
// 页面**完全恢复**（不只是「命令能返回」）——即产品无缺陷，挂死纯属自动化侧未应答对话框。
//
// 判据链：
//   1. 造脏（trusted 按键）→ reload → 自动 accept 对话框
//   2. 新文档就绪 + 编辑器可用（tab-code / code-viewer 在）
//   3. 标签会话重新登记（GET /api/tabs/state 或前端 fetch 一次）
//   4. 编辑器功能可用（再打开一个文件、能编辑）
//   5. 再 reload 一次（此时干净）→ 无对话框、不挂
//
// 用法：node .scratch/code-editor-cdp-hang/verify-recovery-clean.mjs
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-cdp-hang", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "guard.c"), "int main(void) { return 0; }\n");
writeFileSync(join(SAMPLE, "second.c"), "int second(void) { return 1; }\n");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};
const listTargets = async () => { try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch { return []; } };
const pageTarget = async () => (await listTargets()).find((t) => t.type === "page" && t.url.startsWith(PAGE_URL));
async function freshTab() {
  const t = await pageTarget();
  if (t) { await fetchT(`http://127.0.0.1:${CDP}/json/close/${t.id}`).catch(() => {}); await sleep(400); }
  await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(PAGE_URL)}`, 8000, { method: "PUT" }).catch(() => {});
  await sleep(1500);
  return pageTarget();
}
function conn(t) {
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let seq = 0; const pending = new Map(); const events = [];
  const open = new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) events.push({ t: Date.now(), method: m.method, params: m.params });
  };
  const cdp = (method, params = {}, timeout = 6000) => new Promise((resolve, reject) => {
    const id = ++seq;
    const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(method + " 超时"), { hung: true })); } }, timeout);
    pending.set(id, (m) => { clearTimeout(to); resolve(m); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const Eval = async (expr, timeout = 6000) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
  return { cdp, Eval, events, open, close: () => { try { ws.close(); } catch {} } };
}

let pass = 0, fail = 0;
const check = (name, ok, extra) => { log(`${ok ? "PASS" : "FAIL"} ${name}${extra !== undefined ? " [" + extra + "]" : ""}`); ok ? pass++ : fail++; };

const t = await freshTab();
const c = conn(t); await c.open;
await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
// 造脏
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) { if (await c.Eval(`!!document.querySelector('#code-tree [data-code-file="guard.c"]')`).catch(() => false)) break; await sleep(200); }
await c.Eval(`document.querySelector('#code-tree [data-code-file="guard.c"]')?.click()`);
for (let i = 0; i < 30; i++) { if (await c.Eval(`!!document.querySelector('#code-viewer .code-ta')`).catch(() => false)) break; await sleep(200); }
await c.Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0,0); return true; })()`);
for (const ch of "//x") {
  await c.cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
  await c.cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
}
await sleep(500);
const dirty = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => m.dirtyTabPaths())`);
check("前置：缓冲区已脏（guard.c）", Array.isArray(dirty) && dirty.includes("guard.c"), JSON.stringify(dirty));

// reload + 自动应答对话框
c.events.length = 0;
let accepted = false;
const watcher = setInterval(async () => {
  if (accepted) return;
  if (c.events.some((e) => e.method === "Page.javascriptDialogOpening")) {
    accepted = true;
    try { await c.cdp("Page.handleJavaScriptDialog", { accept: true }, 3000); } catch {}
  }
}, 50);
await c.cdp("Page.reload", { ignoreCache: true }, 6000);
await sleep(2500);
clearInterval(watcher);
check("reload 期间出现 beforeunload 对话框", c.events.some((e) => e.method === "Page.javascriptDialogOpening" && e.params?.type === "beforeunload"));
check("对话框已由自动化应答", accepted);

// 新文档完全可用
const ready = await c.Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`, 6000).catch((e) => "err:" + e.message);
check("reload 后新文档就绪（命令能返回）", ready === true, String(ready));
const sess = await c.Eval(`fetch('/api/state').then((r) => r.status)`, 6000).catch((e) => "err:" + e.message);
check("新文档能访问 webapp（/api/state 200）", sess === 200, String(sess));
// 编辑器功能仍可用：打开第二个文件并编辑
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) { if (await c.Eval(`!!document.querySelector('#code-tree [data-code-file="second.c"]')`).catch(() => false)) break; await sleep(200); }
await c.Eval(`document.querySelector('#code-tree [data-code-file="second.c"]')?.click()`);
for (let i = 0; i < 30; i++) { if (await c.Eval(`!!document.querySelector('#code-viewer .code-ta')`).catch(() => false)) break; await sleep(200); }
const path2 = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path)`, 6000).catch((e) => "err:" + e.message);
check("reload 后编辑器仍可打开文件", path2 === "second.c", String(path2));
const clean = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => m.dirtyTabPaths())`).catch((e) => "err:" + e.message);
check("新文档无残留脏标签", Array.isArray(clean) && clean.length === 0, JSON.stringify(clean));

// 再 reload（干净）→ 无对话框、不挂
c.events.length = 0;
await c.cdp("Page.reload", { ignoreCache: true }, 6000);
await sleep(2000);
check("第二次 reload 无对话框（干净页）", c.events.filter((e) => e.method === "Page.javascriptDialogOpening").length === 0);
const ok2 = await c.Eval("document.readyState", 5000).catch((e) => "err:" + e.message);
check("第二次 reload 不挂死", ok2 === "complete", String(ok2));

log(`\nPASS ${pass} / FAIL ${fail}`);
c.close();
process.exit(fail ? 1 : 0);
