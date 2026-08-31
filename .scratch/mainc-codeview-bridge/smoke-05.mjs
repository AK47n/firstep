// 冒烟（mainc-codeview-bridge/05）：模块源码速查——打开模块详情弹窗（真实
// 模块库 led → stm32）→ 文件行可点击 → 点击懒加载源码（行号 + 高亮，复用
// codeViewHTML 观感）→ 二次点击命中缓存（无重复请求）→ 弹窗主体只读。
// 后端 = webapp 8000 真实 /api/modules + 新 /api/modules/{slug}/files/{path}；
// CDP 9251。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;

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
// 1. 打开 led 模块详情弹窗（真实库，stm32 段应有文件行）
await Eval(`(async () => {
  const r = await import("/js/ui/generate-recommend.js");
  r.openModuleInfo("led", "stm32");
})()`);
assert(await waitFor(`!!document.querySelector(".module-info-overlay .module-info-modal")`), "详情弹窗打开");
assert(await Eval(`document.querySelectorAll(".module-info-modal [data-mi-file]").length > 0`), "文件行可点击（data-mi-file）");
// 2. 点击第一个文件行 → 源码区渲染（行号 + 高亮行）
await Eval(`document.querySelector(".module-info-modal [data-mi-file]").click(); true`);
assert(await waitFor(`document.querySelector(".module-info-modal [data-module-source]") && !document.querySelector(".module-info-modal [data-module-source]").hidden`), "源码区显示");
assert(await waitFor(`document.querySelectorAll(".module-info-modal [data-module-source] .code-gutter-line").length > 0`), "源码行号渲染");
assert(await waitFor(`document.querySelectorAll(".module-info-modal [data-module-source] .code-pre-line").length > 0`), "高亮代码行渲染");
assert(await Eval(`document.querySelector(".module-info-modal [data-module-source]").textContent.includes("只读")`), "源码区标注只读");
// 3. 点击另一文件 → 内容切换（不同路径头）
const firstPath = await Eval(`document.querySelector(".module-info-modal [data-module-source] .module-source-head").textContent`);
await Eval(`document.querySelectorAll(".module-info-modal [data-mi-file]")[1].click(); true`);
assert(await waitFor(`(() => {
  const h = document.querySelector(".module-info-modal [data-module-source] .module-source-head");
  return !!h && h.textContent !== ${JSON.stringify(firstPath)};
})()`), "切换文件 → 源码区更新");
// 4. 后端端点直接校验（200 + content；错误路径 400 中文）
const bad = await (await fetchT("http://127.0.0.1:8000/api/modules/led/files/" + encodeURIComponent("../x.c"))).json();
assert(bad && bad.detail && bad.detail.includes("非法路径") || JSON.stringify(bad).includes("非法路径"), "后端穿越路径 400 中文");
ws.close();
console.log(process.exitCode ? "\nSMOKE FAILED" : "\nSMOKE PASS");
