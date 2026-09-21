// smoke-page.mjs — 真浏览器冒烟 + **加载期监听器记账**（工单 frontend-boot-module/02）。
//
// 为什么要有它：这次改动是"把接线从求值期搬到别处"（02 只是把宿主块搬进 boot.js；03/04 才动
// 接线本身）。能不能证明"行为一字不变"，靠的不是"测试全绿"，而是**同一支冒烟在改前 / 改后
// 跑出的记账逐条相同**——监听器的 target + 事件类型 + 数量，一个不许变。
//
// 判据（一次性证据，不进闸门；真浏览器门禁另有 26 条用例）：
//   1. 0 个 pageerror / 0 个模块图链接错误（"does not provide an export named …" 会在这里现形：
//      2026-09-12 整页死就是这条）
//   2. 页面渲染实况：平台卡 / 步骤导航 / 总览 / 词表 / 检测栏目卡 / 交付区
//   3. fx 模块底部的 window 探针桥仍在（模块仍被消费者加载）
//   4. 5 个"靠被加载才接线"的模块各自的绑定都在（03 之后由显式 init 承担）
//   5. #delivery-actions 加载即被写（delivery.js 的首帧 DOM 写）
//   6. 一次真点击有行为反应（#btn-params-chat）
//   7. id 总数（555）——markup 没被动过的旁证
//
// 用法：node .scratch/frontend-boot-module/smoke-page.mjs [--out smoke-after.txt]
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import { startServer } from "../../tests/browser/server.mjs";

const out = tee(fileURLToPath(import.meta.url), process.argv.slice(2));

// fx 模块底部的探针桥（证明模块仍被消费者加载）
const BRIDGES = ["waitLabel", "pdfFilterEntries", "moduleGridHTML", "taskCardHTML", "scoreChecklistItemsHTML", "settingsSectionHead"];

// 5 个"靠被加载才接线"的模块 → 它们顶层绑定的代表性子集（工单 03 会把它们改成显式 init）
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 加载前挂钩：把页面脚本注册的监听器记成 "<目标>#<类型>"
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
  await page.waitForTimeout(1500);   // 等 /api/state 与各 init 落地

  const facts = await page.evaluate((bridgeNames) => ({
    ids: document.querySelectorAll("[id]").length,
    platforms: document.querySelectorAll("#platforms .platform-card").length,
    stepNav: document.querySelectorAll("#step-nav > *").length,
    hwcheckPlatforms: document.querySelectorAll("#hwcheck-platforms > *").length,
    genOverview: (document.getElementById("gen-overview") || {}).innerHTML?.length || 0,
    glossary: (document.getElementById("glossary-card") || {}).innerHTML?.length || 0,
    deliveryActions: (document.getElementById("delivery-actions") || {}).innerHTML?.length || 0,
    bridges: Object.fromEntries(bridgeNames.map((n) => [n, typeof window[n]])),
    listeners: window.__listeners,
  }), BRIDGES);

  const msgBefore = await page.locator("#params-chat-msg").textContent();
  await page.locator("#btn-params-chat").dispatchEvent("click");
  await page.waitForTimeout(400);
  const msgAfter = await page.locator("#params-chat-msg").textContent();

  const linkErrors = errors.filter(
    (e) => e.startsWith("pageerror:") || /does not provide an export|Failed to fetch dynamically/.test(e)
  );
  const missingBridges = BRIDGES.filter((n) => facts.bridges[n] !== "function");
  const seen = new Set(facts.listeners);
  const missingBindings = Object.entries(BINDINGS)
    .map(([mod, want]) => [mod, want.filter((w) => !seen.has(w))])
    .filter(([, miss]) => miss.length);
  const sorted = [...facts.listeners].sort();
  const digest = sorted.join("|").split("").reduce((h, c) => ((h * 31 + c.charCodeAt(0)) >>> 0), 7);

  const checks = [
    ["0 个 pageerror / 模块图链接错误", linkErrors.length === 0],
    ["fx 探针桥全在", missingBridges.length === 0],
    [`加载期监听器记账 ${facts.listeners.length} 条（仪器有效）`, facts.listeners.length > 100],
    ["5 个模块的接线全在（监听器记账）", missingBindings.length === 0],
    ["delivery.js 加载即写 #delivery-actions", facts.deliveryActions > 0],
    ["点击 #btn-params-chat 有行为反应", msgBefore !== msgAfter],
    ["平台卡 / 步骤导航 / 总览 / 词表 / 检测栏目都渲染了",
      facts.platforms > 0 && facts.stepNav > 0 && facts.genOverview > 0 && facts.glossary > 0 && facts.hwcheckPlatforms > 0],
  ];

  console.log(`服务: ${server.url}`);
  console.log(`记账：${facts.listeners.length} 条；排序后指纹 ${digest}；id ${facts.ids}；`
    + `平台卡 ${facts.platforms}；步骤导航 ${facts.stepNav}；总览 ${facts.genOverview} 字符；`
    + `词表 ${facts.glossary} 字符；检测卡 ${facts.hwcheckPlatforms}；交付区 ${facts.deliveryActions} 字符`);
  for (const [name, ok] of checks) console.log(`  ${ok ? "✓" : "✗"} ${name}`);
  if (missingBridges.length) console.log("  缺桥: " + missingBridges.join(", "));
  for (const [mod, miss] of missingBindings) console.log(`  缺绑定 ${mod}: ${miss.join(", ")}`);
  console.log(`  HTTP >=400（记账不判红）: ${httpFailures.length ? [...new Set(httpFailures)].join(" | ") : "（无）"}`);
  for (const e of errors) console.log("  ! " + e);
  console.log("\n--- 监听器记账（原序，逐条可对）---");
  for (const l of facts.listeners) console.log("  " + l);
  const failed = checks.filter(([, ok]) => !ok).length;
  console.log(`\n${failed === 0 ? "PASS" : `FAIL（${failed} 项）`}；证据 ${out}`);
  process.exitCode = failed === 0 ? 0 : 1;
} finally {
  if (browser) await browser.close();
  await server.stop();
}
