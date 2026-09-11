// 工单 real-acceptance/06 体检页面探针：**真浏览器 + 真端点**——打开设置页 →
// 展开「环境体检」卡（`[data-collapse-id="env-check"]`，折叠状态会让内部元素 display:none）
// → 点「一键体检」→ 读 `#env-check-results` 里 CCS 相关行的**渲染文本**。
//
// 这是验收「体检页能看到说明」的页面级证据（probe-06-env-render.mjs 证的是
// 「真载荷 → 真渲染函数」，本脚本证的是「渲染结果真的落进页面」）。
// 姿势用 .scratch/browser-harness.mjs 的助手（工单 07）。
//
// 用法：node .scratch/real-acceptance/probe-06-env-page.mjs
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";
import { expandCard, pollUntil } from "../browser-harness.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
const EVID = "C:/Users/luoji/Desktop/firstep/.scratch/real-acceptance";

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1418, height: 900 } });
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 240)));

await page.goto(BASE, { waitUntil: "networkidle" });
await page.click('button[data-tab="settings"]');
const card = await expandCard(page, '[data-collapse-id="env-check"]');
console.log(`note 环境体检卡展开：原折叠=${card.wasCollapsed}，见证=${card.witness}`);
await page.waitForSelector("#btn-env-check", { state: "visible", timeout: 15000 });
await page.click("#btn-env-check");
// 体检 = 静态探测 + 文本/视觉双通道各一次真调用（各消耗一次最小调用）→ 轮询 DOM
const poll = await pollUntil(page, () => ({
  done: !!document.querySelector('[data-env-row="ccs-note"]')
    && !document.querySelector('[data-env-row="ccs-note"]').textContent.includes("检查中"),
  rows: [...document.querySelectorAll("#env-check-results .env-row")].map((r) => ({
    key: r.dataset.envRow, text: r.textContent.replace(/\s+/g, " ").trim(),
  })),
}), { timeoutMs: 120000, every: 1500, label: "一键体检" });

const rows = poll.rows || [];
for (const r of rows.filter((x) => x.key.startsWith("ccs-"))) console.log(`[${r.key}] ${r.text}`);
await page.screenshot({ path: `${EVID}/shot-06-env-ccs-note.png`, fullPage: false });

const note = rows.find((r) => r.key === "ccs-note");
const fail = [];
if (!poll.done) fail.push("体检未出终态（超时）");
if (!note) fail.push("页面里没有 ccs-note 行");
else {
  if (!note.text.includes("三件逐件独立探测")) fail.push("说明行缺「三件逐件独立探测」");
  if (!note.text.includes("可能来自不同 CCS 安装目录")) fail.push("说明行缺跨目录提示");
  if (!note.text.includes("一个 CCS 版本 = 一套工具链")) fail.push("说明行缺要打破的直觉");
  if (!note.text.includes("（跨安装目录）")) fail.push("说明行缺跨目录判定");
  if (!note.text.includes("编译器 ccs2050")) fail.push("说明行缺本机编译器来源根");
}
for (const [key, tail] of [["ccs-sdk", "ccs2051"], ["ccs-compiler", "ccs2050"], ["ccs-sysconfig", "ccs2051"]]) {
  const row = rows.find((r) => r.key === key);
  if (!row) fail.push(`页面里没有 ${key} 行`);
  else if (!row.text.includes("安装根") || !row.text.includes(tail)) fail.push(`${key} 行缺安装根 ${tail}`);
}
if (pageErrors.length) fail.push(`页面 JS 异常 ${pageErrors.length} 条：${pageErrors[0]}`);

const verdict = fail.length ? `FAILURES: ${fail.length}（${fail.join("；")}）` : "ALL PASS";
console.log(`\n${verdict}`);
writeFileSync(`${EVID}/probe-06-env-page.txt`,
  `# 工单 06 体检页面探针（真浏览器 + 真端点，${new Date().toISOString()}）\n\n`
  + rows.filter((r) => r.key.startsWith("ccs-") || r.key === "toolchain-mspm0")
    .map((r) => `[${r.key}] ${r.text}`).join("\n")
  + `\n\n页面 JS 异常：${pageErrors.length} 条\n${verdict}\n`, "utf-8");

await browser.close();
process.exit(fail.length ? 1 : 0);
