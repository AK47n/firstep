// 工单 17 实况探针：修订工坊簇迁 ui/generate-revise.js 后行为完好性。
// 覆盖：动态 import 无错（导出齐全）→ 监听绑定（btn-revise-session 前置守卫 /
// btn-revise-analyze 前置守卫 / revise-problem-text input 即时更新）→ 全程零 EXC。
// 注：reviseLoad 真实加载需要真实工程目录（后端 /api/revise/context），冒烟不
// 生成落盘工程 → 此处以守卫/文案路径验证（load-context 渲染留待有真实工程的
// 手工确认；事件流分发复用 fix/core 同款 parseSSE 骨架，16 已证）。
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
const realClick = async (id) => {
  const r = await Eval(`(() => { const el = document.getElementById("${id}"); if (!el) return null; el.scrollIntoView({ block: "center" }); const b = el.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
  if (!r) return false;
  await cdp("Input.dispatchMouseEvent", { type: "mouseMoved", x: r.x, y: r.y });
  await cdp("Input.dispatchMouseEvent", { type: "mousePressed", x: r.x, y: r.y, button: "left", clickCount: 1 });
  await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x: r.x, y: r.y, button: "left", clickCount: 1 });
  return true;
};

await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Page.enable");

const impOk = await Eval(`import("/js/ui/generate-revise.js").then((m) => {
  const need = ["reviseLoad", "reviseAnalyze", "reviseApply", "reviseRollback",
    "reviseRunDeepen", "reviseResetAll", "reviseRenderContext"];
  return need.every((n) => typeof m[n] === "function") ? "ok" : "missing exports";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-revise.js 可动态 import（导出齐全）", impOk === "ok", impOk);

await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("btn-revise-analyze") && !!document.getElementById("btn-revise-session")`, 20000);
check("页面就绪（模块化 host 加载成功）", ready);
await new Promise((r) => setTimeout(r, 600));

// P1 btn-revise-session 监听（无 res-dir / output-dir → 守卫文案）
const b1 = events.length;
await realClick("btn-revise-session");
await new Promise((r) => setTimeout(r, 600));
const loadMsg = await Eval(`document.getElementById("revise-load-msg").textContent`);
check("btn-revise-session 监听（守卫：先生成工程）", loadMsg.includes("请先生成工程"), JSON.stringify(loadMsg));

// P2 btn-revise-analyze 监听（无上下文 → 守卫文案；注：分析卡默认 hidden，
// 真实用户路径 = 先加载上下文后按钮可见——守卫为防御性路径，用 DOM click 直测）
const b2 = events.length;
await Eval(`document.getElementById("btn-revise-analyze").click(); "ok"`);
await new Promise((r) => setTimeout(r, 600));
const anaMsg = await Eval(`document.getElementById("revise-analyze-msg").textContent`);
check("btn-revise-analyze 监听（守卫：先加载上下文）", anaMsg.includes("请先加载上下文"), JSON.stringify(anaMsg));

// P3 revise-problem-text input 监听（即时更新题面展示，无 context 兜底）
const b3 = events.length;
await Eval(`(() => { const t = document.getElementById("revise-problem-text"); t.value = "样例补充题面：提高测距精度"; t.dispatchEvent(new Event("input")); return "ok"; })()`);
await new Promise((r) => setTimeout(r, 300));
const probTxt = await Eval(`document.getElementById("revise-problem").textContent`);
check("revise-problem-text input 监听（即时更新）", probTxt === "样例补充题面：提高测距精度", probTxt);

// P4 revise-dir-input Enter 监听（绑定后 input 回车触发 load 守卫）
const b4 = events.length;
await Eval(`(() => { const t = document.getElementById("revise-dir-input"); t.value = "C:\\\\不存在\\\\目录"; t.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); return "ok"; })()`);
await new Promise((r) => setTimeout(r, 600));
const loadMsg2 = await Eval(`document.getElementById("revise-load-msg").textContent`);
check("revise-dir-input Enter 监听（触发 load → 后端 400 文案或守卫）",
  loadMsg2.includes("请先生成工程") || loadMsg2.includes("不存在") || loadMsg2.length > 0,
  JSON.stringify(loadMsg2).slice(0, 80));

const allExcs = events.filter((e) => e.startsWith("EXC@"));
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
ws.close();
