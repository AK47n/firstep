// 探针（工单 code-editor-refine/11 诊断先行）：5000 行 .c 逐击键热点实测
// ——直接计时 fx 纯件（折叠/缩进引导/括号深度/配对）单次全量成本 + 编辑器
// 输入事件处理耗时 + 打开渲染耗时；结果写入 stdout（前后对比基线）。
// 零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-11");
mkdirSync(SAMPLE, { recursive: true });
// 5000 行：函数 + 嵌套括号 + 缩进（覆盖折叠/深度/引导线热点）
const lines = [];
for (let i = 0; i < 500; i++) {
  lines.push("int f" + i + "(int a, int b) {");
  lines.push("    if (a > 0 && b > 0) {");
  lines.push("        for (int k = 0; k < 10; k++) {");
  lines.push("            int v" + i + " = a + b * k; // 行注释 ( 假括号");
  lines.push("        }");
  lines.push("    }");
  lines.push("    {");
  lines.push("        char s[] = \"{ 字符串假括号\";");
  lines.push("    }");
  lines.push("    return a + b;");
  lines.push("}");
  lines.push("");
}
writeFileSync(join(SAMPLE, "big.c"), lines.join("\n"));

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
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
const t0 = Date.now();
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
console.log("打开渲染耗时(ms):", Date.now() - t0);

const stats = await Eval(`(async () => {
  const content = document.querySelector('#code-viewer .code-ta').value;
  const N = 12;
  const time = (fn) => {
    fn();  // 预热
    const t = performance.now();
    for (let i = 0; i < N; i++) fn();
    return ((performance.now() - t) / N).toFixed(2);
  };
  const fold = await import('/js/fx/code-fold.js');
  const marks = await import('/js/fx/code-marks.js');
  const br = await import('/js/fx/code-brackets.js');
  const lines = content.split('\\n').length;
  const row = {};
  row.lines = lines;
  row.foldRanges = time(() => fold.codeFoldRanges(content, 'c'));
  row.indentGuide = time(() => marks.codeIndentGuideMarks(content));
  row.bracketDepth = time(() => br.bracketDepthMarks(content));
  row.pairAtOff = time(() => br.bracketPairAt(content, 1000));
  const ta = document.querySelector('#code-viewer .code-ta');
  const before = ta.value;
  ta.value = before + 'x';
  const t = performance.now();
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  const inputMs = performance.now() - t;
  ta.value = before;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  row.inputHandlerMs = inputMs.toFixed(2);
  return row;
})()`);
console.log(JSON.stringify(stats, null, 2));
process.exit(0);
