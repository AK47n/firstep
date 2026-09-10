// 冒烟（mainc-codeview-bridge/01）：生成页步骤 8 磁盘同步状态行全链路——
// 页面加载无模块图错误 → 状态行 DOM 存在且初始隐藏 → setMainCDiskContext 显示
// written → refreshMainCDiskState 检测差异变 changed → loadDiskMainC 加载磁盘
// 内容（行号/高亮/草稿落盘）→ 状态变 synced → 草稿 outputDir 持久化。
// 零写库（样本工程在 .scratch 下，git 忽略；不真生成）。零依赖：node 内置
// fetch + WebSocket 直连 Chrome CDP（9251，需 Node ≥ 21）；webapp 8000 提供真实 API。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "mainc-codeview-bridge", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  '#include "app.h"',
  "",
  "int main(void) {",
  "    return 0;",
  "}",
  "",
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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("未找到 webapp 页面 target"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const pageErrors = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    pageErrors.push(msg.params.exceptionDetails?.exception?.description || JSON.stringify(msg.params));
  }
  if (msg.method === "Log.entryAdded" && msg.params?.entry?.level === "error") {
    pageErrors.push(msg.params.entry.text);
  }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
await cdp("Log.enable");
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

// 0. 状态卫生（2026-09-09 第九轮）：本脚本第 2 步断言「未生成时状态行隐藏」，
//    前提是草稿里没有 outputDir；而 `firstep.draft.v1` 存在 localStorage（同一
//    profile 跨脚本留存），其它冒烟（ideflow / treeops / ideai 等）会把 outputDir
//    写进去 → 本脚本的绿红取决于**批跑顺序**（实测同一批跑器：
//    ideai/treeops/ideflow 因 CDP 9231 未起而提前失败时本脚本绿；9231 起来后
//    同批次它转红）。故开头清掉草稿键并整页重载 —— 把前提条件自己造出来，
//    不依赖外部执行顺序。
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {} window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });

// 1. 模块图加载完成（fx/draft window 桥 = host 脚本 import 全链成功）
assert(await waitFor(`typeof window.draftState === "function" && !window.__smokeMarker`), "页面模块图加载（draftState 桥就绪）");
// 2. 状态行 DOM 存在且初始隐藏
assert(await Eval(`!!document.querySelector("#mainc-disk-state")`), "状态行 DOM 存在");
assert(await Eval(`document.querySelector("#mainc-disk-state").classList.contains("hidden")`), "未生成时状态行隐藏");
// 3. written 态：setMainCDiskContext 后显示「已写入磁盘」+ 目录
const dir = SAMPLE.replace(/\\/g, "\\\\");
await Eval(`(async () => {
  const m = await import("/js/ui/generate-mainc-sync.js");
  m.setMainCDiskContext(${JSON.stringify(SAMPLE)});
  return m.getMainCDiskDir();
})()`);
assert(await Eval(`document.querySelector("#mainc-disk-state").innerHTML.includes("main.c 已写入磁盘")`), "written 文案显示");
assert(await Eval(`document.querySelector("#mainc-disk-state").innerHTML.includes(${JSON.stringify(SAMPLE)})`), "状态行含生成目录");
// 4. changed 态：编辑框为空 ≠ 磁盘 → 差异警示
await Eval(`(async () => {
  const m = await import("/js/ui/generate-mainc-sync.js");
  await m.refreshMainCDiskState();
})()`);
assert(await Eval(`document.querySelector("#mainc-disk-state").innerHTML.includes("磁盘 main.c 已更新")`), "差异检测 → changed 警示");
// 5. 加载磁盘 → textarea 内容 = 磁盘 main.c（换行归一化后含 include 行）+ synced
await Eval(`(async () => {
  const m = await import("/js/ui/generate-mainc-sync.js");
  await m.loadDiskMainC();
})()`);
assert(await Eval(`document.querySelector("#main-c").value.includes('#include "app.h"')`), "加载后 textarea = 磁盘内容");
assert(await Eval(`document.querySelector("#mainc-disk-state").innerHTML.includes("已同步磁盘版本")`), "加载后状态 synced");
// 6. 草稿落盘：input 事件已触发 → 400ms 防抖后 localStorage 含 outputDir
await new Promise((r) => setTimeout(r, 800));
const draft = await Eval(`(() => { try { return JSON.parse(localStorage.getItem("firstep.draft.v1")); } catch { return null; } })()`);
assert(draft && draft.outputDir === SAMPLE, "草稿持久化含 outputDir（" + (draft && draft.outputDir || "无") + "）");
// 7. 刷新恢复：reload 后状态行依草稿恢复（written→异步校验→synced）
await Eval(`location.reload(); true`);
assert(await waitFor(`typeof window.draftState === "function" && document.querySelector("#mainc-disk-state") && !document.querySelector("#mainc-disk-state").classList.contains("hidden")`, 10000), "刷新后状态行恢复可见");
assert(await waitFor(`document.querySelector("#mainc-disk-state").innerHTML.includes("已同步磁盘版本")`, 8000), "刷新后差异校验 → synced（编辑框=磁盘同内容）");
// 8. 无页面级异常（白名单：favicon / 母版树 / preview-dir = 既有页面环境噪声——
//    preview-dir 是就绪检查的静默降级调用，本机空白状态 400 属既有常态；
//    用 performance 资源条目标记失败 URL——Log 文本不含 URL 无法分类）
const failed = await Eval(`performance.getEntriesByType("resource")
  .map((e) => ({ name: e.name, status: e.responseStatus }))
  .filter((e) => e.status >= 400)`);
const ambient = /favicon\.ico|\/api\/masters\/|\/api\/generate\/preview-dir/;
const bad = (failed || []).filter((e) => !ambient.test(e.name));
bad.forEach((e) => console.error("失败资源: " + e.status + " " + e.name));
if (bad.length) process.exitCode = 1;
assert(bad.length === 0, "无资源加载失败（白名单外）");
ws.close();
console.log(process.exitCode ? "\nSMOKE FAILED" : "\nSMOKE PASS");
