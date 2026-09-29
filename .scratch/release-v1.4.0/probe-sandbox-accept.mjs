// 沙箱「模拟用户机」真机验收探针（发版 v1.4.0，工单 03）
//
// 为什么要它：门禁跑的是**夹具**（`tests/browser/` 各起真后端 + 内核分配端口 + 独立数据目录），
// 而这一单要的是"用户机上打开工具会看到什么"——所以对着**真沙箱**（工具根 `Desktop\firstep-sim`、
// 数据目录 `~\.contest_generator_sim`、端口 8020、入口 `sim-run.py`，见 `local-environment.md` 第 1 节）
// 用真 Chromium 走一遍，量的是**计算样式**，不是截图"看着行"。
//
// 看四件事：
//   ① `/api/health` 的版本 = 要发的那个版本（盘上的代码就是这一版）
//   ② 十二个页签逐页：正文基准 = 14px（`--fs-body`）、**有文字的元素**的字号取值集合 ⊆ 六档角色
//      （12/13/14/16/20/22）∪ em 派生值；每个页签的折叠区**全展开**后再量
//      ——口径坑记一笔：第一版把 `checkbox` / `radio` 也算进来，它们没有文字、computed
//      font-size 是浏览器默认的 13.3333px，白报 5 条；详见 `sandbox-input-detail*.txt`
//   ③ 设置页：`#update-current-version` = 本版；更新面板的体积文案是实测口径
//      （约 800 MB / 约 0.7 GB），不再是 6.2 GB / 5 GB+
//   ④ 版本更新记录页：首块就是本版，主题句是 VERSIONS.md 里写的那句
//   （另报一张读数：每页"整圈完整框"的可见元素数——**不作判据**，它是本轮申报例外的口径）
//
// 用法（沙箱已在 8020 起着）：
//   node .scratch/release-v1.4.0/probe-sandbox-accept.mjs [--base http://127.0.0.1:8020] [--json <out>]
//
// 零网络：只打本机 8020（真后端），不点任何会打 GitHub / LLM 的按钮。

import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import process from "node:process";

const EXPECT_VERSION = process.env.EXPECT_VERSION || "1.4.0";
const ROLES = [12, 13, 14, 16, 20, 22]; // --fs-tag / note / body / block / page / icon
const EM_FACTORS = [0.62, 0.75, 0.8, 0.85, 0.88, 0.9, 1, 1.15, 1.2, 1.25]; // 允许的 em 派生
const TABS = ["generate", "hwcheck", "topic", "code", "settings", "library",
              "reference", "pdf", "md", "master", "guide", "changelog"];

const argv = process.argv.slice(2);
const argOf = (name, dflt) => {
  const at = argv.indexOf(name);
  return at >= 0 && argv[at + 1] ? argv[at + 1] : dflt;
};
const BASE = argOf("--base", "http://127.0.0.1:8020");
const JSON_OUT = argOf("--json", "");

const explainable = (px) =>
  ROLES.some((r) => Math.abs(px - r) < 0.06) ||
  ROLES.some((r) => EM_FACTORS.some((f) => Math.abs(px - r * f) < 0.12));

const failures = [];
const check = (ok, msg) => {
  console.log(`${ok ? "✅" : "❌"} ${msg}`);
  if (!ok) failures.push(msg);
};

