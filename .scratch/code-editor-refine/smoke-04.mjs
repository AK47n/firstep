// 冒烟（code-editor-refine/04 括号彩虹）：真实浏览器验证
// 嵌套括号按深度着色（深度 0..3 背景色两两不同）；深浅主题各可见；
// 字符串/注释内假括号不着色；未配对不输出（txt 全无、md 门控内生效）；
// 光标对描边（.code-mark-bracket）仍优先。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-04");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "nest.c"), [
  "/* comment ( fake */",
  "void f(void) {",
  "  if (1) {",
  "    while (2) {",
  '      char s[] = "{ fake";',
  "      x();      // ( fake",
  "    }",
  "  }",
  "}",
  "",
].join("\n"));
writeFileSync(join(SAMPLE, "note.txt"), "{ ( [ } ) ]\n");
writeFileSync(join(SAMPLE, "readme.md"), "# 标题 { 正文 }\n");

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

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
const openFile = (name) => Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
const depthSpans = (cls) => Eval(`document.querySelectorAll('#code-viewer .code-marks .code-mark-${cls}').length`);
const lineSpans = (lineNo) => Eval(`document.querySelector('#code-viewer .code-marks [data-code-line="${lineNo}"]')?.querySelectorAll('.code-mark-bracket-depth-0,.code-mark-bracket-depth-1,.code-mark-bracket-depth-2,.code-mark-bracket-depth-3,.code-mark-bracket-depth-4,.code-mark-bracket-depth-5,.code-mark-bracket-depth-6,.code-mark-bracket-depth-7').length ?? -1`);
const bgOf = (cls) => Eval(`(() => {
  const el = document.querySelector('#code-viewer .code-marks .code-mark-${cls}');
  return el ? getComputedStyle(el).backgroundColor : null;
})()`);
const setCursorAtBrace = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  const lines = ta.value.split("\\n");
  let off = 0;
  for (let i = 0; i < 3; i++) off += lines[i].length + 1;   // 行 4 起点
  const pos = off + lines[3].indexOf("{");                   // while(2) 的 '{'
  ta.focus();
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('select', { bubbles: true }));
  return true;
})()`);

// ---- 准备：打开目录 + nest.c ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="nest.c"]')`);
await openFile("nest.c");
await waitFor(`document.querySelectorAll('#code-viewer .code-marks .code-mark-bracket-depth-0').length >= 2`);
check("0 nest.c 彩虹标记就位", (await depthSpans("bracket-depth-0")) >= 2);

// ---- 场景 1：嵌套深度 0..3 颜色两两不同（深色主题）----
await waitFor(`!!document.querySelector('#code-viewer .code-marks .code-mark-bracket-depth-3')`);
const bgs = {};
for (const d of [0, 1, 2, 3]) bgs[d] = await bgOf("bracket-depth-" + d);
const distinct = new Set(Object.values(bgs));
check("1a 深度 0..3 颜色互不相同", distinct.size === 4, JSON.stringify(bgs));
check("1b 背景非透明", Object.values(bgs).every((c) => c && c !== "transparent" && c !== "rgba(0, 0, 0, 0)"));

// ---- 场景 2：字符串内假括号不着色（真实 [] 仍着色）----
await waitFor(`document.querySelector('#code-viewer .code-marks [data-code-line="1"]')`);
check("2a 注释行无彩虹标记", (await lineSpans(1)) === 0);
const line5ok = await Eval(`(() => {
  const line = document.querySelector('#code-viewer .code-marks [data-code-line="5"]');
  if (!line) return null;
  const spans = line.querySelectorAll('[class*="code-mark-bracket-depth-"]');
  const texts = Array.from(spans).map((s) => s.textContent);
  return { count: spans.length, hasFakeBrace: texts.includes("{") };
})()`);
check("2b 字符串行仅真实 [] 着色", line5ok && line5ok.count === 2 && !line5ok.hasFakeBrace, JSON.stringify(line5ok));

// ---- 场景 3：亮色主题同样可见且互异 ----
await Eval(`document.documentElement.setAttribute('data-theme', 'light'); true`);
const bgsL = {};
for (const d of [0, 1, 2, 3]) bgsL[d] = await bgOf("bracket-depth-" + d);
check("3 亮色主题颜色互异", new Set(Object.values(bgsL)).size === 4, JSON.stringify(bgsL));
await Eval(`document.documentElement.removeAttribute('data-theme'); true`);

// ---- 场景 4：门控 plain/txt 不生效 ----
await openFile("note.txt");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "note.txt"`);
await new Promise((r) => setTimeout(r, 300));
check("4 txt 无彩虹标记", (await Eval(`document.querySelectorAll('#code-viewer .code-marks [class*="code-mark-bracket-depth-"]').length`)) === 0);

// ---- 场景 5：md 门控内生效（预览态→编辑态）----
await openFile("readme.md");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "readme.md"`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.setMdMode('readme.md', 'edit')); true`);
await waitFor(`document.querySelectorAll('#code-viewer .code-marks .code-mark-bracket-depth-0').length >= 2`);
check("5 md 编辑态彩虹生效（{ } 配对着色）", (await Eval(`document.querySelectorAll('#code-viewer .code-marks [class*="code-mark-bracket-depth-"]').length`)) === 2);

// ---- 场景 6：光标对描边仍优先（nested）----
await openFile("nest.c");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "nest.c"`);
await setCursorAtBrace();
await waitFor(`document.querySelectorAll('#code-viewer .code-marks .code-mark-bracket').length === 2`);
const outlineBg = await Eval(`(() => {
  const el = document.querySelector('#code-viewer .code-marks .code-mark-bracket');
  return el ? getComputedStyle(el).boxShadow : null;
})()`);
check("6 光标对描边 2 段且非空", outlineBg !== null && outlineBg !== "none", outlineBg);

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
