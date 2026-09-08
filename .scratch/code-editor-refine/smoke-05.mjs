// 冒烟（code-editor-refine/05 编译错误行内标记）：真实浏览器验证
// ①带错误「编译」（fetch 打桩 SSE）→ 打开对应文件 → 行号色点 + 错误行
// 下划线/底色 + title 悬停消息；②点击 gutter 色点 → 跳转到该行（复用
// jumpToCompileError 兜底链，active tab + 行号 flash 断言）；③重编成功 →
// 标记清除；④切走切回错误仍在；⑤无错误文件不显示。零后端（编译接口
// 打桩，不触真实工具链）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-05");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "bad.c"), [
  "#include <stdio.h>",
  "int main(void) {",
  "  int y = x + 1;      // 错误一：未声明 x",
  "  printf(\"%d\\n\", y);",
  "  if (1) {",
  "    y++;",
  "  } else               // 错误二：缺少分号",
  "  return 0;",
  "}",
].join("\n"));
writeFileSync(join(SAMPLE, "other.c"), [
  "#include <stdio.h>",
  "void other(void) {",   // 错误三：other 文件
  "}",
].join("\n"));
writeFileSync(join(SAMPLE, "good.c"), [
  "#include <stdio.h>",
  "void good(void) {",    // 无错误文件
  "}",
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
// fetch 打桩：/api/compile → 单事件 SSE done（结构错误列表 = 传入载荷）
const stubCompile = (payload) => Eval(`(() => {
  if (!window.__origFetch) window.__origFetch = window.fetch.bind(window);
  window.fetch = (url, init) => {
    if (String(url).includes('/api/compile')) {
      const sse = 'event: done\\ndata: ' + JSON.stringify(${JSON.stringify(payload)}) + '\\n\\n';
      return Promise.resolve(new Response(sse, { status: 200, headers: { 'content-type': 'text/event-stream' } }));
    }
    return window.__origFetch(url, init);
  };
  return true;
})()`);
const runCompile = () => Eval(`import('/js/ui/code-compile.js').then((m) => m.runCodeCompile()).then(() => true)`);

// ---- 准备：目录 + bad.c 打开 ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="bad.c"]')`);
await openFile("bad.c");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "bad.c"`);

// ---- 场景 1：带错误编译 → 行号色点 + 错误行标记 + title ----
const ERRS = [
  { path: "bad.c", line: 3, message: "错误一：未声明标识符 'x'" },
  { path: "..\\bad.c", line: 7, message: "错误二：缺少分号" },   // 反斜杠 + ..\ 前缀（basename 兜底）
  { path: "other.c", line: 2, message: "错误三：other 文件" },
];
await stubCompile({ passed: false, timed_out: false, parsed_errors: ERRS });
await runCompile();
await waitFor(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length === 2`);
check("1a 错误行号色点 2 个（bad.c 行 3/7）",
  (await Eval(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length`)) === 2);
const dotLines = await Eval(`Array.from(document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line')).map((el) => el.dataset.codeLine).sort().join(',')`);
check("1b 色点行号 = 3,7", dotLines === "3,7", dotLines);
const dotTitle = await Eval(`document.querySelector('#code-viewer .code-gutter-line.code-err-line[data-code-line="3"]')?.title ?? ''`);
check("1c gutter title = 错误消息", dotTitle.includes("未声明标识符"), dotTitle);
await waitFor(`document.querySelectorAll('#code-viewer .code-marks .code-mark-error').length >= 2`);
const errLineMembers = await Eval(`(() => {
  const line3 = document.querySelector('#code-viewer .code-marks [data-code-line="3"]');
  const line7 = document.querySelector('#code-viewer .code-marks [data-code-line="7"]');
  return {
    l3: line3 ? line3.querySelectorAll('.code-mark-error').length : -1,
    l7: line7 ? line7.querySelectorAll('.code-mark-error').length : -1,
    title: line3 ? (line3.querySelector('.code-mark-error')?.title || '') : '',
    deco: line3 ? getComputedStyle(line3.querySelector('.code-mark-error')).textDecorationLine : '',
  };
})()`);
check("2a 错误行 3/7 全行标记", errLineMembers.l3 > 0 && errLineMembers.l7 > 0, JSON.stringify(errLineMembers));
check("2b 标记 title = 消息", errLineMembers.title.includes("未声明标识符"), errLineMembers.title);
check("2c 下划线样式", errLineMembers.deco.includes("underline"), errLineMembers.deco);

// ---- 场景 2：按文件归口——other.c 自己的错误显示，无错文件不显示 ----
await openFile("other.c");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "other.c"`);
await waitFor(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length === 1`);
check("3a other.c 显示自己 1 个色点（行 2）",
  (await Eval(`document.querySelector('#code-viewer .code-gutter-line.code-err-line')?.dataset.codeLine`)) === "2");
await openFile("good.c");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "good.c"`);
await new Promise((r) => setTimeout(r, 400));
check("3b good.c（无错误）无边/色点/标记",
  (await Eval(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line, #code-viewer .code-marks .code-mark-error').length`)) === 0);

// ---- 场景 3：切走切回错误仍在 ----
await openFile("bad.c");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "bad.c"`);
await waitFor(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length === 2`);
check("4 切回 bad.c 色点仍在", (await Eval(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length`)) === 2);

// ---- 场景 4：点击色点跳转（复用 jumpToCompileError）----
await Eval(`document.querySelector('#code-viewer .code-gutter-line.code-err-line[data-code-line="7"]')?.click(); true`);
const jumped = await waitFor(`document.querySelector('#code-viewer .code-hl-line.flash')?.dataset.codeLine === '7'`, 5000);
check("5 点击行 7 色点 → 跳转 flash 行 7", jumped);

// ---- 场景 5：重编成功 → 标记清除 ----
await stubCompile({ passed: true, timed_out: false, parsed_errors: [] });
await runCompile();
await waitFor(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length === 0`);
check("6 重编成功后色点/标记清除",
  (await Eval(`document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line, #code-viewer .code-marks .code-mark-error').length`)) === 0);

await Eval(`(() => { if (window.__origFetch) { window.fetch = window.__origFetch; delete window.__origFetch; } return true; })()`);
console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