const health = await (await fetch(`${BASE}/api/health`)).json();
console.log(`\n== ① 版本 ==\n/api/health → ${JSON.stringify(health).slice(0, 160)}`);
check(health.version === EXPECT_VERSION, `/api/health 版本 = ${health.version}（要发的版本 ${EXPECT_VERSION}）`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.waitForSelector("button[data-tab]", { timeout: 15000 });

const report = {};
console.log(`\n== ② 十二个页签的字号档位（计算样式）==`);
for (const tab of TABS) {
  await page.click(`button[data-tab="${tab}"]`);
  await page.waitForTimeout(220);
  // 折叠区全展开：否则"默认收起的那些输入框 / 面板"永远在射程外（第一次跑就没展开）
  await page.evaluate((tabId) => {
    for (const d of document.getElementById(`tab-${tabId}`).querySelectorAll("details")) d.open = true;
  }, tab);
  await page.waitForTimeout(250);
  const got = await page.evaluate((tabId) => {
    const root = document.getElementById(`tab-${tabId}`);
    // 口径（第一次跑踩到的坑）：只看**有文字的元素**——`checkbox` / `radio` / `file` 是自绘控件
    // （没有文字、字号不影响渲染），它们的 computed font-size 是浏览器默认 13.3333px，不是"档位"问题。
    const textBearing = (el) => {
      const tag = el.tagName.toLowerCase();
      if (tag === "input") {
        const t = (el.getAttribute("type") || "text").toLowerCase();
        return !["checkbox", "radio", "file", "range", "hidden", "color"].includes(t);
      }
      if (tag === "select" || tag === "textarea" || tag === "button") return true;
      return Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim() !== "");
    };
    const out = { sizes: {}, rawSizes: {}, fullBoxes: 0, boxSamples: [], rootSize: getComputedStyle(root).fontSize };
    const bump = (bag, k, sample) => {
      bag[k] = bag[k] || { count: 0, sample: "" };
      bag[k].count += 1;
      if (!bag[k].sample) bag[k].sample = sample;
    };
    for (const el of root.querySelectorAll("*")) {
      if (el.closest("svg")) continue; // SVG 的 font-size 是用户单位（随图缩放），不在口径里
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) continue;
      const fs = parseFloat(cs.fontSize);
      const cls = (el.className || "").toString().trim().split(/\s+/).slice(0, 2).join(".");
      const sample = `${el.tagName.toLowerCase()}${cls ? "." + cls : ""}`;
      if (Number.isFinite(fs)) {
        bump(out.rawSizes, fs, sample);
        if (textBearing(el)) bump(out.sizes, fs, sample);
      }
      const widths = ["borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth"]
        .map((k) => parseFloat(cs[k]) || 0);
      const styles = ["borderTopStyle", "borderRightStyle", "borderBottomStyle", "borderLeftStyle"]
        .map((k) => cs[k]);
      if (widths.every((w) => w > 0) && styles.every((s) => s && s !== "none")) {
        out.fullBoxes += 1;
        if (out.boxSamples.length < 3) out.boxSamples.push(`${el.tagName.toLowerCase()}.${(el.className || "").toString().trim().split(/\s+/)[0] || ""}`);
      }
    }
    return out;
  }, tab);

  const bad = Object.entries(got.sizes).filter(([px]) => !explainable(parseFloat(px)));
  const setText = Object.entries(got.sizes)
    .map(([px, info]) => `${px}×${info.count}`)
    .join(" ");
  report[tab] = got;
  console.log(`  ${tab.padEnd(10)} 基准 ${got.rootSize.padEnd(6)} 文字取值 {${setText}} 整圈框 ${got.fullBoxes}`);
  check(parseFloat(got.rootSize) === 14, `[${tab}] 页签正文基准 = ${got.rootSize}（应为 14px = --fs-body）`);
  check(bad.length === 0,
    `[${tab}] 全部字号取值都在六档角色内${bad.length ? "——例外：" + bad.map(([px, i]) => `${px}（${i.sample}）`).join("、") : ""}`);
}

console.log(`\n== ③ 设置页：版本与体积文案 ==`);
await page.click('button[data-tab="settings"]');
await page.waitForFunction(() => {
  const el = document.getElementById("update-current-version");
  return el && el.textContent && el.textContent !== "…";
}, null, { timeout: 15000 });
const shown = (await page.textContent("#update-current-version")).trim();
check(shown === `v${EXPECT_VERSION}`, `设置页显示的版本 = ${shown}（应为 v${EXPECT_VERSION}）`);
const settingsText = (await page.textContent("#tab-settings")).replace(/\s+/g, "");
for (const [needle, want] of [["约800MB", true], ["约0.7GB", true], ["6.2GB", false], ["5GB+", false], ["约1GB", false]]) {
  check(settingsText.includes(needle) === want,
    `设置页文案${want ? "含" : "不含"}「${needle}」`);
}

console.log(`\n== ④ 版本更新记录页：首块就是本版 ==`);
await page.click('button[data-tab="changelog"]');
await page.waitForTimeout(400);
const changelogText = (await page.textContent("#tab-changelog")).replace(/\s+/g, "");
check(changelogText.includes(`v${EXPECT_VERSION}`), `版本记录页出现 v${EXPECT_VERSION}`);
check(changelogText.includes("十四个页面终于长成一套"), "版本记录页首块主题句 = VERSIONS.md 里写的那句");

await browser.close();

if (JSON_OUT) {
  writeFileSync(JSON_OUT, JSON.stringify({ base: BASE, health, report }, null, 2), "utf-8");
  console.log(`\n读数已落盘：${JSON_OUT}`);
}
console.log(`\n${failures.length === 0 ? "全部通过" : `不通过 ${failures.length} 条`}（共 ${
  1 + TABS.length * 2 + 6 + 2} 条判据）`);
process.exit(failures.length === 0 ? 0 : 1);
