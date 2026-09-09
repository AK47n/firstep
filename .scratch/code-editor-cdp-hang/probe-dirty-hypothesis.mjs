// 定位（工单 code-editor-cdp-hang/01）：挂死是否与「编辑器有未保存修改（dirty）」有关？
//
// 变体（每个变体：先重建标签页 → 造状态 → 探活 reload）：
//   clean       —— 打开文件、不编辑 → reload
//   dirty       —— 打开文件、编辑（不保存）→ reload      ← 触发 beforeunload 拦截
//   dirty_saved —— 打开文件、编辑、保存 → reload
//   dirty_keep  —— 编辑后 reload（保留 dirty），第二轮再 reload
//
// 用法：node .scratch/code-editor-cdp-hang/probe-dirty-hypothesis.mjs
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync } from "node:fs";
import { writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-cdp-hang", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "dirty.c"), "int main(void) { return 0; }\n");
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
  let seq = 0; const pending = new Map();
  const open = new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (method, params = {}, timeout = 6000) => new Promise((resolve, reject) => {
    const id = ++seq;
    const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(method + " 超时"), { hung: true })); } }, timeout);
    pending.set(id, (m) => { clearTimeout(to); resolve(m); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const Eval = async (expr, timeout = 6000) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
  return { cdp, Eval, open, close: () => { try { ws.close(); } catch {} } };
}

async function setup(c, variant) {
  await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
  await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
  for (let i = 0; i < 40; i++) { if (await c.Eval(`!!document.querySelector('#code-tree [data-code-file="dirty.c"]')`).catch(() => false)) break; await sleep(200); }
  await c.Eval(`document.querySelector('#code-tree [data-code-file="dirty.c"]')?.click()`);
  for (let i = 0; i < 30; i++) { if (await c.Eval(`!!document.querySelector('#code-viewer .code-ta')`).catch(() => false)) break; await sleep(200); }
  if (variant !== "clean") {
    await c.Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.value = 'int main(void) { return 42; }\\n'; ta.setSelectionRange(0,0); ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return true; })()`);
    await sleep(400);
  }
  if (variant === "dirty_saved") {
    await c.cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "s", code: "KeyS", windowsVirtualKeyCode: 83, nativeVirtualKeyCode: 83 });
    await c.cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "s", code: "KeyS", windowsVirtualKeyCode: 83, nativeVirtualKeyCode: 83 });
    await sleep(1200);
  }
  const state = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => {
    const t = m.getActiveTab();
    return { path: t && t.path, dirty: !!(t && t.dirty), len: t ? t.content.length : -1 };
  })`).catch((e) => "err:" + e);
  return state;
}

const VARIANTS = ["clean", "dirty", "dirty_saved"];
for (const variant of VARIANTS) {
  log(`\n=== 变体 ${variant} ===`);
  const t = await freshTab();
  if (!t) { log("  无 target"); continue; }
  const c = conn(t); await c.open;
  const state = await setup(c, variant);
  log(`  状态：${JSON.stringify(state)}`);
  const t0 = Date.now();
  let reloadOk = false, reloadMs = 0;
  try { await c.cdp("Page.reload", { ignoreCache: true }, 6000); reloadOk = true; reloadMs = Date.now() - t0; }
  catch (e) { log(`  Page.reload ${e.message}`); }
  if (reloadOk) log(`  Page.reload ok ${reloadMs}ms`);
  await sleep(1500);
  try {
    const v = await c.Eval("document.readyState", 6000);
    log(`  reload 后探活：OK → ${v}   ${Date.now() - t0}ms`);
  } catch (e) {
    log(`  reload 后探活：HANG（${e.message}）→ 该变体复现挂死`);
  }
  c.close();
}
log("\n结束");
