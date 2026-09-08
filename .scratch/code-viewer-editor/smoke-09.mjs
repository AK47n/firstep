// 冒烟（code-viewer-editor/07e）：信息条初始空态折叠——用户反馈「中间那行
// 黑的空隙不需要留，直接顶满」= 未打开目录/无活动 tab 时 .code-file-path
// 空态 30px 黑带（onActiveTabChanged 从未触发，.empty 未设置）。
// 断言：激活代码栏（未开目录）→ 信息条折叠（display:none）、标签条与
// 编辑器空态提示紧贴（gap<4）；打开目录后仍折叠；打开文件后正常显示。
// 零依赖 CDP（9251）+ webapp 8000。
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");

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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
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

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ===== 初始空态：激活代码栏（未打开目录） =====
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await waitFor(`document.readyState === 'complete'`);
check("初始空态：信息条折叠（display:none）", await Eval(`
  (() => {
    const p = document.querySelector('.code-file-path');
    return p && p.classList.contains('empty')
      && getComputedStyle(p).display === 'none';
  })()`));
check("初始空态：标签条 → 编辑器空态提示紧贴（gap < 4）", await Eval(`
  (() => {
    const tabs = document.getElementById('code-tabs');
    const viewer = document.getElementById('code-viewer');
    const gap = viewer.getBoundingClientRect().top - tabs.getBoundingClientRect().bottom;
    return gap < 4;
  })()`));
check("初始空态：编辑器空态提示可见（点左侧文件…）", await Eval(`
  (() => {
    const v = document.getElementById('code-viewer');
    return !!v && v.textContent.includes('点左侧文件在编辑器中打开');
  })()`));

// ===== 打开目录后：仍折叠（无活动 tab） =====
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length >= 2`);
check("打开目录（未点文件）→ 仍折叠", await Eval(`
  document.querySelector('.code-file-path')?.classList.contains('empty')`));

// ===== 打开文件 → 信息条正常（非空态可折叠由 smoke-07 覆盖） =====
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
check("打开 main.c → 信息条折叠中（未编辑无按钮）", await Eval(`
  document.querySelector('.code-file-path')?.classList.contains('empty')`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// x\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("编辑 → 信息条出现（保存按钮在 → 非 empty）", await waitFor(`
  !document.querySelector('.code-file-path')?.classList.contains('empty')`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
