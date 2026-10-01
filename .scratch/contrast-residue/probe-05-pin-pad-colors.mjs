// .scratch/contrast-residue/probe-05-pin-pad-colors.mjs —— 板图焊盘 / 图例色点的**改前改后**读数
// （工单 contrast-residue/03）。
//
// 要量的事：亮色块补上 `--pin-fixed-pad` 之后
//   ① 「固定/电源」焊盘的**计算填充色**从近黑 `#171b21` 变成与「空闲 IO」焊盘一套的浅灰；
//   ② 暗色主题**不变**（那一格的值不动）；
//   ③ 两个图例色点的填充（`--pin-pad` / `--pin-fixed-pad` 的色样）与板图一致（同一令牌）；
//   ④ 每主题一张板图 PNG（人眼记录）。
//
// 跑法（仓库根；**不要与 pytest 同时跑**）：
//     node .scratch/contrast-residue/probe-05-pin-pad-colors.mjs --tag before
//     node .scratch/contrast-residue/probe-05-pin-pad-colors.mjs --tag after
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

/** 采样：板图里 `io` / 非 `io` 两类焊盘各取第一个的解析后填充色 + 图例两个色点。
 *  `getComputedStyle().fill` 会把 `fill="var(--pin-pad)"` **解析成实际颜色**（这是关键的取证点：
 *  令牌解不出时它会退化成 `rgb(0, 0, 0)`——正是"亮色未覆盖"的可疑形态）。 */
const COLLECT = () => {
  const out = { pads: {}, dots: {}, tokens: {} };
  const root = getComputedStyle(document.documentElement);
  for (const t of ["--pin-pad", "--pin-fixed-pad"]) out.tokens[t] = root.getPropertyValue(t).trim();
  const svg = document.getElementById("pin-board-svg");
  if (svg) {
    const circles = [...svg.querySelectorAll("circle")];
    // ⚠ 按 `fill` **属性里写的令牌**认焊盘，别按"有没有 data-pin"猜：板上还有高亮环 / 色点之类
    // 的圆（第一次跑就抓到一个是 `fill: none` 的装饰圆，读数成了 `固定=none`）。
    const io = circles.find((c) => (c.getAttribute("fill") || "") === "var(--pin-pad)");
    const fixed = circles.find((c) => (c.getAttribute("fill") || "") === "var(--pin-fixed-pad)");
    for (const [name, el] of [["io", io], ["fixed", fixed]]) {
      if (!el) continue;
      const cs = getComputedStyle(el);
      out.pads[name] = { pin: el.dataset.pin || "", fill: cs.fill, stroke: cs.stroke,
        box: el.getBoundingClientRect().width };
    }
  }
  const legend = document.getElementById("pin-legend");
  if (legend) {
    out.dots.legend = [...legend.querySelectorAll(".dot")].map((d) => {
      const cs = getComputedStyle(d);
      return { bg: cs.backgroundColor, border: cs.borderTopColor,
        label: (d.parentElement.textContent || "").trim() };
    });
  }
  return out;
};

const server = await startServer();
const browser = await chromium.launch();
const rows = [];
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(600);
    await page.click('nav button[data-tab="generate"]', { timeout: 8000 }).catch(() => {});
    // MSPM0：`step_motor` 的角色默认全在 B 口（板图上既有 IO 焊盘也有固定/电源焊盘）
    await page.locator("#platforms .platform-card", { hasText: "MSPM0" }).first()
      .click({ timeout: 8000 }).catch(() => {});
    const ready = await page.waitForFunction(
      () => document.querySelectorAll("#module-grid .module-card:not(.off)").length > 0,
      undefined, { timeout: 25000 }).then(() => true).catch(() => false);
    if (!ready) { console.log(`[${theme}] **没造出来**：模块网格里没有可选的卡`); continue; }
    await page.fill("#module-search", "step_motor", { timeout: 8000 }).catch(() => {});
    await page.locator('#module-grid .module-card[data-add="step_motor"]').first()
      .click({ timeout: 8000 }).catch(() => {});
    const board = await page.waitForSelector("#pin-board-svg circle", { timeout: 25000 })
      .then(() => true).catch(() => false);
    if (!board) { console.log(`[${theme}] **没造出来**：20 s 内板图上没有焊盘圆点`); continue; }
    const data = await page.evaluate(COLLECT);
    data.theme = theme;
    const file = `probe-05-pads-${TAG}-${theme}.png`;
    data.shot = await page.locator("#pin-board-svg").screenshot({ path: join(HERE, file), timeout: 15000 })
      .then(() => true).catch(() => false) ? file : null;
    const legendShot = `probe-05-legend-${TAG}-${theme}.png`;
    data.legendShot = await page.locator("#pin-legend").screenshot({ path: join(HERE, legendShot), timeout: 15000 })
      .then(() => true).catch(() => false) ? legendShot : null;
    rows.push(data);
    console.log(`[${theme}] 令牌 ${JSON.stringify(data.tokens)}`);
    console.log(`        焊盘 io=${data.pads.io && data.pads.io.fill} 固定=${data.pads.fixed && data.pads.fixed.fill}`);
    console.log(`        图例 ${JSON.stringify((data.dots.legend || []).map((d) => [d.label, d.bg]))}`);
  }
  writeFileSync(join(HERE, `probe-05-pads-${TAG}.json`), JSON.stringify({ tag: TAG, rows }, null, 2), "utf8");
  console.log(`\n已落盘 probe-05-pads-${TAG}.json（${rows.length} 行）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
