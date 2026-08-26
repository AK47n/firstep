// 工单 10 实况探针：设置簇迁出后 tab 行为——分发器 loadSettings +
// loadRecentWorkflows + renderUsageStats → 表单回填 / 价格参考表 / 视觉预设/
// 折叠状态；保存按钮存在；跨簇接缝 setSettingsDeps（保存后 refreshState 重载
// 走按钮直连，探针只验证注册不抛）。全程零 EXC。
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
check("启动 init 完成", bootOk);
await Eval(`document.querySelector('nav button[data-tab="settings"]').click()`);
await waitFor(`document.getElementById("set-base-url")?.value || false`, 15000);
const st = await Eval(`(() => ({
  baseUrl: document.getElementById("set-base-url")?.value || "",
  model: document.getElementById("set-model")?.value || "",
  configPath: document.getElementById("set-config-path")?.textContent?.trim() || "",
  priceRows: document.querySelectorAll("#price-ref-rows tr").length,
  envBtn: !!document.getElementById("btn-env-check"),
  visionProvider: document.getElementById("set-vision-provider")?.value || "",
  saved: !!document.getElementById("btn-save-settings"),
  wfEmpty: document.getElementById("recent-workflows")?.textContent?.includes("暂无已完成") || false,
}))()`);
check("设置 tab 加载（表单回填 + 价格表 + 控件存在）", st.baseUrl.length > 0 && st.model.length > 0 && st.priceRows >= 3 && st.envBtn && st.saved, JSON.stringify(st));
// 折叠状态：首个可折叠设置卡应用了默认/记忆状态（collapsed 类存在与否都算应用成功——查 toggle 按钮存在）
const fold = await Eval(`(() => {
  const cards = [...document.querySelectorAll("#tab-settings [data-collapse-id]")];
  const withBtn = cards.filter((c) => c.querySelector(".card-collapse"));
  const master = document.getElementById("btn-settings-collapse-all");
  return { cards: cards.length, withBtn: withBtn.length, master: !!master, masterText: master?.textContent || "" };
})()`);
check("设置折叠（initSettingsCollapse 挂载按钮 + 总开关标签）", fold.cards > 0 && fold.withBtn > 0 && fold.master, JSON.stringify(fold));
// 视觉预设下拉联动（choose zhipu → base_url 变 + hint）
const vis = await Eval(`(() => {
  const sel = document.getElementById("set-vision-provider");
  sel.value = "zhipu";
  sel.dispatchEvent(new Event("change"));
  const base = document.getElementById("set-vision-base-url")?.value || "";
  const hint = document.getElementById("vision-provider-hint")?.textContent || "";
  return { base, hintLen: hint.length };
})()`);
check("视觉预设切换（applyVisionPreset 联动）", vis.base.includes("bigmodel.cn") && vis.hintLen > 0, JSON.stringify(vis));
await new Promise((r) => setTimeout(r, 1000));
const excs = events.filter((e) => e.startsWith("EXC") || (e.startsWith("HTTP") && !e.includes("favicon")));
check("全程零 EXC / 零 HTTP≥400（favicon 除外）", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
process.exit(process.exitCode || 0);
