// 工单 16 实况探针：修复中心簇迁 ui/generate-fix.js 后行为完好性。
// 覆盖：动态 import 无错（导出齐全）→ 工具链状态文案（renderToolchainStatus 已
// 由 init 调用渲染）→ 就绪度（updateFixCenterAvailability 驱动 btn-fix-center
// 禁用态）→ 顶层监听绑定（btn-fix-center 真实点击 → 前置守卫「请先生成工程」）→
// btn-fix-continue 文案（FIX_MAX_ROUNDS 注入）→ generate-core 静态 import 链
//（renderGenerateSuccess 假载荷——核心 import fix 的编译触发）→ 全程零 EXC。
// CDP 直连（9251），webapp 8000。
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
await cdp("Network.enable");
await cdp("Page.enable");

// P0 模块静态 import 可执行性直探
const impOk = await Eval(`import("/js/ui/generate-fix.js").then((m) => {
  const need = ["startFixCenter", "continueFixCenter", "runCompileOnce", "runFixOnce",
    "fixRounds", "renderToolchainStatus", "updateFixCenterAvailability", "toolchains",
    "setToolchains", "compileBanner"];
  return need.every((n) => m[n] !== undefined) && typeof m.FIX_MAX_ROUNDS === "number"
    && typeof m.fixLoop === "object" ? "ok" : "missing exports";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-fix.js 可动态 import（导出齐全）", impOk === "ok", impOk);

await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("btn-fix-center") && !!document.getElementById("fix-center-toolchain")`, 20000);
check("页面就绪（模块化 host 加载成功）", ready);
await new Promise((r) => setTimeout(r, 600));

// P1 工具链状态文案（renderToolchainStatus 已由 host init 调用）
const tc = await Eval(`document.getElementById("fix-center-toolchain").textContent`);
check("工具链状态文案（renderToolchainStatus 渲染 ✅/❌）",
  tc.includes("工具链：Keil UV4") && tc.includes("gmake") && (tc.includes("✅") || tc.includes("❌")),
  tc.slice(0, 60));

// P2 就绪度：无平台 → btn-fix-center 禁用；选平台后启用
const b2 = events.length;
const dis0 = await Eval(`import("/js/ui/generate-fix.js").then(async (m) => { m.updateFixCenterAvailability(); return document.getElementById("btn-fix-center").disabled; })`);
check("就绪度：未选平台 → 一键按钮禁用", dis0 === true, "disabled=" + dis0);
await Eval(`document.querySelector("#platforms .platform-card").click(); "ok"`);
await new Promise((r) => setTimeout(r, 400));
const dis1 = await Eval(`import("/js/ui/generate-fix.js").then(async (m) => { m.updateFixCenterAvailability(); return document.getElementById("btn-fix-center").disabled; })`);
check("就绪度：选平台（有工具链）→ 一键按钮启用", dis1 === false, "disabled=" + dis1);
check("就绪度期间零 EXC", events.slice(b2).filter((e) => e.startsWith("EXC@")).length === 0);

// P3 顶层监听绑定：真实点击 btn-fix-center（无输出目录 → 前置守卫文案，不编译）
const b3 = events.length;
await realClick("btn-fix-center");
await new Promise((r) => setTimeout(r, 800));
const guard = await Eval(`document.getElementById("fix-errors-msg").textContent`);
check("btn-fix-center 监听（前置守卫：未生成工程 → 提示）", guard.includes("请先生成工程"), JSON.stringify(guard));

// P4 btn-fix-continue 文案（FIX_MAX_ROUNDS 注入，顶层绑定执行证明）
const cont = await Eval(`document.getElementById("btn-fix-continue").textContent`);
check("btn-fix-continue 文案（再来 3 轮）", cont.includes("继续修复（再来 3 轮）"), cont);

// P5 generate-core → generate-fix 静态 import 链（假载荷走 startFixCenter 接缝）
const b5 = events.length;
const fakeOk = await Eval(`import("/js/ui/generate-core.js").then((m) => {
  m.renderGenerateSuccess({
    output_dir: "C:\\\\fake-topic-16\\\\工程",
    include_dirs: [], modules: [], python_artifacts: [],
    score_points: [], build_hint: "", structure: ["main.c"],
  });
  return "ok";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-core → generate-fix 静态 import 链（renderGenerateSuccess 执行）", fakeOk === "ok", fakeOk);
await new Promise((r) => setTimeout(r, 2500));
const bannerCls = await Eval(`document.getElementById("compile-banner").className`);
const bannerTxt = await Eval(`document.getElementById("compile-banner").textContent`);
check("core 触发 fix 侧编译横幅（running/fail 终态）",
  /^(running|fail|success|notool)(\s|$)/.test(bannerCls) && bannerTxt.trim().length > 0,
  bannerCls + "|" + bannerTxt.slice(0, 50));
check("静态 import 链期间零 EXC", events.slice(b5).filter((e) => e.startsWith("EXC@")).length === 0);

const allExcs = events.filter((e) => e.startsWith("EXC@"));
console.log("--- 全程事件（EXC/HTTP>=400） ---");
console.log(events.filter((e) => e.startsWith("EXC@") || e.startsWith("HTTP")).slice(0, 10).join("\n") || "（无）");
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
ws.close();
