// 冒烟（mainc-codeview-bridge/03）：双向跳转桥——步骤 8 工具栏「查看工程」/
// 结果区「在代码查看器中打开工程」→ 代码 tab 加载生成上下文目录；代码 tab
// 打开目录 === 生成上下文 → 顶栏「去生成页编辑 main.c」；点它 → 回生成页 +
// 编辑框加载磁盘版本；打开其他目录 → 入口隐藏（只读契约不破：代码 tab 无
// 任何编辑控件）。零写库；webapp 8000 + CDP 9251。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "mainc-codeview-bridge", "sample-proj");
const OTHER = join(ROOT, ".scratch", "mainc-codeview-bridge", "sample-other");
mkdirSync(OTHER, { recursive: true });
writeFileSync(join(OTHER, "main.c"), "int main(void) { return 0; }\n");

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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("未找到 webapp 页面 target"); process.exit(1); }
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
const assert = (cond, label) => {
  if (!cond) { console.error("FAIL: " + label); process.exitCode = 1; }
  else console.log("ok: " + label);
};

assert(await waitFor(`typeof window.draftState === "function"`), "页面模块图加载");
// 前置：显式清空生成上下文 → 工具栏入口隐藏（验收 #2；本机 recent.json 有
// 历史记录，无草稿回退会先给上下文，先清空再加入再断言——消除偶发）
await Eval(`(async () => { const m = await import("/js/ui/generate-mainc-sync.js"); m.setMainCDiskContext(""); })()`);
assert(await Eval(`document.querySelector("#btn-goto-code-mainc").classList.contains("hidden")`), "无上下文 → 工具栏入口隐藏");
// 前置：生成上下文 = SAMPLE（等价 renderGenerateSuccess 的效果）
await Eval(`(async () => {
  const m = await import("/js/ui/generate-mainc-sync.js");
  m.setMainCDiskContext(${JSON.stringify(SAMPLE)});
})()`);
assert(await waitFor(`!document.querySelector("#btn-goto-code-mainc").classList.contains("hidden")`), "有上下文 → 工具栏入口可见");
// 1. 步骤 8 工具栏「查看工程」→ 代码 tab + 目录 = SAMPLE
assert(await Eval(`!!document.querySelector("#btn-goto-code-mainc")`), "步骤 8 工具栏入口存在");
await Eval(`document.querySelector("#btn-goto-code-mainc").click(); true`);
assert(await waitFor(`document.querySelector('section#tab-code').classList.contains("active")`), "点击后切到代码 tab");
assert(await waitFor(`document.querySelector("#code-dir-label").textContent.includes(${JSON.stringify(SAMPLE)}) && document.querySelector("#code-tree .code-tree")`), "代码查看器加载了生成目录");
// 2. 目录 === 上下文 → 顶栏「去生成页编辑 main.c」可见
assert(await waitFor(`!document.querySelector("#btn-code-goto-generate").classList.contains("hidden")`), "匹配目录 → 跳回按钮可见");
// 3. 点击跳回 → 生成 tab + 编辑框 = 磁盘版本（sample main.c 含 include）
await Eval(`document.querySelector("#btn-code-goto-generate").click(); true`);
assert(await waitFor(`document.querySelector('section#tab-generate').classList.contains("active")`), "跳回生成页");
assert(await waitFor(`document.querySelector("#main-c").value.includes('#include "app.h"')`), "编辑框加载磁盘 main.c");
// 4. 打开其他目录 → 入口隐藏
await Eval(`(async () => { const c = await import("/js/ui/codeview.js"); c.openCodeViewer(${JSON.stringify(OTHER)}); })()`);
assert(await waitFor(`document.querySelector("#code-dir-label").textContent.includes(${JSON.stringify(OTHER)})`), "打开其他目录");
assert(await waitFor(`document.querySelector("#btn-code-goto-generate").classList.contains("hidden")`), "非生成上下文 → 入口隐藏");
// 5. 生成页编辑框不受代码 tab 影响（原「代码 tab 只读（无 textarea）」断言已过期：
//    工单 code-viewer-editor 起代码 tab 本身即可编辑（.code-ta）；本桥的契约是
//    「生成页 #main-c 仍是生成侧编辑入口」，故改为断生成页编辑框仍在且未被清空。
//    2026-09-09 第八轮按实现现状修订，见工单 code-editor-cdp-hang/01。
assert(await Eval(`!!document.getElementById("main-c")
  && document.getElementById("main-c").value.includes('#include "app.h"')`), "生成页编辑框独立于代码 tab（内容仍在）");
assert(await Eval(`!!document.querySelector("#tab-code #code-viewer")`), "代码 tab 编辑器面板在位（可编辑入口）");
ws.close();
console.log(process.exitCode ? "\nSMOKE FAILED" : "\nSMOKE PASS");
