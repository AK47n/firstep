// 冒烟（code-viewer-editor/07c）：信息条 .code-file-path 空态折叠——
// 用户反馈「代码第一行上面有一行啥也没有的空行」= 空态信息条 30px 占位。
// 断言：未编辑 .c → 折叠（display none，代码区紧贴标签条）；编辑脏 → 信息条
// 出现（保存按钮可见）；保存成功 → 重新折叠；.md 预览态 → 出现（编辑源码）；
// 切编辑态 →「返回预览」出现仍显示；回预览 → 仍显示；关闭全部 tab → 折叠。
// 零依赖 CDP（9251）+ webapp 8000。
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");

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

// 确定性起点
writeFileSync(MAIN_C, "int base = 1;\n", "utf8");

await Eval(`localStorage.removeItem('firstep.codeSideCollapsed'); window.__smokeMarker = 1`);
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
const barDisplay = () => Eval(`
  (() => {
    const p = document.querySelector('.code-file-path');
    return p ? getComputedStyle(p).display : 'gone';
  })()`);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length >= 2`);

// ===== 未编辑普通 .c → 信息条折叠（不留 30px 空行） =====
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
check("打开 main.c（未编辑）→ .code-file-path 折叠", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    return p && p.classList.contains('empty')
      && getComputedStyle(p).display === 'none';
  })()`));
check("折叠后代码区紧贴标签条（无 30px 空隙）", await Eval(`
  (() => {
    const tabs = document.getElementById('code-tabs');
    const viewer = document.getElementById('code-viewer');
    const gap = viewer.getBoundingClientRect().top - tabs.getBoundingClientRect().bottom;
    return gap < 4;
  })()`));

// ===== 编辑 → 脏 → 保存按钮出现 → 信息条出现 =====
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// 改了\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("编辑 → 脏点（保存按钮可见 → 信息条不折叠）", await waitFor(`
  (async () => {
    const save = document.getElementById('btn-code-save');
    await new Promise((r) => setTimeout(r, 0));
    return !!save && !save.classList.contains('hidden')
      && !document.querySelector('.code-file-path').classList.contains('empty');
  })()`));

// ===== Ctrl+S 保存成功 → 脏清 → 重新折叠 =====
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("保存成功 → 信息条重新折叠", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    return p && p.classList.contains('empty')
      && getComputedStyle(p).display === 'none';
  })()`));

// ===== .md 预览态 → 信息条出现（编辑源码）→ 两态往返均显示 =====
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer [data-md-line]')`);
check(".md 预览态 → 信息条出现（编辑源码按钮）", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    const b = document.getElementById('code-edit-md');
    return b && !b.classList.contains('hidden')
      && !p.classList.contains('empty');
  })()`));
await Eval(`document.getElementById('code-edit-md')?.click()`);
check(".md 编辑态 → 信息条仍显示（返回预览）", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    const b = document.getElementById('code-back-preview');
    return b && !b.classList.contains('hidden')
      && !p.classList.contains('empty');
  })()`));
await Eval(`document.getElementById('code-back-preview')?.click()`);
check("返回预览 → 信息条仍显示（编辑源码）", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    const b = document.getElementById('code-edit-md');
    return b && !b.classList.contains('hidden')
      && !p.classList.contains('empty');
  })()`));

// ===== 关闭全部 tab → 折叠 =====
await Eval(`document.querySelector('#code-tabs .code-tab.on .code-tab-close')?.click()`);
check("关闭活动 md tab（预览态非脏）→ 信息条折叠", await waitFor(`
  (() => {
    const p = document.querySelector('.code-file-path');
    return p && p.classList.contains('empty')
      && getComputedStyle(p).display === 'none'
      && !document.querySelector('#code-viewer [data-md-line]');
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
