// 冒烟（工单 code-write-guard/01-02）：反向写盘保护——代码栏（目录=生成上下文）
// 有未保存编辑时 guardCodeTabWrite 弹两键确认；「保存全部并继续」→ 落盘返回
// true + 脏点清除；「取消」→ 返回 false + 编辑保留；无脏 → 直通 true 零弹窗。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）；文件/保存接口
// window.fetch 层 mock（app.js apiGet/apiPost 走全局 fetch 单源）。
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"))
  || targets.find((t) => t.type === "page");
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

let ready = false;
// 先导航到应用页（上次会话可能停在别的页面），再刷新加载最新静态文件
await cdp("Page.navigate", { url: pageUrl });
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- mock：目录打开 / 文件读取 / 保存计数（apiGet/apiPost → window.fetch）----
const MAIN_SRC = ["int x = 0;", "void setup(void) {", "  x = 1;", "}", "int main(void) {", "  return 0;", "}"].join("\n");
const mocksOk = await Eval(`(async () => {
  const msrc = ${JSON.stringify(MAIN_SRC)};
  const json = (o) => new Response(JSON.stringify(o), { status: 200,
    headers: { 'Content-Type': 'application/json' } });
  window.__saveCount = 0;
  window.fetch = async (url, opts) => {
    const p = new URL(String(url), location.origin);
    if (p.pathname === '/api/code/open') {
      const body = JSON.parse((opts && opts.body) || '{}');
      return json({ root: body.dir, files: [{ path: 'main.c', size_bytes: msrc.length }] });
    }
    if (p.pathname === '/api/code/file') {
      return json({ path: p.searchParams.get('path'), size_bytes: msrc.length,
        content: msrc, outline: [], mtime_ns: '123', utf8: true });
    }
    if (p.pathname === '/api/code/save') {
      window.__saveCount++;
      return json({ path: 'main.c', size_bytes: msrc.length, mtime_ns: '124', outline: [] });
    }
    return new Response(null, { status: 404 });
  };
  return true;
})()`);
check("mock 安装成功", mocksOk === true);

// ---- 建立同目录上下文：setMainCDiskContext + openCodeViewer（真实入口）----
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
const ctxSet = await Eval(`(async () => {
  await import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext('D:/tmp/fakeproj'));
  await import('/js/ui/codeview.js').then((m) => m.openCodeViewer('D:/tmp/fakeproj'));
  await new Promise((r) => setTimeout(r, 200));
  await document.querySelector('#code-tree [data-code-file="main.c"]').click();
  await new Promise((r) => setTimeout(r, 200));
  return true;
})()`);
check("上下文 + 目录 + 打开 main.c", ctxSet === true);

// ---- 改脏：编辑内容 → 脏点；guard 弹确认 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\nint extra = 1;';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
const dirty0 = await Eval(`document.querySelectorAll('#code-tabs .code-tab-dirty').length`);
check("编辑后出现脏点", dirty0 === 1, "dirty=" + dirty0);

await Eval(`(async () => {
  const m = await import('/js/ui/code-write-guard.js');
  window.__guardP = m.guardCodeTabWrite('测试动作');
})()`);
for (let i = 0; i < 40; i++) {
  const shown = await Eval(`!!document.querySelector('[data-confirm-ok]')`);
  if (shown) break;
  await new Promise((r) => setTimeout(r, 150));
}
const modalState = await Eval(`(() => {
  const m = document.querySelector('.confirm-modal');
  return { shown: !!m,
    ok: document.querySelector('[data-confirm-ok]') ? document.querySelector('[data-confirm-ok]').textContent : null,
    cancel: document.querySelector('[data-confirm-cancel]') ? document.querySelector('[data-confirm-cancel]').textContent : null,
    message: m ? m.textContent : null };
})()`);
check("守卫弹确认（两键文案）", modalState.shown === true
  && modalState.ok === "保存全部并继续" && modalState.cancel === "取消",
  JSON.stringify({ ok: modalState.ok, cancel: modalState.cancel }));
check("确认文案含动作名 + N 文件", !!modalState.message && modalState.message.includes("『测试动作』")
  && modalState.message.includes("1 个文件未保存"), "msg=" + String(modalState.message || "").slice(0, 60));

// ---- 点「保存全部并继续」→ 落盘 + true + 脏点清除 ----
await Eval(`document.querySelector('[data-confirm-ok]').click()`);
const confirmResult = await Eval(`(async () => {
  const ok = await window.__guardP;
  return { ok, saves: window.__saveCount,
    dirty: document.querySelectorAll('#code-tabs .code-tab-dirty').length,
    modalClosed: !document.querySelector('[data-confirm-ok]') };
})()`);
check("确认 → 返回 true + 保存 1 次", confirmResult.ok === true && confirmResult.saves === 1, JSON.stringify({ ok: confirmResult.ok, saves: confirmResult.saves }));
check("确认 → 脏点清除 + 模态已关", confirmResult.dirty === 0 && confirmResult.modalClosed === true);

// ---- 再改脏 → 取消路径：false + 编辑保留 + 不保存 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\nint keep = 2;';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`(async () => {
  const m = await import('/js/ui/code-write-guard.js');
  window.__guardP2 = m.guardCodeTabWrite('测试动作');
})()`);
for (let i = 0; i < 40; i++) {
  const shown = await Eval(`!!document.querySelector('[data-confirm-cancel]')`);
  if (shown) break;
  await new Promise((r) => setTimeout(r, 150));
}
await Eval(`document.querySelector('[data-confirm-cancel]').click()`);
const cancelResult = await Eval(`(async () => {
  const ok = await window.__guardP2;
  return { ok, saves: window.__saveCount,
    dirty: document.querySelectorAll('#code-tabs .code-tab-dirty').length,
    hasKeep: document.querySelector('#code-viewer .code-ta').value.includes('int keep = 2;') };
})()`);
check("取消 → 返回 false + 不保存", cancelResult.ok === false && cancelResult.saves === 1, JSON.stringify(cancelResult));
check("取消 → 编辑保留（脏点 + 内容在）", cancelResult.dirty === 1 && cancelResult.hasKeep === true);

// ---- 清脏（内容改回已保存版）→ 无脏直通 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value.split('\\nint keep = 2;')[0];
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
const pass = await Eval(`(async () => {
  const ok = await import('/js/ui/code-write-guard.js').then((m) => m.guardCodeTabWrite('测试动作'));
  return { ok, modal: !!document.querySelector('[data-confirm-ok]') };
})()`);
check("无脏 → 直通 true 零弹窗", pass.ok === true && pass.modal === false, JSON.stringify(pass));

// ---- 非上下文直通：代码栏目录 ≠ 生成上下文时，即使有脏也不拦（评审整改补齐）----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\nint off = 3;';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
const offRes = await Eval(`(async () => {
  await import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext('D:/tmp/other'));
  const before = window.__saveCount;
  const ok = await import('/js/ui/code-write-guard.js').then((m) => m.guardCodeTabWrite('测试动作'));
  return { ok, saves: window.__saveCount, modal: !!document.querySelector('[data-confirm-ok]'),
    dirty: document.querySelectorAll('#code-tabs .code-tab-dirty').length, before };
})()`);
check("非上下文 + 脏 → 直通 true 零弹窗零保存", offRes.ok === true && offRes.modal === false
  && offRes.saves === offRes.before && offRes.dirty === 1, JSON.stringify(offRes));
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext('D:/tmp/fakeproj'))`);

console.log(failed ? "FAIL " + failed + " 项" : "ALL PASS");
process.exit(failed ? 1 : 0);
