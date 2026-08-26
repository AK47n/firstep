// 工单 18 实况探针：草稿 + 就绪总览簇迁 ui/generate-steps.js 后行为完好性。
// 覆盖：动态 import 无错 → 总览渲染（initGenOverview 由启动区调用：chips /
// summary / 补齐按钮）→ markStepDone 联动（setOnStepChange → refreshGenOverview：
// chip done 态 + 步骤进度条）→ 草稿往返（输入 → scheduleDraftSave 防抖 →
// reload → restoreDraft 恢复 + draft-tip）→ 全程零 EXC。
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

const impOk = await Eval(`import("/js/ui/generate-steps.js").then((m) => {
  const need = ["restoreDraft", "scheduleDraftSave", "initGenOverview", "refreshGenOverview", "setStepsDeps"];
  return need.every((n) => typeof m[n] === "function") ? "ok" : "missing exports";
}).catch((e) => "FAIL: " + e.message)`);
check("generate-steps.js 可动态 import（导出齐全）", impOk === "ok", impOk);

// P1 总览渲染（initGenOverview 已由 host 启动区调用）
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
const ready = await waitFor(`document.readyState === "complete" && !!document.getElementById("gen-overview") && !!document.querySelector("#gen-overview .ov-chip")`, 20000);
check("页面就绪 + 总览 chips 已渲染（initGenOverview）", ready);
await new Promise((r) => setTimeout(r, 600));
const chips = await Eval(`document.querySelectorAll("#gen-overview .ov-chip").length`);
const summary = await Eval(`document.querySelector("#gen-overview .ov-summary")?.textContent || ""`);
check("总览摘要非空（genOverviewSummaryHTML）", chips > 0 && summary.trim().length > 0, "chips=" + chips);

// P2 markStepDone 联动：总览 chip done 态 + 步骤进度条（setOnStepChange → refreshGenOverview）
const b2 = events.length;
await Eval(`import("/js/ui/step-state.js").then((m) => { m.markStepDone(1); return "ok"; })`);
await new Promise((r) => setTimeout(r, 700));
const chipDone = await Eval(`document.querySelector('#gen-overview .ov-chip[data-step="1"]').classList.contains("done")`);
check("markStepDone(1) → 总览 chip done 态（setOnStepChange 联动）", chipDone === true);
const gpHidden = await Eval(`document.getElementById("gen-progress").classList.contains("hidden")`);
const gpFrac = await Eval(`document.getElementById("gen-progress")?.textContent || ""`);
check("步骤进度条显隐（stepDoneSet.size>0 后显示）", gpHidden === false, "frac=" + gpFrac.slice(0, 30));

// P3 草稿往返：输入 → 防抖保存 → reload → restoreDraft 恢复 + draft-tip
const b3 = events.length;
await Eval(`(() => { const p = document.getElementById("problem"); p.value = "草稿往返样例：测距避障小车。"; p.dispatchEvent(new Event("input")); return "ok"; })()`);
await new Promise((r) => setTimeout(r, 800));   // 400ms 防抖 + 余量
const draftSaved = await Eval(`JSON.parse(localStorage.getItem("firstep.draft.v1") || "null")?.problem || ""`);
check("scheduleDraftSave 防抖落盘（localStorage draft）", draftSaved.includes("草稿往返样例"), draftSaved.slice(0, 20));
await cdp("Page.reload", { ignoreCache: true });
const ready2 = await waitFor(`document.readyState === "complete" && !!document.getElementById("problem")`, 20000);
await new Promise((r) => setTimeout(r, 800));
const restored = await Eval(`document.getElementById("problem").value`);
const tip = await Eval(`!document.getElementById("draft-tip").classList.contains("hidden")`);
check("restoreDraft 恢复（reload 后题面 + draft-tip 显示）", restored.includes("草稿往返样例") && tip === true,
  "problem=" + JSON.stringify(restored.slice(0, 12)) + " tip=" + tip);

// P4 清除草稿按钮（顶层监听）：点击 → 清空 + tip 隐藏 + 按钮文案翻转
const b4 = events.length;
await Eval(`document.getElementById("btn-clear-draft").click(); "ok"`);
await new Promise((r) => setTimeout(r, 300));
const tipAfter = await Eval(`document.getElementById("draft-tip").classList.contains("hidden")`);
const btnTxt = await Eval(`document.getElementById("btn-clear-draft").textContent.trim()`);
check("btn-clear-draft 监听（清除 + 文案翻转）", tipAfter === true && btnTxt.includes("已清除"), btnTxt);

const allExcs = events.filter((e) => e.startsWith("EXC@"));
check("全程零 EXC", allExcs.length === 0, allExcs.join(" | ") || "无");
ws.close();
