// 复现「刷新后板定义加载不出」：选平台 + 加模块（引脚配置可见）→ 刷新 →
// 抓 console 错误 / /api/boards 请求 / 引脚卡占位文案，最终截图。
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8814";
const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(15000);

const logs = [];
page.on("console", (m) => logs.push(`[console:${m.type()}] ${m.text()}`));
page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
const boardReqs = [];
page.on("request", (r) => { if (r.url().includes("/api/boards")) boardReqs.push(r.url()); });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("#platforms .platform-card:not(.disabled)");
await page.click("#platforms .platform-card:not(.disabled)");
await page.waitForSelector("#module-grid .module-card[data-add='led']");
await page.click("#module-grid .module-card[data-add='led']");
await page.waitForSelector("#card-instance-config:not(.hidden)");
await page.waitForSelector("#pin-config-body:not(.hidden)", { timeout: 10000 }).catch(() => {});
const before = await page.evaluate(() => ({
  empty: document.querySelector("#pin-config-empty")?.textContent || "",
  bodyHidden: document.querySelector("#pin-config-body")?.classList.contains("hidden") ?? null,
}));
console.log("BEFORE refresh:", JSON.stringify(before));
console.log("boards reqs before:", boardReqs.join(" | "));

// ---- 刷新 ----
boardReqs.length = 0;
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);
const after = await page.evaluate(() => ({
  empty: document.querySelector("#pin-config-empty")?.textContent || "",
  bodyHidden: document.querySelector("#pin-config-body")?.classList.contains("hidden") ?? null,
  svgChildren: document.querySelector("#pin-board-svg")?.childElementCount ?? -1,
  platforms: document.querySelectorAll("#platforms .platform-card").length,
  selected: document.querySelector("#platforms .platform-card.selected .name")?.textContent || "",
}));
console.log("AFTER refresh:", JSON.stringify(after));
console.log("boards reqs after:", boardReqs.join(" | "));
console.log("page errors:", logs.filter((l) => l.startsWith("[pageerror]")).join("\n") || "(none)");
await page.screenshot({ path: ".scratch/zigbee-link/shot-after-refresh.png", fullPage: false });
await browser.close();
