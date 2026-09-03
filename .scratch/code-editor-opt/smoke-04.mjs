// 冒烟（工单 code-editor-opt/04 整体回归）：打开 6000 行 → 逐键 → 查找 →
// 折叠 → 跳行 → 配对 → 无异常 → 三层 top 对齐；最后出深浅两主题截图。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-opt");
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11");
mkdirSync(OUT, { recursive: true });

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
const shot = async (name) => {
  const r = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(join(OUT, name), Buffer.from(r.result.data, "base64"));
};
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`(() => { window.__errs = []; window.addEventListener('error', (e) => window.__errs.push(String(e.message))); return true; })()`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// ① 文末逐键 10 次（字母 + 空格交替）+ 视口滚到底
const typed = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const view = document.getElementById('code-viewer');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  view.scrollTop = view.scrollHeight;
  const orig = ta.value;
  for (const ch of ['x', ' ', 'y', ' ', 'z', ' ', '1', ' ', 'a', ' ']) {
    ta.value = ta.value + ch;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
  const dirty = ta.value.length - orig.length;
  const gutterHl = Array.from(document.querySelectorAll('#code-viewer .code-gutter-line')).length;
  const hlCount = Array.from(document.querySelectorAll('#code-viewer .code-hl-line')).length;
  // 恢复到原内容
  ta.value = orig;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return { dirty, gutterHl, hlCount, errs: window.__errs.slice() };
})()`);
check("文末逐键 10 次无异常且脏长度正确", typed.dirty === 10 && typed.errs.length === 0, JSON.stringify(typed));

// ② 跳行（查找/折叠之前——全局状态隔离，跳行语义与 probe-jump 一致）
const jumpR = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  ce.editJumpToLine(25);
  await new Promise((r) => setTimeout(r, 100));
  const ta = document.querySelector('#code-viewer .code-ta');
  const selStart = ta.selectionStart;
  const line = ta.value.slice(0, selStart).split('\\n').length;
  const line25Text = ta.value.split('\\n')[24];
  return { selStart, line, line25Text, errs: window.__errs.slice() };
})()`);
check("跳转到 25 行", jumpR.line === 25, JSON.stringify(jumpR));

// ③ 查找（Ctrl+F 口径：setEditorFind）
const findR = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const r = ce.setEditorFind('int');
  return { total: r.total, errs: window.__errs.slice() };
})()`);
check("文件内查找命中数 > 0", findR.total > 0, JSON.stringify(findR));

// ④ 折叠（Ctrl+Shift+[ 在第 1 行折叠 f0）
const foldR = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', code: 'BracketLeft', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  await new Promise((r) => setTimeout(r, 150));
  const ph = document.querySelectorAll('#code-viewer .code-gutter-ph').length;
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: ']', code: 'BracketRight', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  await new Promise((r) => setTimeout(r, 150));
  return { ph, errs: window.__errs.slice() };
})()`);
check("折叠/展开无异常", foldR.errs.length === 0, JSON.stringify(foldR));

// ⑤ 三层 top 对齐（当前视口）
const align = await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const tops = (sel) => Array.from(box.querySelectorAll(sel)).map((el) => Math.round(el.getBoundingClientRect().top * 2) / 2).sort((a, b) => a - b);
  const g = tops('.code-gutter-line'), h = tops('.code-hl-line'), m = tops('.code-marks-line');
  const near = (a, b) => Math.abs(a - b) <= 1;
  const bad = [];
  for (const t of h) if (!g.some((x) => near(x, t))) bad.push('hl-orphan');
  for (const t of g) if (!h.some((x) => near(x, t))) bad.push('gut-orphan');
  for (const t of m) if (!h.some((x) => near(x, t))) bad.push('marks-orphan');
  return { bad, errs: window.__errs.slice() };
})()`);
check("三层 top 集合 1:1", align.bad.length === 0 && align.errs.length === 0, JSON.stringify(align));

// ⑥ 深浅主题截图
for (const theme of ["light", "dark"]) {
  await Eval(`document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)}); localStorage.setItem('firstep.theme', ${JSON.stringify(theme)}); true`);
  await new Promise((r) => setTimeout(r, 400));
  await shot("final-" + theme + ".png");
}
console.log("总计: pass=" + passed + " fail=" + failed);
process.exit(failed ? 1 : 0);
