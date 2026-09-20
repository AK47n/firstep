// smoke-page.mjs — 装载清单改动的真浏览器验证（feature: frontend-import-fossils，工单 01）。
//
// 判据（一次性证据，不进闸门；既有 browser 用例在 HEAD 上就有已知红，接闸门是另一件事）：
//   1. 页面加载 0 个 pageerror / 0 个模块图链接错误（import 链接失败会在这里现形：
//      "does not provide an export named …" —— 2026-09-12 整页死就是这条）
//   2. 被删装载的 fx 模块**仍被它们的 ui 消费者加载**：探针桥（window.<纯函数>）仍在
//   3. 转裸 import 的 5 个 ui 模块**顶层接线真的执行了**：加载期监听器记账（下面钩住
//      addEventListener 记的账）里必须出现它们各自的绑定；delivery.js 另验"加载即写
//      #delivery-actions"；params-chat 再补一次真点击的行为证据
//   4. 侧栏 / 硬件检测平台卡 / 总览 / 词表照旧渲染（宿主 startup 的 init 链走通）
//
// HTTP >=400 单独记账（不判红）：本机未配 AI key 时 `POST /api/generate/preview-dir`
// 会 400 并在 console 留一条 error——改前改后都有，属既有基线（见 smoke-before.txt）。
//
// 用法：node .scratch/frontend-import-fossils/smoke-page.mjs
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

// 被删装载的 fx 模块 → 它们底部的探针桥必须仍在（证明模块仍被消费者加载）
const BRIDGES = ["waitLabel", "pdfFilterEntries", "moduleGridHTML", "taskCardHTML", "scoreChecklistItemsHTML", "settingsSectionHead"];

// 5 个"转裸 import / 删装载"的 ui 模块 → 它们顶层绑定的监听器（代表性子集）
const BINDINGS = {
  "ui/generate-revise.js": ["#btn-revise-analyze#click", "#btn-revise-apply#click", "#btn-revise-load-dir#click"],
  "ui/generate-tasks.js": ["#btn-tasks-plan#click", "#btn-tasks-replan#click", "window#revise-context-loaded"],
  "ui/params.js": ["#btn-params-scan#click", "#params-grid#click", "window#tasks-invalidated"],
  "ui/params-chat.js": ["#btn-params-chat#click", "#params-chat#keydown", "window#step11-state-changed"],
  "ui/delivery.js": ["window#revise-context-loaded", "window#tasks-invalidated"],
};

const server = await startServer();
const errors = [];
const httpFailures = [];
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage();

  // 加载前挂钩：把页面脚本注册的监听器记成 "<目标>#<类型>"（目标：window / document / #id / .class）
  await page.addInitScript(() => {
    window.__listeners = [];
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type) {
      try {
        const t = this;
        let desc = (t && t.tagName) || String(t);
        if (t === window) desc = "window";
        else if (t === document) desc = "document";
        else if (t && t.id) desc = "#" + t.id;
        else if (t && typeof t.className === "string" && t.className) desc = "." + t.className.split(/\s+/)[0];
        window.__listeners.push(desc + "#" + type);
      } catch (e) { /* 记账失败不影响页面 */ }
      return orig.apply(this, arguments);
    };
  });

  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console.error: " + m.text()); });
  page.on("response", (r) => {
    if (r.status() >= 400) httpFailures.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });

  await page.goto(server.url, { waitUntil: "load" });
  await page.waitForTimeout(1500); // 等 /api/state 与各 init 落地

  const facts = await page.evaluate((bridgeNames) => ({
    stepNav: document.querySelectorAll("#step-nav > *").length,
    hwcheckPlatforms: document.querySelectorAll("#hwcheck-platforms > *").length,
    genOverview: (document.getElementById("gen-overview") || {}).innerHTML?.length || 0,
    glossary: (document.getElementById("glossary-card") || {}).innerHTML?.length || 0,
    deliveryActions: (document.getElementById("delivery-actions") || {}).innerHTML?.length || 0,
    bridges: Object.fromEntries(bridgeNames.map((n) => [n, typeof window[n]])),
    listeners: window.__listeners,
  }), BRIDGES);

  // 行为补充：params-chat 在"无会话目录"时会往 #params-chat-msg 写提示（证明监听器活着）
  const msgBefore = await page.locator("#params-chat-msg").textContent();
  await page.locator("#btn-params-chat").dispatchEvent("click");
  await page.waitForTimeout(400);
  const msgAfter = await page.locator("#params-chat-msg").textContent();

  const missingBridges = BRIDGES.filter((n) => facts.bridges[n] !== "function");
  const seen = new Set(facts.listeners);
  const missingBindings = Object.entries(BINDINGS)
    .map(([mod, want]) => [mod, want.filter((w) => !seen.has(w))])
    .filter(([, miss]) => miss.length);
  const linkErrors = errors.filter(
    (e) => e.startsWith("pageerror:") || /does not provide an export|Failed to fetch dynamically/.test(e)
  );
  const checks = [
    ["0 个 pageerror / 模块图链接错误", linkErrors.length === 0],
    ["被删装载的 fx 探针桥全在（模块仍被消费者加载）", missingBridges.length === 0],
    [`加载期监听器记账共 ${facts.listeners.length} 条（仪器有效）`, facts.listeners.length > 100],
    ["5 个模块的顶层接线全在（监听器记账）", missingBindings.length === 0],
    ["delivery.js 加载即写 #delivery-actions", facts.deliveryActions > 0],
    ["点击 #btn-params-chat 有行为反应", msgBefore !== msgAfter],
    ["#step-nav 已渲染", facts.stepNav > 0],
    ["#hwcheck-platforms 已渲染", facts.hwcheckPlatforms > 0],
  ];

  console.log(`服务: ${server.url}`);
  for (const [name, ok] of checks) console.log(`  ${ok ? "✓" : "✗"} ${name}`);
  if (missingBridges.length) console.log("  缺桥: " + missingBridges.join(", "));
  for (const [mod, miss] of missingBindings) console.log(`  缺绑定 ${mod}: ${miss.join(", ")}`);
  console.log(`  HTTP >=400（记账不判红）: ${httpFailures.length ? [...new Set(httpFailures)].join(" | ") : "（无）"}`);
  for (const e of errors) console.log("  ! " + e);
  const failed = checks.filter(([, ok]) => !ok).length;
  console.log(failed === 0 ? "\nPASS" : `\nFAIL（${failed} 项）`);
  process.exitCode = failed === 0 ? 0 : 1;
} finally {
  if (browser) await browser.close();
  await server.stop();
}
