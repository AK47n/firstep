// .scratch/cdp-harness.mjs —— CDP 冒烟共用工具（工单 code-editor-cdp-hang/01 收口）
//
// 存在的理由（根因见 .scratch/code-editor-cdp-hang/issues/01-reload-renderer-hang.md）：
//   编辑器有未保存标签（tab.content !== tab.savedContent）时，`beforeunload` 退出保护
//   会让 Chrome 在 `Page.reload` / `Page.navigate` 前弹**原生 beforeunload 对话框**；
//   对话框未被应答时渲染进程卡住 —— 此后所有「渲染进程侧」CDP 命令
//   （Runtime.evaluate / DOM.* / Page.navigate）永不返回（浏览器进程侧的
//   Input.dispatchKeyEvent / Page.handleJavaScriptDialog 仍能应答，据此可与崩溃区分）。
//   这不是产品缺陷（真实浏览器里用户点「离开」即继续；对话框被应答后页面完全恢复，
//   见 verify-recovery-clean.mjs 9/9），而是自动化侧没应答对话框。
//
// 因此本模块提供两件事：
//   1. rebuildTab()  —— 每支脚本前重建标签页（clean 页 = 无脏缓冲 = 无对话框），最省事的约定；
//   2. connect()     —— 挂 `Page.javascriptDialogOpening` → 立即
//                       `Page.handleJavaScriptDialog{accept:true}` 自动应答，
//                       并给每个命令加超时守卫（挂死显式报错，不静默卡住）。
//
// 用法：
//   import { rebuildTab, connect, ensureReady } from "<相对路径>/cdp-harness.mjs";
//   await rebuildTab({ port: 9251 });                       // 每支脚本前
//   const cdp = await connect({ port: 9251 });              // cdp.cdp / cdp.Eval / cdp.close
//   await cdp.cdp("Page.reload", { ignoreCache: true });    // 对话框自动应答
//
// 零依赖：Node 内置 fetch + WebSocket（Node ≥ 22）。
export const DEFAULT_PAGE_URL = "http://127.0.0.1:8000/";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function fetchT(url, ms = 5000, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
}

export async function listTargets(port) {
  try { return await (await fetchT(`http://127.0.0.1:${port}/json/list`)).json(); }
  catch { return []; }
}

export async function pageTarget({ port, pageUrl = DEFAULT_PAGE_URL, anyPage = false }) {
  const list = await listTargets(port);
  if (!Array.isArray(list)) return null;
  const hit = list.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
  if (hit) return hit;
  return anyPage ? list.find((t) => t.type === "page") || null : null;
}

// rebuildTab：关掉现有页面标签 → 新开一个（`json/new` 必须 PUT）。返回新 target 或 null。
// 这是「每支脚本前重建标签页」约定的实现；挂死现场也可用它恢复。
export async function rebuildTab({ port, pageUrl = DEFAULT_PAGE_URL, settleMs = 1500 } = {}) {
  const t = await pageTarget({ port, pageUrl, anyPage: true });
  if (t) {
    await fetchT(`http://127.0.0.1:${port}/json/close/${t.id}`, 5000).catch(() => {});
    await sleep(400);
  }
  await fetchT(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(pageUrl)}`, 8000, { method: "PUT" }).catch(() => {});
  await sleep(settleMs);
  return pageTarget({ port, pageUrl, anyPage: true });
}

// connect：连上 page target；每个命令带超时守卫；对话框自动应答。
//   opts.port         CDP 端口（脚本各异：9251 / 9231 …）
//   opts.pageUrl      页面地址（默认 8000）
//   opts.timeoutMs    单命令超时（默认 20000，与既有 overhaul 守卫同值）
//   opts.autoDialog   是否自动应答对话框（默认 true）
//   opts.onEvent      事件回调（可选，收全部 CDP 事件）
export async function connect({
  port, pageUrl = DEFAULT_PAGE_URL, timeoutMs = 20000, autoDialog = true, onEvent,
} = {}) {
  let t = await pageTarget({ port, pageUrl });
  if (!t) t = await rebuildTab({ port, pageUrl });
  if (!t) throw new Error(`CDP 不可达或无 page target（端口 ${port}）`);

  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let seq = 0;
  const pending = new Map();
  const events = [];
  let dialogsAccepted = 0;

  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("CDP ws error")); });

  const send = (method, params = {}) => ws.send(JSON.stringify({ id: ++seq, method, params }));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); return; }
    if (msg.method) {
      events.push({ t: Date.now(), method: msg.method, params: msg.params });
      if (typeof onEvent === "function") onEvent(msg);
      // 关键：对话框一到就应答（不等调用方）
      if (autoDialog && msg.method === "Page.javascriptDialogOpening") {
        dialogsAccepted++;
        send("Page.handleJavaScriptDialog", { accept: true });
      }
    }
  };

  const cdp = (method, params = {}, timeout = timeoutMs) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const to = setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(Object.assign(new Error(`CDP 无响应（${timeout}ms）: ${method} —— 页面可能已挂死`), { hung: true, method }));
        }
      }, timeout);
      pending.set(id, (msg) => { clearTimeout(to); resolve(msg); });
      ws.send(JSON.stringify({ id, method, params }));
    });

  const Eval = async (expr, timeout) => {
    const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout);
    if (r.result?.exceptionDetails) {
      throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
    }
    return r.result?.result?.value;
  };

  const waitFor = async (expr, ms = 10000) => {
    for (let i = 0; i < ms / 200; i++) {
      try { if (await Eval(expr)) return true; } catch {}
      await sleep(200);
    }
    return false;
  };

  // 就绪判据：新文档 + 关键节点在场（脚本可传自己的表达式）
  const ready = async (expr, ms = 20000) =>
    waitFor(expr || `document.readyState === 'complete' && !!document.getElementById('tab-code')`, ms);

  return {
    ws, cdp, Eval, waitFor, ready, events, target: t,
    get dialogsAccepted() { return dialogsAccepted; },
    close: () => { try { ws.close(); } catch {} },
  };
}

// ensureReady：连上 + 就绪（常用组合）
export async function ensureReady({ port, pageUrl = DEFAULT_PAGE_URL, expr, timeoutMs = 20000, waitMs = 20000 } = {}) {
  const c = await connect({ port, pageUrl, timeoutMs });
  const ok = await c.ready(expr, waitMs);
  if (!ok) { c.close(); throw new Error("页面未就绪"); }
  return c;
}
