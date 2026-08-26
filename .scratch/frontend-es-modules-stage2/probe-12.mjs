// 工单 12 实况探针：推荐簇 A + 步骤状态核心迁出后生成页行为完好性。
// 验证：平台卡渲染→点选（步骤 3 完成 + 进度条 + 总览 chips）→ 模块池渲染 →
// 加模块（步骤 6 完成 + runExpand 展开 + 引脚卡渲染）→ step-nav / 折叠按钮 /
// 总览存在 → 全程零 EXC。CDP 直连（9251），webapp 8000。
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
    events.push("EXC@L" + d.lineNumber + "C" + d.columnNumber + ": " + (d.exception?.description || d.text).slice(0, 200));
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    events.push("LOG: " + m.params.entry.text.slice(0, 250));
  }
  if (m.method === "Network.loadingFailed") {
    events.push("NETFAIL: " + m.params.errorText + " " + (m.params.blockedReason || ""));
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
const check = (name, ok, extra = "") => {
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " [" + extra + "]" : ""));
  if (!ok) process.exitCode = 1;
};

await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Network.enable");
// 清草稿保证确定性起点（草稿恢复会让步骤预完成）
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === "complete" && !!document.getElementById("platforms") && !!document.querySelector(".platform-card")`);
await new Promise((r) => setTimeout(r, 800));

// P1 平台卡渲染
const p1 = await Eval(`(() => {
  const cards = [...document.querySelectorAll("#platforms .platform-card")];
  return { total: cards.length, ready: cards.filter((c) => !c.classList.contains("disabled")).length };
})()`);
check("平台卡渲染（state.platforms）", p1.total >= 2 && p1.ready >= 0, JSON.stringify(p1));

// P2 点击就绪平台卡 → 步骤 3 完成 + 进度条 + 总览 chips
const p2 = await Eval(`(() => {
  const card = [...document.querySelectorAll("#platforms .platform-card")].find((c) => !c.classList.contains("disabled"));
  if (!card) return null;
  card.click();
  return true;
})()`);
check("点选就绪平台卡", p2 === true);
await waitFor(`document.querySelector('.step-nav .step-dot[data-step="3"]')?.classList.contains("done")`);
const p2b = await Eval(`(() => {
  const dot3 = document.querySelector('.step-nav .step-dot[data-step="3"]');
  const prog = document.getElementById("gen-progress");
  const chip3 = document.querySelector('.ov-chip[data-step="3"]');
  return {
    dot3done: dot3?.classList.contains("done") || false,
    dot3txt: dot3?.querySelector(".dot")?.textContent || null,
    progShown: prog && !prog.classList.contains("hidden"),
    chip3done: chip3?.classList.contains("done") || false,
    steps: document.querySelectorAll(".step-nav .step-dot").length,
    collapseBtn: !!document.getElementById("btn-collapse-done"),
    cardCollapse: document.querySelectorAll(".card-collapse").length,
    overviewChips: document.querySelectorAll(".ov-chip").length,
  };
})()`);
check("步骤 3 完成（step-nav dot + 进度条 + 总览 chip）", p2b.dot3done && p2b.dot3txt === "✓" && p2b.progShown && p2b.chip3done, JSON.stringify(p2b));
check("step-nav / 折叠按钮 / 总览 chips 就绪", p2b.steps >= 9 && p2b.collapseBtn && p2b.cardCollapse >= 8 && p2b.overviewChips >= 9, `steps=${p2b.steps} collapse=${p2b.cardCollapse} chips=${p2b.overviewChips}`);

// P3 模块池渲染
const p3 = await Eval(`document.querySelectorAll("#module-grid .module-card").length`);
check("模块池渲染（module-grid 卡片数 > 0）", p3 > 0, "cards=" + p3);

// P4 点击模块卡 → 已选清单 + 步骤 6 完成 + 展开成功（引脚卡渲染）
const p4 = await Eval(`(() => {
  const card = [...document.querySelectorAll("#module-grid .module-card")].find((c) => !c.classList.contains("off") && c.dataset.add);
  if (!card) return "no-card";
  card.click();
  return card.dataset.add;
})()`);
check("点击模块卡（已选进入选中箱）", p4 !== "no-card", "slug=" + p4);
await waitFor(`!!document.querySelector("#selected-list .item")`);
const p4b = await Eval(`(() => {
  const dot6 = document.querySelector('.step-nav .step-dot[data-step="6"]');
  const items = document.querySelectorAll("#selected-list .item").length;
  const expandMsg = document.getElementById("expand-msg")?.textContent || "";
  const pinEmpty = document.getElementById("pin-config-empty");
  const pinBody = document.getElementById("pin-config-body");
  return { dot6done: dot6?.classList.contains("done") || false, items, expandMsg,
    pinCard: pinEmpty && pinBody ? (pinEmpty.classList.contains("hidden") ? "body" : "empty") : "?",
    instanceCardHidden: document.getElementById("card-instance-config")?.classList.contains("hidden") ?? null };
})()`);
check("步骤 6 完成 + 依赖展开", p4b.dot6done && p4b.items > 0 && p4b.expandMsg === "", JSON.stringify(p4b));

// P5 推荐区占位 + 参考选择器存在
const p5 = await Eval(`(() => ({
  recList: !!document.getElementById("rec-list"),
  btnRecommend: !!document.getElementById("btn-recommend"),
  refPicker: !!document.getElementById("ref-picker"),
  refSearch: !!document.getElementById("ref-search"),
  moduleSearch: !!document.getElementById("module-search"),
  btnExpand: !!document.getElementById("btn-expand"),
  topicPdfBox: !!document.getElementById("topic-pdf-box"),
}))()`);
check("推荐区 / 参考选择器 / 模块池控件存在", p5.recList && p5.btnRecommend && p5.refPicker && p5.refSearch && p5.moduleSearch && p5.btnExpand && p5.topicPdfBox, JSON.stringify(p5));

await new Promise((r) => setTimeout(r, 1500));
// LOG 的 404 资源报告 = favicon 的浏览器级重复（HTTP 事件已过滤 favicon），不算故障
const excs = events.filter((e) =>
  e.startsWith("EXC") || e.startsWith("NETFAIL")
  || (e.startsWith("HTTP") && !e.includes("favicon"))
  || (e.startsWith("LOG") && !e.includes("Failed to load resource")));
check("全程零 EXC / 零网络失败", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
console.log("=== events ===");
events.filter((e) => !e.includes("favicon")).slice(0, 8).forEach((e) => console.log(e));
process.exit(process.exitCode || 0);
