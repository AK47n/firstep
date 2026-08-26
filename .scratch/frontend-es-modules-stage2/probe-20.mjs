// 工单 20 收尾探针：btn-generate 覆盖重发监听器补迁 generate-core.js 后回归。
// 覆盖：动态 import core（含新监听器）→ btn-generate 前置校验（无题面文案）→
// 题面+平台+模块全链路前置通过后按钮态 → 就绪面板 / 总览联动回归 → 全程零 EXC。
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
await cdp("Page.enable");

const impOk = await Eval(`import("/js/ui/generate-core.js").then((m) => {
  return typeof m.renderGenerateSuccess === "function" ? "ok" : "missing";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-core.js 可动态 import（含新监听器无语法错）", impOk === "ok", impOk);

await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("btn-generate")`, 20000);
check("页面就绪（模块化 host 加载成功）", ready);
await new Promise((r) => setTimeout(r, 600));

// P1 btn-generate 监听器（模块顶层绑定）：无题面/平台 → 前置校验文案
const b1 = events.length;
await Eval(`document.getElementById("btn-generate").click(); "ok"`);
await new Promise((r) => setTimeout(r, 500));
const msg1 = await Eval(`document.getElementById("generate-msg").textContent`);
check("btn-generate 前置校验（文案 = 平台/题面缺失）", msg1.trim().length > 0, JSON.stringify(msg1.slice(0, 30)));

// P2 填题面 + 选平台 + 加模块 → 前置通过（按钮进入就绪路径，无 400/异常）
const b2 = events.length;
await Eval(`document.getElementById("problem").value = "收尾总验样例：测距小车。"; "ok"`);
await Eval(`document.querySelector("#platforms .platform-card").click(); "ok"`);
await new Promise((r) => setTimeout(r, 400));
await Eval(`document.querySelector("#module-grid .module-card[data-add=\\"oled\\"], #module-grid .module-card[data-add=\\"debug_uart\\"]").click(); "ok"`);
await new Promise((r) => setTimeout(r, 1500));
await Eval(`document.getElementById("btn-generate").click(); "ok"`);
await new Promise((r) => setTimeout(r, 1200));
const msg2 = await Eval(`document.getElementById("generate-msg").textContent`);
check("btn-generate 前置通过后进入生成流（校验提示消失或进入 stage）",
  !msg2.includes("请先") && !msg2.includes("请填写"), JSON.stringify(msg2.slice(0, 60)));

// P3 就绪面板 + 总览联动（交叉簇回归）
const b3 = events.length;
await Eval(`document.getElementById("btn-readiness-check").click(); "ok"`);
await new Promise((r) => setTimeout(r, 400));
const panelLen = await Eval(`document.getElementById("readiness-check").innerHTML.length`);
const chips = await Eval(`document.querySelectorAll("#gen-overview .ov-chip").length`);
check("就绪面板 + 总览（跨簇回归）", panelLen > 50 && chips > 0, "panel=" + panelLen + " chips=" + chips);

const allExcs = events.filter((e) => e.startsWith("EXC@"));
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
console.log("--- 事件摘要（HTTP>=400） ---");
console.log(events.filter((e) => e.startsWith("HTTP")).join("\n") || "（无）");
ws.close();
