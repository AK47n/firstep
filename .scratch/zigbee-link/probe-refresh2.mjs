// 复现「刷新后板定义加载不出」：选平台 + 加模块 → 等草稿落盘 → 刷新 →
// 检查引脚卡是否永久停在「板定义加载中…」（pinBoard 为 null、无 /api/boards 请求）。
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8814";
const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(15000);
const logs = [];
page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
const boardReqs = [];
page.on("request", (r) => { if (r.url().includes("/api/boards")) boardReqs.push(r.url()); });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("#platforms .platform-card:not(.disabled)");
await page.click("#platforms .platform-card:not(.disabled)");
await page.waitForSelector("#module-grid .module-card[data-add='led']");
await page.click("#module-grid .module-card[data-add='led']");
await page.waitForTimeout(900);  // 等草稿 debounce(400ms) 落盘

// 刷新前基线
const draft = await page.evaluate(() => localStorage.getItem("firstep.draft.v1"));
const before = await page.evaluate(() => ({
  empty: document.querySelector("#pin-config-empty")?.textContent || "",
  bodyHidden: document.querySelector("#pin-config-body")?.classList.contains("hidden") ?? null,
  svg: document.querySelector("#pin-board-svg")?.childElementCount ?? -1,
}));
console.log("BEFORE refresh:", JSON.stringify(before));
console.log("draft saved:", draft ? draft.slice(0, 120) : "(none)");

// 刷新
boardReqs.length = 0;
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
const after = await page.evaluate(() => ({
  empty: document.querySelector("#pin-config-empty")?.textContent || "",
  bodyHidden: document.querySelector("#pin-config-body")?.classList.contains("hidden") ?? null,
  svg: document.querySelector("#pin-board-svg")?.childElementCount ?? -1,
  selected: document.querySelector("#platforms .platform-card.selected .name")?.textContent || "",
}));
console.log("AFTER refresh:", JSON.stringify(after));
console.log("boards reqs after refresh:", boardReqs.join(" | ") || "(none)");
console.log("page errors:", logs.join("\n") || "(none)");

// 再点一次已选平台卡片（用户直觉操作）→ 是否恢复？
await page.click("#platforms .platform-card.selected").catch(() => {});
await page.waitForTimeout(1500);
const afterClick = await page.evaluate(() => ({
  empty: document.querySelector("#pin-config-empty")?.textContent || "",
  svg: document.querySelector("#pin-board-svg")?.childElementCount ?? -1,
}));
console.log("AFTER re-click same platform:", JSON.stringify(afterClick));
console.log("boards reqs after click:", boardReqs.join(" | ") || "(none)");
await page.screenshot({ path: ".scratch/zigbee-link/shot-after-refresh2.png", fullPage: false });
await browser.close();
