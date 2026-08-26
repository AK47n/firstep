// 工单 11 实况探针：最近生成列表簇迁出后——启动 initRecent → 列表渲染（刷新
// 按钮/删除/复制事件委托就绪）；readiness 面板留 host 仍工作（按钮 toggle +
// 面板渲染 + rc-recommend 入口接线）。全程零 EXC。
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
    events.push("EXC: " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).slice(0, 200));
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
check("启动 init 完成（initRecent 已绑定）", bootOk);
const r = await Eval(`(() => ({
  refreshBtn: !!document.getElementById("btn-recent-refresh"),
  list: !!document.getElementById("gen-recent-list"),
  box: !!document.getElementById("gen-recent"),
  emptyState: document.getElementById("gen-recent")?.classList.contains("hidden") ?? null,
}))()`);
check("最近生成容器与刷新按钮（initRecent 接线）", r.refreshBtn && r.list && r.box, JSON.stringify(r));
// readiness 面板按钮 toggle + 渲染（留 host）；一键推荐入口仅在有题面时渲染
await Eval(`document.getElementById("btn-readiness-check").click()`);
await new Promise((r) => setTimeout(r, 400));
const rd0 = await Eval(`(() => {
  const box = document.getElementById("readiness-check");
  return { visible: box && !box.classList.contains("hidden"), rows: box ? box.querySelectorAll(".rc-row").length : 0 };
})()`);
check("readiness 面板 toggle + 渲染", rd0.visible && rd0.rows > 0, JSON.stringify(rd0));
// 有题面 → 一键推荐按钮出现（rc-recommend 条件渲染）
await Eval(`(() => { document.getElementById("problem").value = "2024H 循迹小车"; return true; })()`);
await Eval(`document.getElementById("btn-readiness-check").click(); document.getElementById("btn-readiness-check").click();`);
await new Promise((r) => setTimeout(r, 400));
const rd1 = await Eval(`(() => {
  const box = document.getElementById("readiness-check");
  return { visible: box && !box.classList.contains("hidden"),
    recommendBtn: !!box.querySelector(".rc-recommend"), goBtns: box ? box.querySelectorAll(".rc-go").length : 0 };
})()`);
check("readiness 一键推荐入口（有题面渲染）", rd1.visible && rd1.recommendBtn, JSON.stringify(rd1));
await Eval(`(() => { document.getElementById("problem").value = ""; return true; })()`);
await new Promise((r2) => setTimeout(r2, 900));
const excs = events.filter((e) => e.startsWith("EXC") || (e.startsWith("HTTP") && !e.includes("favicon")));
check("全程零 EXC / 零 HTTP≥400（favicon 除外）", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
process.exit(process.exitCode || 0);
