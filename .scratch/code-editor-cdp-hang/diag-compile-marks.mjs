// 诊断（code-editor-refine/smoke-05 场景 5 失败）：重编成功（parsed_errors=[]）后
// 编辑器标记层是否残留 .code-mark-error / .code-err-line？
// 逐项打印：getCompileErrors()、currentMarks 里的 error 条数、DOM 里的色点/标记数。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-05");
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
writeFileSync(join(SAMPLE, "other.c"), "#include <stdio.h>\nvoid other(void) {\n}\n");
writeFileSync(join(SAMPLE, "good.c"), "#include <stdio.h>\nvoid good(void) {\n}\n");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 10000 });
await c.cdp("Page.enable");
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="bad.c"]')`, 10000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="bad.c"]')?.click()`);
await c.waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === "bad.c"`, 10000);

const stub = (payload) => c.Eval(`(() => {
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
const runCompile = () => c.Eval(`import('/js/ui/code-compile.js').then((m) => m.runCodeCompile()).then(() => true)`);
const snap = (tag) => c.Eval(`import('/js/ui/codeeditor.js').then((m) => ({
  tag: ${JSON.stringify(tag)},
  compileErrors: (m.getCompileErrors() || []).length,
  marks: m.currentMarks().filter((x) => x.kind === 'error').length,
  gutterErrLines: document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length,
  domErrMarks: document.querySelectorAll('#code-viewer .code-marks .code-mark-error').length,
  activePath: m.getActiveTab() && m.getActiveTab().path,
}))`);

const ERRS = [
  { path: "bad.c", line: 3, message: "错误一：未声明标识符 'x'" },
  { path: "..\\bad.c", line: 7, message: "错误二：缺少分号" },
  { path: "other.c", line: 2, message: "错误三：other 文件" },
];
log("=== 第一次编译（带 3 条错误，与 smoke-05 同形）===");
await stub({ passed: false, timed_out: false, parsed_errors: ERRS });
await runCompile();
await sleep(1200);
log(JSON.stringify(await snap("after-err-compile")));

log("=== 按 smoke-05 顺序切文件 ===");
await c.Eval(`document.querySelector('#code-tree [data-code-file="other.c"]')?.click()`);
await sleep(600); log(JSON.stringify(await snap("other.c")));
await c.Eval(`document.querySelector('#code-tree [data-code-file="good.c"]')?.click()`);
await sleep(600); log(JSON.stringify(await snap("good.c")));
await c.Eval(`document.querySelector('#code-tree [data-code-file="bad.c"]')?.click()`);
await sleep(600); log(JSON.stringify(await snap("bad.c-back")));

log("=== 点击行 7 色点（jumpToCompileError）===");
await c.Eval(`document.querySelector('#code-viewer .code-gutter-line.code-err-line[data-code-line="7"]')?.click(); true`);
await sleep(1500);
log(JSON.stringify(await snap("after-dot-click")));

log("=== 第二次编译（passed:true, parsed_errors:[]）===");
await stub({ passed: true, timed_out: false, parsed_errors: [] });
await runCompile();
await sleep(1500);
log(JSON.stringify(await snap("after-ok-compile")));
await sleep(3000);
log(JSON.stringify(await snap("after-ok-compile+3s")));

log("=== 强制重画（切到 other.c 再切回 bad.c）===");
await c.Eval(`document.querySelector('#code-tree [data-code-file="other.c"]')?.click()`);
await sleep(800);
await c.Eval(`document.querySelector('#code-tree [data-code-file="bad.c"]')?.click()`);
await sleep(800);
log(JSON.stringify(await snap("after-switch")));
c.close();
