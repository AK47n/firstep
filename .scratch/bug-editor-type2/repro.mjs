// 复现：代码编辑器在第 2 行（行首）连打 4 个字符，观察模型/窗口/高亮层是否错行反转
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9252;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "bug-editor-type2", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "int line1;",
  "int line2;",
  "int line3;",
  "int line4;",
  "int line5;",
].join("\n"));

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
if (!page) { console.error("未找到页面 target"); process.exit(1); }
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

await Eval(`window.__repro = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__repro && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
console.log("opening code viewer...");
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
console.log("opened, waiting tree...");
const treeOk = await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
console.log("treeOk =", treeOk);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('main.c'))`);
const taOk = await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
console.log("taOk =", taOk);
if (!treeOk || !taOk) process.exit(2);

const out = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const tab = ce.getActiveTab();
  const model0 = tab.content;
  const snap = (tag) => {
    const lines = tab.content.split('\\n');
    const hl = Array.from(box.querySelectorAll('.code-hl-line')).map((el) => el.textContent);
    return { tag, model: tab.content, modelLines: lines,
      ta: ta.value, taSelStart: ta.selectionStart, taSelEnd: ta.selectionEnd,
      winInfoStart: (() => { try { return ce.editorCaretModelPos(); } catch { return null; } })(),
      hlLines: hl };
  };
  const log = [snap('初始')];
  ta.focus();
  // 光标定位到第 2 行行首（窗口内偏移 = 第一个换行符之后）
  let p = ta.value.indexOf('\\n') + 1;
  ta.setSelectionRange(p, p);
  log.push(snap('定位第2行行首'));
  for (const ch of ['a', 'b', 'c', 'd']) {
    p = ta.selectionStart;
    ta.value = ta.value.slice(0, p) + ch + ta.value.slice(p);
    ta.setSelectionRange(p + 1, p + 1);
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    log.push(snap('输入 ' + ch));
  }
  return { model0, log, savedOk: tab.content !== model0 };
})()`);

console.log(JSON.stringify(out, null, 2));
process.exit(0);
