// 工单 15 基线探针（迁移前）：冒烟生成一次，确认迁移前行为 + 探测
// currentTopicId 悬空引用（ticket 12 迁 A 簇后 host 2357/2501 仍引用未导出名）。
// CDP 直连（9251），webapp 8000。smoke 模式不落盘（webapp.py:1286 注释）。
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
    events.push("EXC@L" + d.lineNumber + "C" + d.columnNumber + ": " + (d.exception?.description || d.text).slice(0, 300));
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    const t = (m.params.entry.text || "") + " " + (m.params.entry.url || "");
    if (t.includes("favicon")) return;
    events.push("LOG: " + (m.params.entry.text || "").slice(0, 250));
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
const waitFor = async (expr, ms = 15000) => {
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

// 0. 页面就绪
await cdp("Page.enable");
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("problem") && !!document.querySelector("#platforms .platform-card")`, 20000);
check("页面就绪（platforms 卡片已渲染）", ready);
if (!ready) { console.log(events.join("\n")); process.exit(1); }
await new Promise((r) => setTimeout(r, 600));

// 1. 填题面 + 选平台 + 加模块（各一步，尽量真实）
await Eval(`document.getElementById("problem").value = "样例赛题（冒烟基线）：实现智能小车测距避障。"; "ok"`);
await Eval(`document.querySelector("#platforms .platform-card").click(); "ok"`);
await new Promise((r) => setTimeout(r, 400));
const platOk = await waitFor(`!!document.querySelector("#platforms .platform-card.active, #platforms .platform-card.selected") || !!document.getElementById("platform-msg") && document.getElementById("platform-msg").textContent.length > 0`, 3000);
check("选择平台（active/selected 或 msg）", platOk);
const cards = await Eval(`document.querySelectorAll("#module-grid .module-card[data-add]:not(.off)").length`);
check("模块池有可加模块卡", cards > 0, "cards=" + cards);
if (cards > 0) {
  await Eval(`document.querySelector("#module-grid .module-card[data-add]:not(.off)").click(); "ok"`);
  await new Promise((r) => setTimeout(r, 1500));
}

// 2. 冒烟生成（smoke 自检，不落盘）
const before = events.length;
await Eval(`document.getElementById("btn-smoke").click(); "ok"`);
const done = await waitFor(`(document.getElementById("main-c").value || "").length > 0`, 120000);
const msg = await Eval(`document.getElementById("skeleton-msg").textContent`);
const maincLen = await Eval(`(document.getElementById("main-c").value || "").length`);
const btn = await Eval(`document.getElementById("btn-smoke").textContent.trim()`);
check("冒烟生成完成（main-c 非空）", done, "len=" + maincLen + " msg=" + JSON.stringify(msg) + " btn=" + JSON.stringify(btn));
const excs = events.slice(before);
check("生成期间零 EXC/HTTP>=400", excs.filter((e) => e.startsWith("EXC@")).length === 0
  && excs.filter((e) => e.startsWith("HTTP")).length === 0,
  excs.join(" | ") || "无");

// 3. currentTopicId 悬空探测：直接构造 payload 构建路径的等价表达式（模块作用域不可达，
// 用 window 全局 + 宿主函数执行证明兜底：若 bug 存在，步骤 2 已炸 EXC）
console.log("--- 事件日志（本轮） ---");
console.log(excs.join("\n") || "（无）");
ws.close();
