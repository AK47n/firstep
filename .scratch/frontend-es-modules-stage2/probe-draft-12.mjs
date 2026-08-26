// 工单 12 草稿恢复写点探针：restoreDraft 经宿主 setter 写 A 状态
// （setChosenPlatform / setSelectedSlugs / setCurrentTopicId）+ markStepDone
// 与 renderPlatforms/renderSelected 联动；草稿恢复后不触发任何后端。
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
    events.push("EXC: " + (d.exception?.description || d.text).slice(0, 200));
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
// 预写草稿：stm32 + 2 个 slug → 恢复后应：平台卡 selected、步骤 3/6 完成、
// 已选箱有 2 条、草稿提示条显示
await Eval(`(() => {
  localStorage.setItem("firstep.draft.v1", JSON.stringify({ problem: "2024H 循迹小车", topicId: "", platform: "stm32", slugs: ["adc", "pid"], mainC: "", qa: "" }));
  return true;
})()`);
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === "complete" && !!document.querySelector(".platform-card")`);
await new Promise((r) => setTimeout(r, 900));
const r = await Eval(`(() => {
  const sel = [...document.querySelectorAll("#platforms .platform-card")].find((c) => c.classList.contains("selected"));
  const dot3 = document.querySelector('.step-nav .step-dot[data-step="3"]');
  const dot6 = document.querySelector('.step-nav .step-dot[data-step="6"]');
  const listText = document.getElementById("selected-list")?.textContent || "";
  const chip3 = document.querySelector('.ov-chip[data-step="3"]');
  return {
    platformSelected: sel ? sel.textContent.trim() : null,
    dot3done: dot3?.classList.contains("done") || false,
    dot6done: dot6?.classList.contains("done") || false,
    adcInList: listText.includes("adc"),
    pidInList: listText.includes("pid"),
    chip3done: chip3?.classList.contains("done") || false,
    draftTip: !document.getElementById("draft-tip")?.classList.contains("hidden"),
  };
})()`);
check("草稿恢复：平台卡 selected + 步骤 3/6 完成 + 已选清单回填", r.platformSelected && r.dot3done && r.dot6done && r.adcInList && r.pidInList && r.chip3done && r.draftTip, JSON.stringify(r));
await new Promise((r) => setTimeout(r, 800));
check("恢复全程零 EXC / 零 HTTP≥400", events.length === 0, events.slice(0, 5).join(" | ") || "clean");
// 清理草稿，避免污染后续手工使用
await Eval(`localStorage.removeItem("firstep.draft.v1")`);
process.exit(process.exitCode || 0);
