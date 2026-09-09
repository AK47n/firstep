// 修复验证（工单 code-editor-cdp-hang/01 验收项 ③/④）：
//
// 实验 D：挂死前就挂上 Page.javascriptDialogOpening 监听，事件一到立即
//         Page.handleJavaScriptDialog{accept:true} —— 若 reload 不再挂死，
//         则确认「渲染进程在等对话框应答」，且自动化侧有确定性的解。
// 实验 E：对同一 dirty 状态做 headful（非 headless）对照 —— 见脚本末尾说明：
//         headful 需要另起 Chrome（不影响 9251），本脚本只打印手工命令。
// 实验 F：Page.addScriptToEvaluateOnNewDocument 注入「自动化下不注册 beforeunload」
//         补丁后，新建文档不再有守卫 → reload 不再弹框（会话级解）。
//
// 用法：node .scratch/code-editor-cdp-hang/probe-fix-dialog.mjs
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-cdp-hang", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "guard.c"), "int main(void) { return 0; }\n");
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
// 造脏：打开文件 + trusted 按键（用户手势 = 对话框出现的必要条件）
async function makeDirty(c) {
  await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
  await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
  for (let i = 0; i < 40; i++) { if (await c.Eval(`!!document.querySelector('#code-tree [data-code-file="guard.c"]')`).catch(() => false)) break; await sleep(200); }
  await c.Eval(`document.querySelector('#code-tree [data-code-file="guard.c"]')?.click()`);
  for (let i = 0; i < 30; i++) { if (await c.Eval(`!!document.querySelector('#code-viewer .code-ta')`).catch(() => false)) break; await sleep(200); }
  await c.Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
  for (const ch of "//x") {
    await c.cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
    await c.cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
  }
  await sleep(500);
  return await c.Eval(`import('/js/ui/codeeditor.js').then((m) => ({ dirty: m.dirtyTabPaths(), active: m.getActiveTab()?.path }))`);
}

log("=== 实验 D：dialogOpening 一到就 accept ===");
{
  const t = await freshTab(); const c = conn(t); await c.open;
  log(`  脏状态：${JSON.stringify(await makeDirty(c))}`);
  // 关键：监听 dialogOpening，事件一到立即应答
  c.events.length = 0;
  let accepted = false;
  const watcher = setInterval(async () => {
    if (accepted) return;
    const hit = c.events.find((e) => e.method === "Page.javascriptDialogOpening");
    if (hit) {
      accepted = true;
      try { await c.cdp("Page.handleJavaScriptDialog", { accept: true }, 3000); log("  事件到达 → handleJavaScriptDialog 已应答"); }
      catch (e) { log("  应答失败：" + e.message); }
    }
  }, 50);
  try { await c.cdp("Page.reload", { ignoreCache: true }, 6000); log("  Page.reload OK"); } catch (e) { log("  " + e.message); }
  await sleep(2000);
  clearInterval(watcher);
  log(`  dialogOpening：${c.events.filter((e) => e.method === "Page.javascriptDialogOpening").length} 次，accepted=${accepted}`);
  try { log(`  探活：OK → ${await c.Eval("document.readyState", 5000)}`); }
  catch (e) { log(`  探活：HANG（${e.message}）`); }
  c.close();
}

log("\n=== 实验 F：addScriptToEvaluateOnNewDocument 注入守卫禁用补丁 ===");
{
  const t = await freshTab(); const c = conn(t); await c.open;
  log(`  脏状态：${JSON.stringify(await makeDirty(c))}`);
  // 会话级补丁：新文档里把 beforeunload 监听变成空操作（自动化专用）
  await c.cdp("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.addEventListener('beforeunload', (e) => { e.stopImmediatePropagation(); }, true);`,
  });
  try { await c.cdp("Page.reload", { ignoreCache: true }, 6000); log("  Page.reload OK"); } catch (e) { log("  " + e.message); }
  await sleep(1800);
  log(`  dialogOpening：${c.events.filter((e) => e.method === "Page.javascriptDialogOpening").length} 次`);
  try { log(`  探活：OK → ${await c.Eval("document.readyState", 5000)}`); }
  catch (e) { log(`  探活：HANG（${e.message}）`); }
  c.close();
}

log("\n=== 实验 G：clean（对照，应始终 OK）===");
{
  const t = await freshTab(); const c = conn(t); await c.open;
  await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
  await c.cdp("Page.reload", { ignoreCache: true }, 6000);
  await sleep(1500);
  try { log(`  探活：OK → ${await c.Eval("document.readyState", 5000)}`); } catch (e) { log(`  探活：HANG（${e.message}）`); }
  c.close();
}
log("\n结束");
