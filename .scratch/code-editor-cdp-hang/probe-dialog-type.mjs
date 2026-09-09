// 确证（工单 code-editor-cdp-hang/01）：
//   假设 —— 挂死 = 编辑器 beforeunload 退出保护在 **headless 下弹出的原生对话框**
//   把导航卡住（渲染进程随后对 Runtime.evaluate 永不响应）。
//
// 三组对照（同一支脚本内、每组建新标签页）：
//   A dirty        —— 打开文件 + 改成脏内容（不保存）→ reload（预期：dialogOpening + 挂死）
//   B dirty+解绑   —— 同上，但 reload 前 removeEventListener 掉 beforeunload（预期：不挂）
//   C clean        —— 打开文件不改 → reload（预期：不挂）
// 并打印 dialogOpening 的 type/message（确认是否 beforeunload 型）。
//
// 用法：node .scratch/code-editor-cdp-hang/probe-dialog-type.mjs
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
    const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(method + " 超时（" + timeout + "ms）"), { hung: true })); } }, timeout);
    pending.set(id, (m) => { clearTimeout(to); resolve(m); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const Eval = async (expr, timeout = 6000) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
  return { cdp, Eval, events, open, close: () => { try { ws.close(); } catch {} } };
}

async function openAndEdit(c, { edit, unbind }) {
  await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
  await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
  for (let i = 0; i < 40; i++) { if (await c.Eval(`!!document.querySelector('#code-tree [data-code-file="guard.c"]')`).catch(() => false)) break; await sleep(200); }
  await c.Eval(`document.querySelector('#code-tree [data-code-file="guard.c"]')?.click()`);
  for (let i = 0; i < 30; i++) { if (await c.Eval(`!!document.querySelector('#code-viewer .code-ta')`).catch(() => false)) break; await sleep(200); }
  if (edit) {
    // 走真实输入路径（trusted 按键），确保模型真的变脏
    await c.Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
    for (const ch of "//x") {
      await c.cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
      await c.cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
    }
    await sleep(500);
  }
  if (unbind) {
    // 解绑 beforeunload（用同一个 handler 引用不可得 → 改用捕获阶段 stopImmediatePropagation 拦一层）
    await c.Eval(`(() => {
      window.__guardBlocked = true;
      window.addEventListener('beforeunload', (e) => { e.stopImmediatePropagation(); }, true);
      return true;
    })()`);
  }
  return await c.Eval(`import('/js/ui/codeeditor.js').then((m) => {
    const t = m.getActiveTab();
    return { dirty: !!(t && t.content !== t.savedContent), len: t ? t.content.length : -1, saved: t ? t.savedContent.length : -1 };
  })`).catch((e) => "err:" + e);
}

const GROUPS = [
  { name: "A dirty", edit: true, unbind: false },
  { name: "B dirty+捕获阶段拦截", edit: true, unbind: true },
  { name: "C clean", edit: false, unbind: false },
];
for (const g of GROUPS) {
  log(`\n=== ${g.name} ===`);
  const t = await freshTab();
  if (!t) { log("  无 target"); continue; }
  const c = conn(t); await c.open;
  const st = await openAndEdit(c, g);
  log(`  编辑状态：${JSON.stringify(st)}`);
  try { await c.cdp("Page.reload", { ignoreCache: true }, 6000); log("  Page.reload OK"); } catch (e) { log("  " + e.message); }
  await sleep(1500);
  const dialogs = c.events.filter((e) => e.method === "Page.javascriptDialogOpening");
  for (const d of dialogs) log(`  dialogOpening: type=${d.params?.type} message=${JSON.stringify(d.params?.message)} url=${d.params?.url}`);
  try { log(`  探活：OK → ${await c.Eval("document.readyState", 5000)}`); }
  catch (e) { log(`  探活：HANG（${e.message}）  ${dialogs.length ? "（本次有对话框事件）" : "（本次无对话框事件）"}`); }
  c.close();
}
log("\n结束");
