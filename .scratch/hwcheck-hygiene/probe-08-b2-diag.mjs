// probe-08-b2-diag.mjs — 临时诊断：B2（丢一发登记 → 重试救回）现在为什么红。
//
// 只做一件事：把 `page.route("/api/tabs/register")` 上的**每一发请求**按时间打印出来，
// 并同时记录产品的两条时间线（reload 的时刻、dropNext 的时刻）。
// 判据不在这里——这里只回答"一共发了几发、每发什么时候、被丢的是哪一发"。
//
// 用法：node .scratch/hwcheck-hygiene/probe-08-b2-diag.mjs
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const t0 = Date.now();
const stamp = () => `+${String(Date.now() - t0).padStart(6)}ms`;
const log = (...args) => console.log(`[DEBUG-b2] ${stamp()}`, ...args);

const server = await startServer({ launcher: true });
log("服务已起", server.url);
const browser = await chromium.launch();
const page = await browser.newPage();

let attempts = 0;
let dropNext = false;
await page.route("**/api/tabs/register", async (route) => {
  attempts++;
  const n = attempts;
  const drop = dropNext;
  if (dropNext) dropNext = false;
  log(`请求 #${n}  drop=${drop}  url=${route.request().url().split("/").pop()}`);
  if (drop) { await route.abort("failed"); log(`请求 #${n} 已 abort(failed)`); return; }
  await route.continue().catch((e) => log(`请求 #${n} continue 失败: ${e.message}`));
});

try {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#hwcheck-platforms .platform-card", { state: "attached", timeout: 30000 });
  await page.waitForTimeout(1200);            // 让首屏那一发落定
  const before = attempts;
  log(`reload 前 attempts=${before}`);
  dropNext = true;
  log("dropNext=true，准备 reload");
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  log("reload 返回（domcontentloaded）");
  await page.waitForTimeout(4000);            // 重试预算 300ms，给足观察窗
  log(`reload 后 attempts=${attempts}（本段 ${attempts - before} 发）`);
  const epoch = await page.evaluate(() => performance.timeOrigin);
  log(`新文档 epoch=${epoch}`);
} catch (e) {
  log(`异常：${e.message}`);
} finally {
  await browser.close();
  const alive = await fetch(server.url + "/api/health").then((r) => r.ok).catch(() => false);
  log(`收尾：服务还活着=${alive}`);
  await server.stop();
}
