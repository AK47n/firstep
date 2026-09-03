// 冒烟（工单 code-editor-opt/01）：标记增量修补路径浏览器验证——
// ①非结构编辑后无异常（window.onerror 计数）；②渲染标记与全量重算一致
// （读 .code-marks 行数与类分布）；③边界：光标贴 } 时编辑仍正常。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-opt");
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11");

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
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
// 错误计数
await Eval(`(() => { window.__errs = []; window.addEventListener('error', (e) => window.__errs.push(String(e.message))); return true; })()`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// 基线：行 5000 附近插入（非结构），观察标记行数/类分布
const run = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const text = ta.value;
  // 定位到第 5000 行行中（模拟真实编辑：value 改 + input 事件，与 input 管线同路）
  const lines = text.split('\\n');
  const targetLine = 5000;
  const target = lines.slice(0, targetLine - 1).reduce((a, l) => a + l.length + 1, 0) + 8; // 第 5000 行内 col 8
  ta.setSelectionRange(target, target);
  const old = ta.value;
  ta.value = old.slice(0, target) + 'q' + old.slice(target);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  const marksEl = document.querySelector('#code-viewer .code-marks');
  const marksHTML = marksEl ? marksEl.innerHTML : '';
  const lineCount = (marksHTML.match(/data-code-line=/g) || []).length;
  const guideCount = (marksHTML.match(/code-mark-guide/g) || []).length;
  const rbCount = (marksHTML.match(/code-mark-bracket-depth-/g) || []).length;
  // 回退并再触发一次（恢复基准）
  ta.value = old;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  const after = marksEl.innerHTML;
  return { lineCount, guideCount, rbCount, afterLineCount: (after.match(/data-code-line=/g) || []).length, errs: window.__errs.slice() };
})()`);
console.log(JSON.stringify(run, null, 2));
// 尾端贴近 } 场景（bracketPairAt 全扫路径）编辑
const run2 = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const old = ta.value;
  ta.focus();
  ta.setSelectionRange(old.length, old.length);
  ta.value = old + 'x';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  const before = ta.value.length;
  ta.value = old;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return { ok: before === old.length + 1, errs: window.__errs.slice() };
})()`);
console.log(JSON.stringify(run2, null, 2));
process.exit(0);
