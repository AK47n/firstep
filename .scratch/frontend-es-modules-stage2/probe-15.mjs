// 工单 15 实况探针：生成页 8/9/11 簇迁 ui/generate-core.js 后行为完好性。
// 覆盖：动态 import 无错 → 冒烟生成（generateMain，与基线同路径，必须 PASS）→
// 交接提示词（btn-handoff 真实点击）→ renderGenerateSuccess 假载荷（无工具链
// 守卫：走 compileBanner notool 分支；渲染评分清单/产物树/目录）→ 复制输出路径
// （真实鼠标点击 + clipboard）→ 桌面输出开关切换（change 监听）→ 全程零 EXC。
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

// P0 模块静态 import 可执行性直探（语法错误会在此炸出异常）
const impOk = await Eval(`import("/js/ui/generate-core.js").then((m) => typeof m.renderGenerateSuccess === "function" && typeof m.setGenerateCoreDeps === "function" ? "ok" : "missing exports").catch((e) => "FAIL: " + e.message)`);
check("generate-core.js 可动态 import（导出齐全）", impOk === "ok", impOk);

// 清草稿保证确定性起点
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await Eval(`try { localStorage.removeItem("score-checklist:C:\\\\fake-topic-15\\\\工程"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("problem") && !!document.querySelector("#platforms .platform-card")`, 20000);
check("页面就绪（模块化 host 加载成功）", ready);
await new Promise((r) => setTimeout(r, 600));

// P1 冒烟生成（与基线同路径：题面 + 平台 + 模块 + btn-smoke）
await Eval(`document.getElementById("problem").value = "样例赛题（工单15）：实现智能小车测距避障。"; "ok"`);
await Eval(`document.querySelector("#platforms .platform-card").click(); "ok"`);
await new Promise((r) => setTimeout(r, 400));
await Eval(`document.querySelector("#module-grid .module-card[data-add=\\"oled\\"], #module-grid .module-card[data-add=\\"debug_uart\\"]").click(); "ok"`);
await new Promise((r) => setTimeout(r, 1500));
const before = events.length;
await Eval(`document.getElementById("btn-smoke").click(); "ok"`);
const smokeOk = await waitFor(`(document.getElementById("main-c").value || "").length > 0 || document.getElementById("skeleton-msg").textContent.length > 0`, 300000);
check("冒烟生成完成（generateMain 迁后）", smokeOk,
  "msg=" + JSON.stringify(await Eval(`document.getElementById("skeleton-msg").textContent`)));
check("冒烟期间零 EXC", events.slice(before).filter((e) => e.startsWith("EXC@")).length === 0);

// P2 交接提示词（btn-handoff 真实点击 + handoff-msg 为空 + 文本含章节）
const b2 = events.length;
await realClick("btn-handoff");
await new Promise((r) => setTimeout(r, 1500));
const hText = await Eval(`document.getElementById("handoff-text").value`);
check("交接提示词生成（含章节/工具链段/空态兜底）",
  typeof hText === "string" && hText.includes("电赛工程交接提示词") && hText.includes("## 四、模块清单")
  && hText.includes("七、main.c 骨架") && hText.includes("八、工程位置")
  && (await Eval(`document.getElementById("handoff-msg").textContent`)) === "",
  "len=" + (hText || "").length);
check("交接期间零 EXC", events.slice(b2).filter((e) => e.startsWith("EXC@")).length === 0);

// P3 renderGenerateSuccess 假载荷（本机有工具链 → 走 startFixCenter 接缝分支：
// 假目录 → /api/compile 400 → compileBanner fail；无工具链环境则 notool 分支）
const b3 = events.length;
const fakeOk = await Eval(`import("/js/ui/generate-core.js").then((m) => {
  m.renderGenerateSuccess({
    output_dir: "C:\\\\fake-topic-15\\\\工程",
    include_dirs: ["drivers", "CMSIS"],
    modules: [], python_artifacts: [],
    score_points: [{ id: "B1", part: "basic", description: "完成测距", score: 10, sentence_refs: [2, 3] }],
    build_hint: "",
    structure: ["main.c", "设计报告草稿.md", "演示脚本.md"],
  });
  return "ok";
}).catch((e) => "FAIL: " + e.message)`);
check("renderGenerateSuccess 假载荷执行", fakeOk === "ok", fakeOk);
await new Promise((r) => setTimeout(r, 2500));
const resDir = await Eval(`document.getElementById("res-dir").textContent`);
const resVisible = await Eval(`!document.getElementById("generate-result").classList.contains("hidden")`);
const spVisible = await Eval(`!document.getElementById("res-score-points").classList.contains("hidden")`);
const spItems = await Eval(`document.querySelectorAll("#sp-list .sp-item, #sp-list input[type=checkbox]").length`);
const artChips = await Eval(`document.querySelectorAll("#res-artifacts .badge").length`);
const banner = await Eval(`document.getElementById("compile-banner").className + "|" + document.getElementById("compile-banner").textContent`);
const bannerOk = /^(notool|running|fail|success)(\s|$)/.test(banner.split("|")[0])
  && banner.split("|")[1].trim().length > 0;
check("成功区渲染（目录/评分清单/产物树 + 修复中心接缝横幅）",
  resDir === "C:\\fake-topic-15\\工程" && resVisible && spVisible && spItems >= 1 && artChips >= 1
  && bannerOk,
  "dir=" + JSON.stringify(resDir) + " sp=" + spItems + " art=" + artChips + " banner=" + banner.slice(0, 60));
check("假载荷期间零 EXC", events.slice(b3).filter((e) => e.startsWith("EXC@")).length === 0);

// P4 复制输出路径（btn-copy-dir 真实点击 → toast 已复制输出路径）
const b4 = events.length;
await realClick("btn-copy-dir");
await new Promise((r) => setTimeout(r, 800));
const toastTxts = await Eval(`Array.from(document.querySelectorAll("#toast-root .toast, #toast-root div")).map((n) => n.textContent).join(" | ")`);
check("复制输出路径 toast", /已复制输出路径/.test(toastTxts || ""), toastTxts);
check("复制期间零 EXC", events.slice(b4).filter((e) => e.startsWith("EXC@")).length === 0);

// P5 桌面输出开关（markup 默认 checked → disabled；点击取消勾选 = 手动模式解锁）
const b5 = events.length;
const beforeDisabled = await Eval(`document.getElementById("output-dir").disabled`);
await realClick("desktop-topic-output");
await new Promise((r) => setTimeout(r, 500));
const afterManual = await Eval(`document.getElementById("output-dir").disabled === false && document.getElementById("btn-pick-output-dir").disabled === false`);
check("桌面输出开关切换（默认勾选锁定 → 取消勾选解锁）", beforeDisabled === true && afterManual,
  "beforeDisabled=" + beforeDisabled + " afterManual=" + afterManual);
check("开关期间零 EXC", events.slice(b5).filter((e) => e.startsWith("EXC@")).length === 0);

// 收尾：汇总全部 EXC
const allExcs = events.filter((e) => e.startsWith("EXC@"));
console.log("--- 全程事件（EXC/LOG/HTTP>=400） ---");
console.log(events.filter((e) => !e.startsWith("LOG: Failed to load resource")).slice(0, 10).join("\n") || "（无）");
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
ws.close();
