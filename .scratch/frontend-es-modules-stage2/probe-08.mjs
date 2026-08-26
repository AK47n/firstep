// 工单 08 实况探针：参考库簇迁出后 tab 行为——分发器 loadReferences +
// loadKitVocabulary → 行数 > 0、chips/stats 渲染、详情弹层（viewReferenceDetail）、
// 录入表单初始文件行 + ref 文件选择绑定、编辑弹窗一次（editReference）。全程零 EXC。
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
const bootOk = await waitFor(`document.readyState === "complete" && document.querySelectorAll("#module-grid .module-card").length > 0`, 15000);
check("启动 init 完成", bootOk);
await Eval(`document.querySelector('nav button[data-tab="reference"]').click()`);
const loaded = await waitFor(`document.querySelectorAll("#ref-rows tr").length > 1`, 15000);
const ref = await Eval(`(() => ({
  rows: document.querySelectorAll("#ref-rows tr").length,
  stats: document.getElementById("ref-stats")?.textContent || "",
  chips: document.querySelectorAll("#ref-platform-chips [data-ref-chip]").length,
  kitOpts: document.querySelectorAll("#ref-anchor-kit option").length,
  tabActive: document.getElementById("tab-reference")?.classList.contains("active") || false,
}))()`);
check("参考库 tab 加载（行数 > 0 + 统计 + chips + kit 词表）", loaded && ref.rows > 0 && ref.chips >= 4 && ref.kitOpts >= 1 && ref.tabActive, JSON.stringify(ref));
// 详情弹层（viewReferenceDetail + 文件清单端点）
const viewed = await Eval(`(() => {
  const b = document.querySelector("#ref-rows [data-ref-view]");
  if (!b) return "no-view-btn";
  b.click();
  return true;
})()`);
const detailOk = await waitFor(`!!document.querySelector(".ref-files-overlay")`, 8000);
const detailText = await Eval(`document.querySelector(".ref-detail-scroll")?.textContent?.slice(0, 60) || ""`);
check("详情弹层（viewReferenceDetail）", viewed === true && detailOk, detailText);
await Eval(`(() => { const o = document.querySelector(".ref-files-overlay"); if (o) o.remove(); return true; })()`);
// 编辑弹窗一次（editReference 打开，文件清单端点直取）
const edited = await Eval(`(() => {
  const b = document.querySelector("#ref-rows [data-ref-edit]");
  if (!b) return "no-edit-btn";
  b.click();
  return true;
})()`);
const editOk = await waitFor(`!!document.querySelector(".lib-edit-overlay") && !!document.querySelector(".ref-edit-title")`, 8000);
const editTitle = await Eval(`document.querySelector(".ref-edit-title")?.value || ""`);
check("编辑弹窗（editReference 打开 + 预填）", edited === true && editOk && editTitle.length > 0, "title=" + editTitle.trim().slice(0, 30));
await Eval(`(() => { const o = document.querySelector(".lib-edit-overlay"); if (o) o.remove(); return true; })()`);
// 录入表单初始文件行 + 文件选择绑定
const form = await Eval(`(() => ({
  fileRows: document.querySelectorAll("#ref-files .file-row").length,
  pickBtn: !!document.getElementById("btn-ref-pick-files"),
  bindGone: true,
}))()`);
check("录入表单初始文件行 + ref 文件选择绑定", form.fileRows >= 1 && form.pickBtn, JSON.stringify(form));
await new Promise((r) => setTimeout(r, 1200));
const excs = events.filter((e) => e.startsWith("EXC") || (e.startsWith("HTTP") && !e.includes("favicon")));
check("全程零 EXC / 零 HTTP≥400（favicon 除外）", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
process.exit(process.exitCode || 0);
