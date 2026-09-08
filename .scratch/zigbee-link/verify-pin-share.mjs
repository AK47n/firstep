// 同脚 共享/冲突 判据前端验证（工单 pin-share-rule/01）：mspm0 选
// pid+debug_uart+uwb_uart → 角色清单应把 灰度×UART 同脚标冲突、纯灰度组标
// 合法共享；再点自动配置看 ⚠/🔗 标注。stm32 选 config+pid → DIP×灰度同脚 = 冲突。
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8814";
const OUT = ".scratch/zigbee-link";
const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(30000);

async function setup(platformCardIdx, slugs) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => localStorage.clear());  // 清草稿，避免恢复旧平台触发切换确认
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("#platforms .platform-card:not(.disabled)");
  await page.click(`#platforms .platform-card:not(.disabled):nth-of-type(${platformCardIdx})`);
  // 兜底：任何确认弹窗（切换平台）点「切换」
  const confirmBtn = await page.locator(".ref-files-overlay button:has-text('切换')").first().click().catch(() => null);
  await page.waitForSelector("#module-grid");
  for (const s of slugs) {
    await page.waitForSelector(`#module-grid .module-card[data-add='${s}']`);
    await page.click(`#module-grid .module-card[data-add='${s}']`);
    await page.waitForTimeout(400);
  }
  await page.waitForSelector("#pin-config-body:not(.hidden)", { timeout: 15000 });
  await page.waitForTimeout(500);
}

// ---- 场景 1：mspm0 pid+debug_uart+uwb_uart（灰度×UART 冲突 + 灰度纯组合法共享）
await page.setViewportSize({ width: 1440, height: 900 });
await setup(2, ["pid", "debug_uart", "uwb_uart", "huidu"]);
const s1 = await page.evaluate(() => {
  const roles = [...document.querySelectorAll("#pin-role-items .pin-role")];
  const info = {};
  for (const el of roles) {
    const t = el.textContent;
    if (t.includes("GRAY_D1") || t.includes("GRAY_D6") || t.includes("L1") || t.includes("DEBUG_UART_RX") || t.includes("UWB_UART_TX")) {
      info[el.dataset.role] = t.replace(/\s+/g, " ").trim().slice(0, 120);
    }
  }
  return info;
});
console.log("mspm0 role statuses:", JSON.stringify(s1, null, 2));
await page.evaluate(() => {
  const el = document.getElementById("card-pin-config");
  if (el) el.scrollIntoView({ block: "start" });
});
await page.waitForTimeout(300);
await page.screenshot({ path: OUT + "/shot-pin-share-mspm0.png", fullPage: false });

// 自动配置 → 说明条 ⚠/🔗
await page.click("#btn-pin-auto");
await page.waitForTimeout(1200);
const auto1 = await page.evaluate(() => document.getElementById("pin-config-msg")?.textContent || "");
console.log("mspm0 auto msg:", auto1.replace(/\n/g, " | "));
await page.screenshot({ path: OUT + "/shot-pin-share-auto-mspm0.png", fullPage: false });

// ---- 场景 2：stm32 config+pid（DIP×灰度同脚 = 冲突）
await setup(1, ["config", "pid"]);
const s2 = await page.evaluate(() => {
  const roles = [...document.querySelectorAll("#pin-role-items .pin-role")];
  const info = {};
  for (const el of roles) {
    const t = el.textContent;
    if (t.includes("DIP0") || t.includes("GRAY_D1")) info[el.dataset.role] = t.replace(/\s+/g, " ").trim().slice(0, 120);
  }
  return info;
});
console.log("stm32 role statuses:", JSON.stringify(s2, null, 2));
await page.evaluate(() => document.getElementById("card-pin-config").scrollIntoView({ block: "start" }));
await page.waitForTimeout(300);
await page.screenshot({ path: OUT + "/shot-pin-share-stm32-dipgray.png", fullPage: false });

// ---- 场景 3：stm32 zigbee 家族（UART_3 同链路 = 合法共享）
await setup(1, ["zigbee_uart", "zigbee_uart_key", "zigbee_link"]);
const s3 = await page.evaluate(() => {
  const roles = [...document.querySelectorAll("#pin-role-items .pin-role")];
  const info = {};
  for (const el of roles) {
    const t = el.textContent;
    if (t.includes("ZIGBEE_UART_TX")) info[el.dataset.role] = t.replace(/\s+/g, " ").trim().slice(0, 120);
  }
  return info;
});
console.log("stm32 zigbee role statuses:", JSON.stringify(s3, null, 2));

await browser.close();
console.log("done");
