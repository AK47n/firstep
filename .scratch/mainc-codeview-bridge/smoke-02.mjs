// 冒烟（mainc-codeview-bridge/02）：任务/深化/修订/参数写盘后的磁盘更新提示——
// 冒烟模拟「外部改写磁盘」：加载到 synced → 改样本 main.c → refreshMainCDiskState
// → 步骤 8 状态行显示 changed 警示（真实钩子在 generate-tasks / generate-revise /
// params 的成功分支各一行，同一 refresh 路径）。零写库；webapp 8000 + CDP 9251。
import { appendFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "mainc-codeview-bridge", "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");

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
// 上下文 + 加载到 synced
await Eval(`(async () => {
  const m = await import("/js/ui/generate-mainc-sync.js");
  m.setMainCDiskContext(${JSON.stringify(SAMPLE)});
  await m.loadDiskMainC();
})()`);
assert(await waitFor(`document.querySelector("#mainc-disk-state").innerHTML.includes("已同步磁盘版本")`), "加载后 synced");
// 模拟任务/深化/修订/参数写盘：外部改写磁盘 main.c → refresh → changed
appendFileSync(MAIN_C, "\n// 任务写入的新逻辑\n");
await Eval(`(async () => { const m = await import("/js/ui/generate-mainc-sync.js"); await m.refreshMainCDiskState(); })()`);
assert(await waitFor(`document.querySelector("#mainc-disk-state").innerHTML.includes("磁盘 main.c 已更新")`), "磁盘改写后 changed 警示");
assert(await Eval(`document.querySelector("#mainc-disk-state").innerHTML.includes("加载为编辑内容")`), "changed 态按钮文案");
// 编辑框原内容未被自动覆盖（绝不自动覆盖手动编辑）
assert(await Eval(`document.querySelector("#main-c").value.includes('#include "app.h"')`), "编辑框未被自动覆盖");
// 点加载 → 回到 synced + 编辑框 = 磁盘新版本
await Eval(`document.querySelector("[data-mainc-reload]").click(); true`);
assert(await waitFor(`document.querySelector("#main-c").value.includes("任务写入的新逻辑")`), "点击加载后编辑框 = 磁盘新版本");
assert(await waitFor(`document.querySelector("#mainc-disk-state").innerHTML.includes("已同步磁盘版本")`), "加载后恢复 synced");
ws.close();
console.log(process.exitCode ? "\nSMOKE FAILED" : "\nSMOKE PASS");
