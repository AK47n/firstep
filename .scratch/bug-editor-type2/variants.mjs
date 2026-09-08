// 变体矩阵：在第 2 行/窗口中部输入 abcd，观察模型/高亮层是否错行/反转
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9252;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "bug-editor-type2", "sample2");
mkdirSync(SAMPLE, { recursive: true });

const big = [];
for (let i = 1; i <= 200; i++) big.push("line " + i + " content");
writeFileSync(join(SAMPLE, "big.c"), big.join("\n"));
writeFileSync(join(SAMPLE, "empty2.c"), "line1\n\nline3\nline4\nline5\n");
writeFileSync(join(SAMPLE, "two.c"), "line1\nline2\n");

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
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
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

await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);

const cases = [
  { file: "big.c", label: "big 第2行行首", line: 2, col: 0, scroll: 0 },
  { file: "big.c", label: "big 第2行行尾", line: 2, col: -1, scroll: 0 },
  { file: "big.c", label: "big 第50行行首(窗口中部)", line: 50, col: 0, scroll: 3000 },
  { file: "empty2.c", label: "empty2 第2行(空行)行首", line: 2, col: 0, scroll: 0 },
  { file: "two.c", label: "two 第2行行首", line: 2, col: 0, scroll: 0 },
];

const results = [];
for (const c of cases) {
  const r = await Eval(`(async () => {
    const ce = await import('/js/ui/codeeditor.js');
    await ce.openEditorFile(${JSON.stringify(c.file)});
    const box = document.getElementById('code-viewer');
    const ta = box.querySelector('.code-ta');
    const tab = ce.getActiveTab();
    if (${JSON.stringify(c.scroll)}) { box.scrollTop = ${JSON.stringify(c.scroll)}; box.dispatchEvent(new Event('scroll')); await new Promise((r2) => setTimeout(r2, 120)); }
    ta.focus();
    const lines = ta.value.split('\\n');
    let p = 0;
    for (let i = 0; i < ${c.line} - 1; i++) p += lines[i].length + 1;
    const target = ${JSON.stringify(c.col)} < 0 ? p + lines[${c.line} - 1].length : p + ${JSON.stringify(c.col)};
    ta.setSelectionRange(target, target);
    const pre = { lines: tab.content.split('\\n'), taSel: target };
    const log = [];
    for (const ch of ['a', 'b', 'c', 'd']) {
      const p2 = ta.selectionStart;
      ta.value = ta.value.slice(0, p2) + ch + ta.value.slice(p2);
      ta.setSelectionRange(p2 + 1, p2 + 1);
      ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
      log.push({
        modelFirst6: tab.content.split('\\n').slice(0, 6),
        hlFirst6: Array.from(box.querySelectorAll('.code-hl-line')).map((el) => el.textContent).slice(0, 6),
        taSel: ta.selectionStart,
        taFirst6: ta.value.split('\\n').slice(0, 6),
      });
    }
    return { label: ${JSON.stringify(c.label)}, pre, log };
  })()`);
  results.push(r);
}
console.log(JSON.stringify(results, null, 2));
process.exit(0);
