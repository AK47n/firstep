// 工单 19 实况探针：就绪检查簇迁 ui/generate-readiness.js（阶段 2 收尾票）。
// 覆盖：动态 import 无错 → initReadinessCheck 后点击按钮 → 面板可见 + 行数>0 →
// generate-steps 静态 import 链（refreshGenOverview 经 readinessState 判定，
// markStepDone 驱动后无 EXC）→ btn-generate 监听器 readinessState（host import）
// 冒烟（无题面守卫文案）→ 全程零 EXC。
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

const impOk = await Eval(`import("/js/ui/generate-readiness.js").then((m) => {
  const need = ["readinessState", "renderReadinessPanel", "refreshReadinessPanel", "initReadinessCheck"];
  return need.every((n) => typeof m[n] === "function") ? "ok" : "missing exports";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-readiness.js 可动态 import（导出齐全）", impOk === "ok", impOk);

await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("btn-readiness-check") && !!document.getElementById("gen-overview")`, 20000);
check("页面就绪（模块化 host 加载成功）", ready);
await new Promise((r) => setTimeout(r, 600));

// P1 就绪面板：点击按钮 → 可见 + 行数 > 0（initReadinessCheck 绑定 + readinessRowsHTML）
const b1 = events.length;
await Eval(`document.getElementById("btn-readiness-check").click(); "ok"`);
await new Promise((r) => setTimeout(r, 500));
const panelOpen = await Eval(`!document.getElementById("readiness-check").classList.contains("hidden")`);
const rows = await Eval(`document.querySelectorAll("#readiness-check .rc-row, #readiness-check table tr, #readiness-check [class*=row]").length`);
check("就绪面板展开 + 行数 > 0", panelOpen === true && rows > 0, "rows=" + rows + "（fallback 计数）");
const htmlLen = await Eval(`document.getElementById("readiness-check").innerHTML.length`);
check("就绪面板内容非空（判据行渲染）", htmlLen > 50, "len=" + htmlLen);

// P2 steps → readiness 静态 import 链：refreshGenOverview 无 EXC + 联动正常
const b2 = events.length;
await Eval(`import("/js/ui/step-state.js").then((m) => { m.markStepDone(1); return "ok"; })`);
await new Promise((r) => setTimeout(r, 700));
const panelRows = await Eval(`document.getElementById("readiness-check").innerHTML.length`);
const chipDone = await Eval(`document.querySelector('#gen-overview .ov-chip[data-step="1"]').classList.contains("done")`);
check("markStepDone → 总览联动（setOnStepChange → refreshGenOverview 经 readinessState）",
  chipDone === true && panelRows > 50, "chipDone=" + chipDone);
check("联动期间零 EXC", events.slice(b2).filter((e) => e.startsWith("EXC@")).length === 0);

// P3 btn-generate 监听器（host）readinessState：无题面 → 前置校验文案
const b3 = events.length;
await Eval(`document.getElementById("btn-generate").click(); "ok"`);
await new Promise((r) => setTimeout(r, 500));
const genMsg = await Eval(`document.getElementById("generate-msg").textContent`);
check("btn-generate 监听（host 侧 readinessState 前置校验，无题面 → 文案）",
  genMsg.trim().length > 0, JSON.stringify(genMsg.slice(0, 40)));

const allExcs = events.filter((e) => e.startsWith("EXC@"));
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
ws.close();
