// .scratch/ui-density-sitewide/probe-02b-shot-generated.mjs —— 生成页「**已生成**」态整页图。
//
// 为什么还要一支：票面要求本页的暗色整页图**含"已生成 / 未生成"两态**，而 `probe-02-shot.mjs`
// 只点页签、不触发生成（拍到的永远是"未生成"）。这一支照 `tests/browser/gen-chain-audit.mjs`
// 的既有跑法真发一次生成：**题面留空 = 零 LLM**（产品侧 report_draft 短路），main_c 必填，
// 输出目录走"手输"（不碰用户桌面，写进临时根）。
//
// 用的是同一套真后端夹具（`tests/browser/server.mjs`）：真库真母版、端口内核分配、跑完自收。
// ⚠ 纪律同 `probe-02-shot.mjs`：不要与全量 pytest 同时跑。
//
// 用法（在仓库根）：
//     node .scratch/ui-density-sitewide/probe-02b-shot-generated.mjs 03-after dark generate
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "shot";
const THEME = process.argv[3] || "dark";
const TAB = process.argv[4] || "generate";
const VIEWPORT = { width: Number(process.env.SHOT_WIDTH || 1600), height: 1000 };

mkdirSync(OUT, { recursive: true });
const work = mkdtempSync(join(tmpdir(), "ui-density-shot-"));
const outDir = join(work, "demo");

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  if (THEME === "light") {
    await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  }
  await page.click(`nav button[data-tab="${TAB}"]`);
  await page.waitForTimeout(1200);

  // 手输输出目录（桌面默认勾选时 #output-dir 是禁用的）
  if (await page.locator("#desktop-topic-output").isChecked().catch(() => false)) {
    await page.locator("#desktop-topic-output").uncheck();
  }
  await page.waitForFunction(() => !document.getElementById("output-dir").disabled,
    undefined, { timeout: 5000 }).catch(() => {});
  // 真点一张平台卡 + 加一个模块（生成的前置校验要求平台与模块都在）
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForTimeout(400);
  const card = page.locator('#module-grid .module-card[data-add="led"]');
  if (await card.count()) {
    await card.click();
    await page.waitForFunction(() => !document.getElementById("btn-expand").disabled,
      undefined, { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1200);
  } else {
    console.log("⚠ 夹具里没有 led 卡片——可能生成会被模块校验拦下");
  }
  await page.fill("#problem", "");                                // 题面留空 = 零 LLM
  await page.fill("#main-c", "int main(void) { return 0; }");     // main_c 必填
  await page.fill("#output-dir", outDir);

  await page.click("#btn-generate");
  await page.waitForFunction(() => !document.getElementById("btn-generate").disabled,
    undefined, { timeout: 180000 }).catch(() => {});
  await page.waitForTimeout(1500);
  console.log(`#generate-msg = 「${(await page.locator("#generate-msg").innerText().catch(() => "")).trim()}」`);
  const shown = await page.locator("#generate-result").isVisible().catch(() => false);
  console.log(`生成终态：结果区可见 = ${shown}；#gen-status = 「${
    (await page.locator("#gen-status").innerText().catch(() => "")).trim()}」`);

  // 展开第 9 步的结果细节，让"已生成"那几张卡在图上真的看得见
  await page.evaluate(() => {
    const r = document.getElementById("generate-result");
    if (r) r.scrollIntoView({ block: "start" });
  });
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-${TAB}-generated-result.png`) });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-${TAB}-generated-top.png`) });
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-${TAB}-generated-full.png`), fullPage: true });
  console.log("shot:", join(OUT, `${TAG}-${THEME}-${TAB}-generated-full.png`));
  // 整页图太高（>8192px）时看不了——再按选择器逐段拍几张（SHOT_AT=".a,.b"）
  const ats = (process.env.SHOT_AT || "").split(",").map((s) => s.trim()).filter(Boolean);
  for (const [i, sel] of ats.entries()) {
    const el = page.locator(sel).first();
    if (!(await el.count())) { console.log(`  ⚠ 找不到 ${sel}`); continue; }
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    const p = join(OUT, `${TAG}-${THEME}-${TAB}-seg${i + 1}.png`);
    await page.screenshot({ path: p });
    console.log("seg:", p, `(${sel})`);
  }
  await page.close();
} finally {
  await browser.close();
  await server.stop();
  rmSync(work, { recursive: true, force: true });
}
