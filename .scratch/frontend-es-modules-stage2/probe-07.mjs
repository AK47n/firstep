// 工单 07 实况探针：模块库簇迁出后 tab 行为——分发器 loadLibrary → 行数 > 0、
// chips/stats 渲染、详情弹窗（openModuleInfo 跨簇 import）、模块池联动
// （renderModulePool）、参考库 ref 文件选择绑定点仍在 host。全程零 EXC。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no 8000 page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0;
const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails;
    events.push("EXC@L" + d.lineNumber + ": " + (d.exception?.description || d.text).slice(0, 200));
  }
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400 && !m.params.response.url.includes("favicon")) {
    events.push("HTTP" + m.params.response.status + ": " + m.params.response.url);
  }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
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
const check = (name, ok, extra = "") => { console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " [" + extra + "]" : "")); if (!ok) process.exitCode = 1; };

await cdp("Runtime.enable");
await cdp("Network.enable");
await cdp("Page.reload", { ignoreCache: true });
// 等启动 init 完成（state.modules 装载 → 模块网格有卡）再切 tab，避免与加载赛跑
const bootOk = await waitFor(`document.readyState === "complete" && document.querySelectorAll("#module-grid .module-card").length > 0`, 15000);
check("启动 init 完成（state.modules 装载）", bootOk);
// 切到模块库 tab（分发器调 loadLibrary）
await Eval(`document.querySelector('nav button[data-tab="library"]').click()`);
const loaded = await waitFor(`document.querySelectorAll("#lib-rows tr").length > 1`, 15000);
const lib = await Eval(`(() => ({
  rows: document.querySelectorAll("#lib-rows tr").length,
  stats: document.getElementById("lib-stats")?.textContent || "",
  chips: document.querySelectorAll("#lib-platform-chips [data-lib-chip]").length,
  search: !!document.getElementById("lib-search"),
  tabActiveLibrary: document.getElementById("tab-library")?.classList.contains("active") || false,
}))()`);
check("模块库 tab 加载（loadLibrary 行数 > 0 + 统计 + chips）", loaded && lib.rows > 0 && lib.chips >= 3 && lib.stats.length > 0 && lib.tabActiveLibrary, JSON.stringify(lib));
// 详情弹窗（openModuleInfo 跨簇 import：generate-recommend.js）
const opened = await Eval(`(() => {
  const btn = document.querySelector("#lib-rows [data-info]");
  if (!btn) return "no-info-btn";
  btn.click();
  return true;
})()`);
const overlayOk = await waitFor(`!!document.querySelector(".module-info-overlay")`, 5000);
const modalInfo = await Eval(`document.querySelector(".module-info-scroll")?.textContent?.slice(0, 60) || ""`);
check("详情弹窗（openModuleInfo 从 generate-recommend import）", opened === true && overlayOk, modalInfo);
await Eval(`(() => { const o = document.querySelector(".module-info-overlay"); if (o) o.remove(); return true; })()`);
// 模块池联动（loadLibrary → renderModulePool 刷新模块网格）
const grid = await Eval(`document.querySelectorAll("#module-grid .module-card").length`);
check("模块池联动（renderModulePool 刷新）", grid > 0, "cards=" + grid);
// 过滤回环：搜索框输入 → 行数变化（renderLibraryTable 事件转发）
const filt = await Eval(`(() => {
  const s = document.getElementById("lib-search");
  s.value = "adc";
  s.dispatchEvent(new Event("input"));
  return document.querySelectorAll("#lib-rows tr").length;
})()`);
check("过滤回环（lib-search input → 表格重渲染）", filt >= 1, "rows=" + filt);
await Eval(`document.getElementById("lib-filter-clear").click()`);
await waitFor(`document.querySelectorAll("#lib-rows tr").length > 1`);
// 添加模块表单文件行 + ref 绑定点仍在 host
const forms = await Eval(`(() => ({
  fileRows: document.querySelectorAll("#new-files .file-row").length,
  refBind: !!document.getElementById("btn-ref-pick-files"),
}))()`);
check("添加模块表单初始文件行 + ref 绑定留 host", forms.fileRows >= 1 && forms.refBind, JSON.stringify(forms));
await new Promise((r) => setTimeout(r, 1200));
const excs = events.filter((e) => e.startsWith("EXC") || (e.startsWith("HTTP") && !e.includes("favicon")));
check("全程零 EXC / 零 HTTP≥400（favicon 除外）", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
process.exit(process.exitCode || 0);
