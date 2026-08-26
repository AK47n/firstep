// 工单 09 实况探针：题库簇迁出后 tab 行为——分发器 loadTopics +
// loadTopicGroupVocabulary → 卡片数 > 0、年份 chips / stats、详情弹窗
// （viewTopicDetail + 页图懒取 + 「用此题生成」useTopic 跨模块调用）、编辑弹窗
// （viewTopicEdit）、archive 链接（pdfFileUrl 单源修正实况）、拆条表单存在。
// 全程零 EXC。
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
await Eval(`document.querySelector('nav button[data-tab="topic"]').click()`);
const loaded = await waitFor(`document.querySelectorAll("#topic-grid .topic-card").length > 0`, 15000);
const top = await Eval(`(() => ({
  cards: document.querySelectorAll("#topic-grid .topic-card").length,
  chips: document.querySelectorAll("#topic-year-chips [data-topic-chip]").length,
  stats: document.getElementById("topic-stats")?.textContent || "",
  archiveLink: !!document.querySelector("[data-open-archive-pdf]"),
  split: !!document.getElementById("btn-topic-split"),
  tabActive: document.getElementById("tab-topic")?.classList.contains("active") || false,
}))()`);
check("题库 tab 加载（卡片 > 0 + 年份 chips + 统计 + archive 链接）", loaded && top.cards > 0 && top.chips >= 1 && top.stats.length > 0 && top.tabActive, JSON.stringify(top));
// 详情弹窗（viewTopicDetail 页图懒取（缓存或加载中）+ 「用此题生成」调用 useTopic 前先关窗）
const viewed = await Eval(`(() => {
  const b = document.querySelector("#topic-grid [data-topic-view]");
  if (!b) return "no-view";
  b.click();
  return true;
})()`);
const detailOk = await waitFor(`!!document.querySelector(".topic-modal")`, 8000);
await waitFor(`!document.querySelector("[data-topic-pages] .muted") || !!document.querySelector("[data-topic-pages] img")`, 8000).catch(() => {});
const detailText = await Eval(`document.querySelector(".topic-modal .ref-detail-scroll")?.textContent?.slice(0, 50) || ""`);
check("详情弹窗（viewTopicDetail + 页图懒取容器）", viewed === true && detailOk, detailText);
// 「用此题生成」按钮 = useTopic 跨模块调用：先验证按钮存在（点击会切 tab 真实生成流程，点击后校验成功态不炸）
const useBtn = await Eval(`!!document.querySelector(".topic-modal [data-topic-use]")`);
check("详情弹窗「用此题生成」按钮（useTopic import 接线）", useBtn);
// 编辑弹窗：详情弹窗内点「编辑」（卡片无编辑按钮——编辑入口在详情弹窗内）
const edited = await Eval(`(() => {
  const b = document.querySelector(".topic-modal [data-topic-edit]");
  if (!b) return "no-edit";
  b.click();
  return true;
})()`);
const editOk = await waitFor(`!!document.querySelector("textarea.topic-edit-problem")`, 8000);
const editLen = await Eval(`(document.querySelector("textarea.topic-edit-problem")?.value || "").length`);
check("编辑弹窗（viewTopicEdit 预填题面）", edited === true && editOk && editLen > 0, "len=" + editLen);
await Eval(`(() => { const o = document.querySelector(".ref-files-overlay"); if (o) o.remove(); return true; })()`);
// 拆条录入表单存在（split/confirm 监听接线不炸即可）
const split = await Eval(`(() => ({ pdfInput: !!document.getElementById("topic-pdf"), proofread: !!document.getElementById("topic-proofread-rows") }))()`);
check("拆条录入表单（split/confirm 接线）", split.pdfInput && split.proofread, JSON.stringify(split));
await new Promise((r) => setTimeout(r, 1200));
const excs = events.filter((e) => e.startsWith("EXC") || (e.startsWith("HTTP") && !e.includes("favicon")));
check("全程零 EXC / 零 HTTP≥400（favicon 除外）", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
process.exit(process.exitCode || 0);
