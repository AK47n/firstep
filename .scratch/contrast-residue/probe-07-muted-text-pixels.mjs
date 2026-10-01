// .scratch/contrast-residue/probe-07-muted-text-pixels.mjs —— 三条「真文字被 opacity 压到 AA 以下」
// 的**真像素改前/改后**读数（工单 contrast-residue/04）。
//
// 目标（都在生成页的推荐区）：
//   ① `.chip.rec.unsel .reason`（点掉一个模块后那条 chip 里的推荐理由）
//   ② `.sugg-count`（库外建议 chip 的「⤵ N 方案」计数）
//   ③ `.res-soft`（资源总览里"非硬件资源"的降级行）——**要一份带 AI 洞察的任务计划**才有；
//      本探针会去找，找不到就如实记「没量到」（见 JSON 的 `missing`）。
//
// 假件只有一个：`/api/recommend` 回合成 SSE（真推荐要花 LLM 额度）——照
// `tests/browser/module-intro.spec.mjs` 的既有做法。其余全真：真后端、真 SSE 解析、真渲染。
//
// 跑法（仓库根；**不要与 pytest 同时跑**）：
//     node .scratch/contrast-residue/probe-07-muted-text-pixels.mjs --tag before
//     node .scratch/contrast-residue/probe-07-muted-text-pixels.mjs --tag after
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

const RECOMMEND = {
  topic_id: "",
  modules: [
    { slug: "ir_beam", reason: "可选点/起始做辅助" },
    { slug: "pid", reason: "巡线核心" },
  ],
  requirements: [
    { sentence: 1, requirement: "检测物体是否经过", modules: ["ir_beam"], suggestions: [] },
    { sentence: 2, requirement: "沿黑线行驶", modules: ["pid"], suggestions: [
      { name: "OLED 显示屏", examples: ["0.96 寸 SSD1306"], degraded: false, selected: false,
        solutions: [{ name: "A 方案", price: "12.5" }, { name: "B 方案", price: "18" }] },
    ] },
  ],
  exclusive_groups: [],
  score_points: [],
  instances: {},
};
const sseStream = () => [
  { event: "start", data: { stage: "分析题面", problem_chars: 24, clarify: false } },
  { event: "round", data: { round: 1, round_total: 4 } },
  { event: "done", data: RECOMMEND },
].map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join("");

/** 量一个元素：自己的 computed color / opacity + 往上找到的第一层不透明底。 */
const MEASURE = (sel) => {
  const el = document.querySelector(sel);
  if (!el) return { missing: `页面上没有 ${sel}` };
  const cs = getComputedStyle(el);
  let bg = "rgba(0, 0, 0, 0)", node = el;
  while (node && (bg === "rgba(0, 0, 0, 0)" || bg === "transparent")) {
    bg = getComputedStyle(node).backgroundColor;
    node = node.parentElement;
  }
  const r = el.getBoundingClientRect();
  return {
    color: cs.color, opacity: cs.opacity, fontSize: cs.fontSize, backdrop: bg,
    text: (el.textContent || "").trim().slice(0, 40),
    box: `${Math.round(r.width)}×${Math.round(r.height)}`,
  };
};

const server = await startServer();
const browser = await chromium.launch();
const rows = [];
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.route("**/api/recommend", (route) => route.fulfill({
    status: 200, headers: { "Content-Type": "text/event-stream" }, body: sseStream(),
  }));
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(600);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(300);
    // 每主题重跑一遍推荐（页面状态被上一主题改过：chip 可能已被点掉）
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.locator("#platforms .platform-card", { hasText: "STM32" }).first()
      .click({ timeout: 8000 }).catch(() => {});
    await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0,
      undefined, { timeout: 20000 }).catch(() => {});
    await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。").catch(() => {});
    await page.click("#btn-recommend", { timeout: 8000 }).catch(() => {});
    const chips = await page.waitForSelector('#rec-list .chip.rec[data-remove="ir_beam"]',
      { timeout: 20000 }).then(() => true).catch(() => false);
    const row = { theme, chips };
    if (chips) {
      // 点掉一个 chip ⇒ 出现 `.chip.rec.unsel .reason`（未选态的理由行）
      await page.click('#rec-list .chip.rec[data-remove="ir_beam"]', { timeout: 8000 }).catch(() => {});
      await page.waitForSelector('#rec-list .chip.rec.unsel[data-remove="ir_beam"]', { timeout: 8000 })
        .catch(() => {});
      row.unsel = await page.evaluate(MEASURE, '#rec-list .chip.rec.unsel[data-remove="ir_beam"] .reason');
      const f = `probe-07-unsel-reason-${TAG}-${theme}.png`;
      row.unselShot = await page.locator('#rec-list .chip.rec.unsel[data-remove="ir_beam"]')
        .screenshot({ path: join(HERE, f), timeout: 15000 }).then(() => true).catch(() => false) ? f : null;
    }
    row.sugg = await page.evaluate(MEASURE, ".sugg-count");
    if (!row.sugg.missing) {
      const f = `probe-07-sugg-count-${TAG}-${theme}.png`;
      row.suggShot = await page.locator(".sugg-count").first()
        .screenshot({ path: join(HERE, f), timeout: 15000 }).then(() => true).catch(() => false) ? f : null;
    }
    // `.res-soft` 要一份带 AI 洞察的任务计划——本流程到不了那里，如实记「没量到」
    row.soft = await page.evaluate(MEASURE, ".res-soft");
    rows.push(row);
    console.log(`[${theme}] unsel.reason ${JSON.stringify(row.unsel)}`);
    console.log(`[${theme}] sugg-count   ${JSON.stringify(row.sugg)}`);
    console.log(`[${theme}] res-soft     ${JSON.stringify(row.soft)}`);
  }
  writeFileSync(join(HERE, `probe-07-muted-text-${TAG}.json`), JSON.stringify({ tag: TAG, rows }, null, 2), "utf8");
  console.log(`\n已落盘 probe-07-muted-text-${TAG}.json`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
