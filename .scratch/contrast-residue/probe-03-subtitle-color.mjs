// .scratch/contrast-residue/probe-03-subtitle-color.mjs —— `.pin-subtitle` 的**零观感取证**
// （工单 contrast-residue/02）。
//
// 要证明的事：把 `color: var(--fg)`（**没定义过的令牌**，浏览器按 `inherit` 处理）改成
// `color: var(--text)` 之后，**两主题下渲染出来的颜色逐字节相同**——这条修复不改变任何观感，
// 它只是把那句"其实一直靠继承"的声明写对。
//
// 取证两类（都跑真 Chromium + 真后端）：
//   ① **计算样式**：`getComputedStyle(#pin-fixed-sub).color` 与 `--fg` 的解析值（应为空串）；
//   ② **真像素**：该元素一张 PNG（人眼记录），文件名带 tag，改前/改后互不覆盖。
//
// 跑法（仓库根；**不要与 pytest 同时跑**）：
//     node .scratch/contrast-residue/probe-03-subtitle-color.mjs --tag before
//     node .scratch/contrast-residue/probe-03-subtitle-color.mjs --tag after
// ⚠ 两次跑的**操作路径必须一致**（同一个平台、同一张卡），否则比的是两个状态。
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
};
const TAG = arg("--tag", "cur").replace(/[^\w.-]/g, "");
mkdirSync(HERE, { recursive: true });

const server = await startServer();
const browser = await chromium.launch();
const rows = [];
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(600);
    // —— 最少的操作路径：选平台 + 加一张卡 ⇒ 引脚卡（`#pin-config-body`）显示出来 ——
    await page.click('nav button[data-tab="generate"]', { timeout: 8000 }).catch(() => {});
    await page.locator("#platforms .platform-card", { hasText: "STM32" }).first()
      .click({ timeout: 8000 }).catch(() => {});
    const ready = await page.waitForFunction(
      () => document.querySelectorAll("#module-grid .module-card:not(.off)").length > 0,
      undefined, { timeout: 20000 }).then(() => true).catch(() => false);
    if (!ready) { console.log(`[${theme}] **没造出来**：模块网格里没有可选的卡`); continue; }
    await page.locator("#module-grid .module-card:not(.off)").first().click({ timeout: 8000 }).catch(() => {});
    const shown = await page.waitForFunction(() => {
      const el = document.getElementById("pin-fixed-sub");
      if (!el) return false;
      const r = el.getBoundingClientRect();
      return r.width > 4 && r.height > 4;
    }, undefined, { timeout: 20000 }).then(() => true).catch(() => false);
    const data = await page.evaluate((t) => {
      const el = document.getElementById("pin-fixed-sub");
      if (!el) return { missing: "页面上没有 #pin-fixed-sub" };
      const cs = getComputedStyle(el);
      const root = getComputedStyle(document.documentElement);
      return {
        theme: t,
        text: (el.textContent || "").trim(),
        class: el.className,
        color: cs.color,
        fg: root.getPropertyValue("--fg").trim(),        // 未定义 ⇒ 空串
        textToken: root.getPropertyValue("--text").trim(),
        visible: el.getBoundingClientRect().width > 4,
      };
    }, theme).catch((e) => ({ missing: String(e.message) }));
    data.shown = shown;
    if (!data.missing && shown) {
      const file = `probe-03-subtitle-${TAG}-${theme}.png`;
      const ok = await page.locator("#pin-fixed-sub").screenshot({ path: join(HERE, file), timeout: 15000 })
        .then(() => true).catch(() => false);
      data.shot = ok ? file : null;
    }
    rows.push(data);
    console.log(`[${theme}] ${JSON.stringify(data)}`);
  }
  writeFileSync(join(HERE, `probe-03-subtitle-${TAG}.json`),
    JSON.stringify({ tag: TAG, rows }, null, 2), "utf8");
  console.log(`\n已落盘 probe-03-subtitle-${TAG}.json`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
