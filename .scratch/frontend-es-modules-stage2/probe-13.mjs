// 工单 13 实况探针：引脚-多实例簇迁 ui/generate-pins.js 后行为完好性。
// 验证：平台卡点选 → 板图 SVG 渲染（board caption + 引脚圆）→ 加 led 模块 →
// 实例配置卡渲染（.instance-mod / .instance-row）→ 板图绑脚一回（选引脚 → 点
// pin-cand 圆 → 实例行显示所绑引脚）→ 角色清单存在 → 全程零 EXC。
// 识别不到跨模块 window 桥（ui 模块不挂桥），一律 DOM 实况驱动。
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
    events.push("EXC@L" + d.lineNumber + "C" + d.columnNumber + ": " + (d.exception?.description || d.text).slice(0, 200));
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    events.push("LOG: " + m.params.entry.text.slice(0, 250));
  }
  if (m.method === "Network.loadingFailed") {
    events.push("NETFAIL: " + m.params.errorText + " " + (m.params.blockedReason || ""));
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
const check = (name, ok, extra = "") => {
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " [" + extra + "]" : ""));
  if (!ok) process.exitCode = 1;
};

await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Network.enable");
// 模块静态 import 可执行性直探（语法错误会在此炸出异常）
const impOk = await Eval(`import("/js/ui/generate-pins.js").then(() => "ok", (e) => "FAIL: " + e.message)`);
check("generate-pins.js 可动态 import（无语法/引用错误）", impOk === "ok", impOk);
// 清草稿保证确定性起点
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === "complete" && !!document.getElementById("platforms") && !!document.querySelector(".platform-card")`);
await new Promise((r) => setTimeout(r, 800));

// P1 平台卡点选 → 板图 SVG 渲染（board caption + 引脚圆 + 图例）
const p1 = await Eval(`(() => {
  const card = [...document.querySelectorAll("#platforms .platform-card")].find((c) => !c.classList.contains("disabled"));
  if (!card) return null;
  card.click();
  return true;
})()`);
check("点选就绪平台卡", p1 === true);
const boardOk = await waitFor(`!!document.querySelector("#pin-board-svg circle[data-pin]")`, 15000);
const p1b = await Eval(`(() => ({
  caption: document.getElementById("pin-board-caption")?.textContent || "",
  circles: document.querySelectorAll("#pin-board-svg circle[data-pin]").length,
  legend: (document.getElementById("pin-legend")?.textContent || "").length,
  bodyShown: !document.getElementById("pin-config-body")?.classList.contains("hidden"),
  pinEmptyHidden: document.getElementById("pin-config-empty")?.classList.contains("hidden"),
}))()`);
check("板图 SVG 渲染（caption+引脚圆+图例）", boardOk && p1b.caption && p1b.circles > 0 && p1b.legend > 0 && p1b.bodyShown, JSON.stringify(p1b));

// P2 加 led 模块 → 实例配置卡渲染（.instance-mod / .instance-row）
const p2 = await Eval(`(() => {
  const card = document.querySelector('#module-grid .module-card[data-add="led"]');
  if (!card) return "no-led-card";
  card.click();
  return "clicked";
})()`);
check("模块池有 led 卡并可点选", p2 === "clicked", p2);
const instOk = await waitFor(`!!document.querySelector("#card-instance-config") && !document.getElementById("card-instance-config").classList.contains("hidden") && !!document.querySelector("#instance-config .instance-mod")`);
const p2b = await Eval(`(() => ({
  mods: document.querySelectorAll("#instance-config .instance-mod").length,
  rows: document.querySelectorAll("#instance-config .instance-row").length,
  dot6: document.querySelector('.step-nav .step-dot[data-step="6"]')?.classList.contains("done") || false,
  roles: document.querySelectorAll("#pin-role-items .pin-role").length,
}))()`);
check("实例配置卡渲染（led 多实例 + 行数）", instOk && p2b.mods > 0 && p2b.rows > 0 && p2b.dot6, JSON.stringify(p2b));
// led 在 stm32 无引脚角色（状态数据本身 pins=0）——角色区应呈现占位文案（renderPinRoles 正常执行）
const p2r = await Eval(`document.getElementById("pin-role-items")?.textContent || ""`);
check("角色区占位（led 无引脚角色——数据本身）", p2r.includes("所选模块在此平台没有可配置的引脚角色"), p2r.slice(0, 40));

// P2.5 追加带引脚角色的模块（adc，stm32 pins=2）→ 角色清单渲染 .pin-role
const p25 = await Eval(`(() => {
  const card = document.querySelector('#module-grid .module-card[data-add="adc"]')
    || document.querySelector('#module-grid .module-card[data-add="key"]');
  if (!card) return "no-card";
  card.click();
  return card.dataset.add;
})()`);
check("追加带引脚角色的模块（adc/key）", p25 === "adc" || p25 === "key", p25);
await waitFor(`document.querySelectorAll("#pin-role-items .pin-role").length > 0`);
const p25b = await Eval(`(() => ({
  roles: document.querySelectorAll("#pin-role-items .pin-role").length,
  boundBadge: document.querySelectorAll("#pin-role-items .pin-role.bound").length,
}))()`);
check("角色清单渲染（adc 引脚角色 > 0）", p25b.roles > 0, JSON.stringify(p25b));

// P3 板图绑脚一回：选引脚 → 点 pin-cand 圆 → 实例行显示所绑引脚
const p3 = await Eval(`(() => {
  const btn = document.querySelector("#instance-config .instance-row [data-pick]");
  if (!btn) return "no-pick-btn";
  btn.click();
  return true;
})()`);
check("点「选引脚」进入选脚模式", p3 === true);
const hintShown = await waitFor(`document.getElementById("instance-pin-hint") && !document.getElementById("instance-pin-hint").classList.contains("hidden")`);
const p3b = await Eval(`(() => {
  const cands = [...document.querySelectorAll("#pin-board-svg circle[data-pin].pin-cand")];
  if (!cands.length) return { cands: 0 };
  const pin = cands[0].dataset.pin;
  cands[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));  // SVGElement 无 .click()
  return { cands: cands.length, pin };
})()`);
check("选脚模式出现候选圆（gpio_out 能力）", hintShown && p3b.cands > 0, JSON.stringify(p3b));
const boundOk = await waitFor(`(() => {
  const hint = document.getElementById("instance-pin-hint");
  const pin = document.querySelector("#instance-config .instance-row .instance-pin span");
  return hint?.classList.contains("hidden") && pin && pin.textContent.trim() !== "自动分配" && !/^#/.test(pin.textContent.trim());
})()`);
const p3c = await Eval(`(() => ({
  pin: document.querySelector("#instance-config .instance-row .instance-pin span")?.textContent.trim() || null,
  hintHidden: document.getElementById("instance-pin-hint")?.classList.contains("hidden"),
}))()`);
check("绑脚一回（实例行显示所绑引脚 + 提示收起）", boundOk && p3c.pin && p3c.pin !== "自动分配", JSON.stringify(p3c));

await new Promise((r) => setTimeout(r, 1200));
const excs = events.filter((e) =>
  e.startsWith("EXC") || e.startsWith("NETFAIL")
  || (e.startsWith("HTTP") && !e.includes("favicon"))
  || (e.startsWith("LOG") && !e.includes("Failed to load resource")));
check("全程零 EXC / 零网络失败", excs.length === 0, excs.slice(0, 5).join(" | ") || "clean");
console.log("=== events ===");
events.filter((e) => !e.includes("favicon")).slice(0, 8).forEach((e) => console.log(e));
process.exit(process.exitCode || 0);
