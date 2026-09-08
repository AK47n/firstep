// 冒烟（code-editor-refine/09 Ctrl+P 快速打开）：真实浏览器验证
// ①Ctrl+P 出 overlay；②输入 main → main.c 命中；Enter 打开；③↑/↓ 选择 +
// Enter 打开；④Esc / 点击遮罩关闭；⑤无匹配空态；⑥已开文件 Enter 激活既有
// tab（不重复开）；⑦中文/空格路径匹配显示。零后端（树走真实 /api/code/open
// 样例目录）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-09");
mkdirSync(join(SAMPLE, "src"), { recursive: true });
mkdirSync(join(SAMPLE, "docs"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "#include <stdio.h>\nvoid main09(void) {}\n");
writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdio.h>\nvoid app(void) {}\n");
writeFileSync(join(SAMPLE, "src", "util.c"), "#include <stdio.h>\nvoid util(void) {}\n");
writeFileSync(join(SAMPLE, "docs", "readme.md"), "# 标题\n");
writeFileSync(join(SAMPLE, "src", "心 得.txt"), "hello\n");

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
const ctrlP = () => Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'p', ctrlKey: true, bubbles: true, cancelable: true })); true`);
const typeQuery = (q) => Eval(`(() => {
  const inp = document.querySelector('.quick-open-input');
  if (!inp) return false;
  inp.value = ${JSON.stringify(q)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
const items = () => Eval(`Array.from(document.querySelectorAll('.quick-open-item')).map((el) => el.textContent)`);
const pressKey = (key) => Eval(`document.querySelector('.quick-open-input')?.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(key)}, bubbles: true, cancelable: true })); true`);

// ---- 准备 ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);

// ---- 场景 1：Ctrl+P 出 overlay ----
await ctrlP();
check("1 Ctrl+P 出 overlay", await waitFor(`!!document.querySelector('.quick-open-overlay')`));
check("1b 空 query 提示（不列结果）", (await items()).length === 0
  && (await Eval(`!!document.querySelector('.quick-open-empty')`)));

// ---- 场景 2：输入 main → 命中 + Enter 打开 ----
await typeQuery("main");
await new Promise((r) => setTimeout(r, 200));
const hits = await items();
check("2 输入 main 命中 main.c", hits.join("|") === "main.c", hits.join("|"));
await pressKey("Enter");
check("2b Enter 打开 main.c", await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === 'main.c'`));
check("2c overlay 已关", (await Eval(`!!document.querySelector('.quick-open-overlay')`)) === false);

// ---- 场景 3：方向键选择 + Enter（util.c） ----
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await typeQuery("uti");
await new Promise((r) => setTimeout(r, 200));
check("3 输入 uti 命中 src/util.c", (await items()).join("|") === "src/util.c", (await items()).join("|"));
await pressKey("ArrowDown");
await pressKey("ArrowUp");
await pressKey("Enter");
check("3b Enter 打开 src/util.c", await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === 'src/util.c'`));

// ---- 场景 4：Esc / 点击遮罩关闭 ----
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })); true`);
await new Promise((r) => setTimeout(r, 200));
check("4a Esc 关闭", (await Eval(`!!document.querySelector('.quick-open-overlay')`)) === false);
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await Eval(`(() => { const o = document.querySelector('.quick-open-overlay'); o.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return true; })()`);
await new Promise((r) => setTimeout(r, 200));
check("4b 点击遮罩关闭", (await Eval(`!!document.querySelector('.quick-open-overlay')`)) === false);

// ---- 场景 5：无匹配空态 ----
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await typeQuery("zzzz");
await new Promise((r) => setTimeout(r, 200));
check("5 无匹配空态", (await Eval(`document.querySelector('.quick-open-empty')?.textContent.includes('无匹配')`)) === true
  && (await items()).length === 0);
await pressKey("Escape");

// ---- 场景 6：已开文件激活既有 tab（不重复开） ----
const tabsBefore = await Eval(`document.querySelectorAll('#code-tabs .code-tab').length`);
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await typeQuery("main");
await new Promise((r) => setTimeout(r, 200));
await pressKey("Enter");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === 'main.c'`);
const tabsAfter = await Eval(`document.querySelectorAll('#code-tabs .code-tab').length`);
check("6 已开文件 Enter 激活既有 tab（tab 数不变）", tabsAfter === tabsBefore, String(tabsBefore) + "->" + String(tabsAfter));

// ---- 场景 7：中文/空格路径 ----
await ctrlP();
await waitFor(`!!document.querySelector('.quick-open-overlay')`);
await typeQuery("心 得");
await new Promise((r) => setTimeout(r, 200));
check("7 中文/空格路径命中", (await items()).join("|") === "src/心 得.txt", (await items()).join("|"));
await pressKey("Escape");

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
