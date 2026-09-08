// 修复验证：草稿恢复后滚动到 7 引脚配置 + 6.5 多实例卡截图
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(15000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto("http://127.0.0.1:8814/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("#platforms .platform-card:not(.disabled)");
await page.click("#platforms .platform-card:not(.disabled)");
await page.waitForSelector("#module-grid .module-card[data-add='led']");
await page.click("#module-grid .module-card[data-add='led']");
await page.waitForTimeout(900);
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForSelector("#pin-config-body:not(.hidden)", { timeout: 15000 });
await page.waitForTimeout(800);
const state = await page.evaluate(() => ({
  pinBody: !document.querySelector("#pin-config-body")?.classList.contains("hidden"),
  svg: document.querySelector("#pin-board-svg")?.childElementCount ?? -1,
  instanceRows: document.querySelectorAll("#instance-config .instance-row").length,
  instanceConfigShown: !document.querySelector("#card-instance-config")?.classList.contains("hidden"),
  error: document.querySelector("#pin-config-empty")?.textContent || "",
}));
console.log("after refresh:", JSON.stringify(state));
await page.evaluate(() => {
  const el = document.getElementById("card-pin-config");
  if (el) el.scrollIntoView({ block: "start" });
});
await page.waitForTimeout(300);
await page.screenshot({ path: ".scratch/zigbee-link/shot-pin-after-refresh.png", fullPage: false });
console.log("page errors:", errors.join("; ") || "(none)");
await browser.close();
