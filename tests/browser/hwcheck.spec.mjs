// tests/browser/hwcheck.spec.mjs — 真机验收（工单 module-hwcheck/02）：
// **真浏览器 + 真后端**把「硬件检测」栏目点一遍——预览 → 生成检测工程 → 真编译
// → 上板清单勾选 → 刷新回显 → 最近几次检测。
//
// 为什么要有这一层：`tests/js/*.test.mjs` 是纯函数 + 静态接线断言——它能证明
// 「fx 渲染出的 HTML 里有 data-hwcheck-check」「ui 里写了事件委托」，但证明不了
// **点下去真的生成、勾选真的存住、刷新真的回来**：这些是运行时行为（事件委托 /
// localStorage / 真 HTTP / 真工具链），只有真浏览器能作证。
//
// 前置（一次性）：npm install && npx playwright install chromium
// 运行：node --test tests/browser/hwcheck.spec.mjs
// **不在默认 `node --test "tests/js/*.test.mjs"` 里**——真机验收要起服务 + 开浏览器
// （生成一次还要真跑 UV4），不该让每次改前端都付这个成本；改动本栏目交互时手动跑。
//
// 假件：无。服务夹具（tests/browser/server.mjs）起的是**真后端**（真库真母版），
// 端口 8791——不动用户默认的 8000。检测生成零 LLM，不花额度。
//
// 隔离：生成父目录是本次的临时目录（不写用户桌面），跑完删掉。
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

let server = null;
let browser = null;
let page = null;
let parentDir = "";

const HWCHECK_TAB = 'nav button[data-tab="hwcheck"]';

test.before(async () => {
  parentDir = mkdtempSync(join(tmpdir(), "firstep-hwcheck-"));
  server = await startServer();
  browser = await chromium.launch();
  page = await browser.newPage();
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();
  try { rmSync(parentDir, { recursive: true, force: true }); } catch { /* 临时目录 */ }
});

// openTab()：打开页面并切到硬件检测栏目（首帧 / 刷新后都用它）。
async function openTab() {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
}

// setParent(dir)：填输出父目录并触发 change（栏目据此重载最近列表）。
// 不用「选择文件夹」——那会弹服务端原生对话框，自动化点不了。
async function setParent(dir) {
  await page.fill("#hwcheck-parent", dir);
  await page.dispatchEvent("#hwcheck-parent", "change");
}

test("栏目可点开：平台卡可选、预览出真 main.c（零 LLM 渲染）", async () => {
  await openTab();
  await page.waitForSelector("#hwcheck-platforms .platform-card");
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]");
  const code = await page.textContent("[data-hwcheck-code]");
  assert.ok(code.includes("int main(void)"), "预览应给出 main.c 文本");
  assert.ok(code.includes("hwcheck_report"), "应有自检结果出口");
  assert.ok(code.includes("板子活着"), "应有一句「板子活着」的上电自报");
});

test("生成检测工程：新子目录 + 工程面板 + 上板清单 + 最近列表都出现", async () => {
  await setParent(parentDir);
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });

  const pathText = await page.textContent(".hwcheck-path");
  assert.ok(pathText.includes(parentDir), "工程应生成在指定父目录下：" + pathText);
  assert.match(pathText, /hwcheck-stm32-\d{8}-\d{6}/, "目录名形态固定");
  // 真落盘（不是只画了块面板）
  const onDisk = readdirSync(parentDir);
  assert.equal(onDisk.length, 1, "父目录里应恰好一个新工程目录");
  assert.match(onDisk[0], /^hwcheck-stm32-\d{8}-\d{6}$/);

  const rows = await page.locator("#hwcheck-checklist .hwcheck-check").count();
  assert.ok(rows >= 3 && rows <= 6, "清单 3-6 条，实际 " + rows);
  const expectText = await page.textContent("#hwcheck-checklist .hwcheck-check-expect");
  const tipText = await page.textContent("#hwcheck-checklist .hwcheck-check-tip");
  assert.ok(expectText.includes("应看到："), "每条要讲清应看到什么");
  assert.ok(tipText.includes("不对先查："), "每条要讲清不对先查哪里");

  await page.waitForSelector("#hwcheck-recent .hwcheck-recent-row");
  const recent = await page.textContent("#hwcheck-recent");
  assert.ok(recent.includes(onDisk[0]), "最近几次检测应列出刚生成的这一个");
});

test("勾选态本地备忘 + 刷新回显（清单是给人照着比的，不回显就等于没有）", async () => {
  const first = page.locator("#hwcheck-checklist .hwcheck-check").first();
  await first.click();
  await page.waitForSelector("#hwcheck-checklist .hwcheck-check.done");
  let progress = await page.textContent("#hwcheck-checklist .hwcheck-hint");
  assert.ok(/已确认 1 \/ \d+ 条/.test(progress), "进度应显示已确认 1 条：" + progress);

  await openTab();   // 刷新 + 重进栏目
  await page.waitForSelector("#hwcheck-project .hwcheck-path", { timeout: 30000 });
  const restored = await page.textContent(".hwcheck-path");
  const onDisk = readdirSync(parentDir)[0];
  assert.ok(restored.includes(onDisk), "刷新后应回到上次看的那个检测工程");
  const checked = await page.locator("#hwcheck-checklist .hwcheck-check.done").count();
  assert.equal(checked, 1, "刷新后勾选态应回显");

  await page.locator("#hwcheck-checklist .hwcheck-check").first().click();
  await page.waitForFunction(
    () => document.querySelectorAll("#hwcheck-checklist .hwcheck-check.done").length === 0);
});

test("编译复用既有面板与判读：真 UV4 编译绿（工具链缺失时本用例如实红）", async () => {
  await page.click("[data-hwcheck-compile]");
  await page.waitForSelector("#hwcheck-compile-status.ok", { timeout: 180000 });
  const status = await page.textContent("#hwcheck-compile-status");
  assert.ok(status.includes("编译成功"), "状态行应报编译成功：" + status);
  assert.ok(/0 Error/.test(status), "应是 0 Error：" + status);
});
