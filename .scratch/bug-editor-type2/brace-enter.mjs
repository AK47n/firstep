// 验证：`{` 自动闭合后回车 → 展开为 `{\n    \n}`（中间行缩进 4 空格）
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9252;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "bug-editor-type2", "sample3");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "void beep_beep(uint woxiangyaoshuijiao)\n");
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
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
  for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); }
  return false;
};
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) { try { if (await Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break; } catch {} await new Promise((r) => setTimeout(r, 300)); }
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
const out = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  await ce.openEditorFile('main.c');
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const tab = ce.getActiveTab();
  ta.focus();
  // 光标移到第 1 行行尾（右括号后）
  const p1 = ta.value.indexOf('\\n');
  ta.setSelectionRange(p1, p1);
  // 键入左大括号：keydown 拦截 → bracketOpen 自动闭合
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '{', bubbles: true, cancelable: true }));
  const afterBrace = { model: tab.content, sel: ta.selectionStart };
  // 回车：keydown 拦截 → indentOnEnter
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  const afterEnter = {
    model: tab.content,
    lines: tab.content.split('\\n'),
    sel: ta.selectionStart,
    caretModel: ce.editorCaretModelPos(),
    hl: Array.from(box.querySelectorAll('.code-hl-line')).map((el) => el.textContent),
  };
  return { afterBrace, afterEnter };
})()`);
console.log(JSON.stringify(out, null, 2));
const c = {
  a: out.afterBrace.model.includes("{}"),
  b: out.afterBrace.sel === out.afterBrace.model.indexOf("{}") + 1,
  c: out.afterEnter.model === "void beep_beep(uint woxiangyaoshuijiao){\n    \n}\n",
  d: out.afterEnter.lines[1] === "    ",
  e: out.afterEnter.lines[2] === "}",
  f: out.afterEnter.sel === 45,
  g: out.afterEnter.caretModel.line === 2,
  h: out.afterEnter.caretModel.col === 5,
  i: out.afterEnter.hl[1] === "    ",
  j: out.afterEnter.hl[2] === "}",
};
console.log("checks:", JSON.stringify(c));
const flowA = c.a && c.b && c.c && c.d && c.e && c.f && c.g && c.h && c.i && c.j;
const flowB = await Eval(`(async () => {
  const { indentOnEnter } = await import('/js/fx/codeeditor.js');
  const r = indentOnEnter('{}', 1, 1);   // 截图现场：左大括号独占一行后回车
  return r.value === '{\\n    \\n}' && r.start === 6 && r.end === 6;
})()`);
console.log("flowA(回车后`{`跟随行内) =", flowA, " flowB(`{`独占行回车) =", flowB);
const ok = flowA && flowB;
console.log(ok ? "PASS 大括号回车自动缩进展开" : "FAIL 大括号回车行为不符");
process.exit(ok ? 0 : 1);
