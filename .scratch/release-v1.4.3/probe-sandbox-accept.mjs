// 沙箱「模拟用户机」真机验收探针（发版 v1.4.3，工单 03）
//
// 为什么要它：门禁跑的是**夹具**（`tests/browser/` 各起真后端 + 内核分配端口 + 独立数据目录），
// 而这一单要的是"用户机上打开工具会看到什么"——所以对着**真沙箱**（工具根 `Desktop\firstep-sim`、
// 数据目录 `~\.contest_generator_sim`、端口 8020、入口 `sim-run.py`，见 `local-environment.md` 第 1 节）
// 用真 Chromium 走一遍，量的是**计算样式与真样式表**，不是截图"看着行"。
//
// 照 `.scratch/release-v1.4.0/probe-sandbox-accept.mjs` 那份的口径（老四段原样保留），
// **加本轮的第五段**——这一版带给用户的两条可见变化必须在真机上读到：
//   ⑤-A 三条被 `opacity` 压到 AA 以下的文字：`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`
//        —— ① 真样式表里这三条规则**不再有 `opacity` 声明**；② 真 DOM 里挂上同款结构后，
//        计算色 = `--muted`、计算 `opacity` = 1（两主题各一遍）
//   ⑤-B 焊盘令牌：亮色 `--pin-fixed-pad` = `#afb8c1`（与空闲焊盘 `--pin-pad` = `#d0d7de`
//        同属浅色一档）、暗色两个值**逐字节不变**（`#171b21` / `#21262d`）
//
// ⚠ 口径说明（别把这张读数读成"真像素"）：⑤-A/⑤-B 量的是**计算样式与规则文本**。
// 真像素那两发（改前/改后）在 `.scratch/contrast-residue/probe-07-compare.txt` 与
// `probe-05-compare.txt`；本段是"装到用户机上的这份页面确实带着这些值"的确认。
// 三条文字里 `.res-soft` 只在"带 AI 洞察的任务计划"里渲染得出来，沙箱造不出那个状态 ⇒
// 用同款结构挂进真 DOM 量（理由与账见 `.scratch/release-v1.4.3/spec.md` 补充说明）。
//
// 用法（沙箱已在 8020 起着）：
//   node .scratch/release-v1.4.3/probe-sandbox-accept.mjs [--base http://127.0.0.1:8020] [--json <out>]
//
// 零网络：只打本机 8020（真后端），不点任何会打 GitHub / LLM 的按钮。

import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import process from "node:process";

const EXPECT_VERSION = process.env.EXPECT_VERSION || "1.4.3";
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
// v1.4.3 的主题句（VERSIONS.md 首块 `- 主题：…`），取破折号前那一句
check(changelogText.includes("三条被「变淡」压得看不清的话恢复成实色"),
  "版本记录页首块主题句 = VERSIONS.md 里写的那句");

console.log(`\n== ⑤ 本轮两条可见变化（真样式表 + 计算样式）==`);

// ⑤-A 三条文字的规则文本：真样式表里这三条选择器**不许再有 opacity 声明**
const RULES = [
  [".res-soft", ".res-soft"],
  [".sugg-count", ".sugg-count"],
  [".chip.rec.unsel .reason", ".chip.rec.unsel .reason"],
];
const ruleTexts = await page.evaluate((selectors) => {
  const flat = (rules, bag) => {
    for (const r of rules) {
      // ⚠ 先收自己再下钻：Chrome 里 CSSStyleRule 也有 `cssRules`（CSS 嵌套，多为空表），
      // 先判 `if (r.cssRules) continue` 会把所有普通规则漏掉（本探针第一版就这么写错过）。
      if (r.selectorText) bag.push([r.selectorText, r.style.cssText]);
      if (r.cssRules && r.cssRules.length) flat(r.cssRules, bag);
    }
    return bag;
  };
  const all = [];
  for (const sheet of document.styleSheets) {
    try { flat(sheet.cssRules, all); } catch { /* 跨域表跳过（本机没有） */ }
  }
  const out = {};
  for (const sel of selectors) out[sel] = all.filter(([s]) => s === sel).map(([, t]) => t);
  return out;
}, RULES.map(([sel]) => sel));

for (const [key] of RULES) {
  const texts = ruleTexts[key] || [];
  check(texts.length > 0, `[规则] ${key} 在真样式表里找得到（${texts.length} 条）`);
  const withOpacity = texts.filter((t) => /(^|;)\s*opacity\s*:/.test(t) || /opacity\s*:/.test(t));
  check(withOpacity.length === 0,
    `[规则] ${key} 不再有 opacity 声明${withOpacity.length ? "——仍有：" + withOpacity.join(" | ") : ""}`);
}

// ⑤-A 计算样式：同款结构挂进真 DOM（只挂一次），两主题各切一次、**等过渡落定**再读
//
// ⚠ 口径（第一版在这里红过一条，已自证是**量具**的问题、不是产品）:`.chip` 一族的 `color` 带
// `0.15s` 过渡，切完主题**立刻**读会读到过渡中间值——诊断读数 `probe-diag-sugg-count.txt`：
// `.sugg-count` 在亮色下 +0ms 读到暗色值 / +50ms `rgb(132,141,151)` / +200ms `rgb(95,104,114)` /
// **+600ms = 亮色 `--muted` `rgb(85,94,104)`**；同一时刻真样式表里给 `.chip.out` 上色的规则
// 只有一条 `color: var(--muted)`。`.sugg-count` 自己没有 `color` 声明（继承 `.chip.out`），
// 所以它比同批另外两条（各有自己的 `color` 规则、瞬时切换）更容易撞上这个窗口。
// ⇒ 量具改成"切主题后等 500ms 再读"（用户看到的就是落定后的样子）。
await page.evaluate(() => {
  const host = document.createElement("div");
  host.id = "probe-v143-texts";
  host.innerHTML = [
    '<span class="res-soft" id="p-res-soft">非硬件资源</span>',
    '<span class="chip out" id="p-sugg"><span class="sugg-count" id="p-sugg-count">⤵ 3 方案</span></span>',
    '<span class="chip rec unsel" id="p-unsel"><span class="reason" id="p-unsel-reason">推荐理由</span></span>',
  ].join("");
  document.body.appendChild(host);
});

const snapshotTheme = async (theme) => {
  await page.evaluate((t) => {
    if (t === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
  }, theme);
  await page.waitForTimeout(500); // ← 过渡落定（`--dur-base` 0.15s，留足余量）
  return page.evaluate(() => {
    const host = document.getElementById("probe-v143-texts");
    const tokenColor = (name) => {
      const el = document.createElement("span");
      el.style.color = `var(${name})`;
      el.textContent = "x";
      host.appendChild(el);
      const c = getComputedStyle(el).color;
      el.remove();
      return c;
    };
    const read = (id) => {
      const cs = getComputedStyle(document.getElementById(id));
      return { color: cs.color, opacity: cs.opacity };
    };
    const root = getComputedStyle(document.documentElement);
    return {
      muted: tokenColor("--muted"),
      resSoft: read("p-res-soft"),
      suggCount: read("p-sugg-count"),
      unselReason: read("p-unsel-reason"),
      pads: { pad: root.getPropertyValue("--pin-pad").trim(), fixed: root.getPropertyValue("--pin-fixed-pad").trim() },
    };
  });
};

const textProbe = { dark: await snapshotTheme("dark"), light: await snapshotTheme("light") };
await page.evaluate(() => document.documentElement.removeAttribute("data-theme"));

for (const theme of ["light", "dark"]) {
  const snap = textProbe[theme];
  for (const [name, got] of [["`.res-soft`", snap.resSoft], ["`.sugg-count`", snap.suggCount],
                             ["`.chip.rec.unsel .reason`", snap.unselReason]]) {
    check(got.color === snap.muted && got.opacity === "1",
      `[${theme}] ${name} 计算色 = --muted（${snap.muted}）且 opacity = 1——实得 color=${got.color} opacity=${got.opacity}`);
  }
}

// ⑤-B 焊盘令牌：亮色成套、暗色原样（同一份快照里读，别另起一次主题切换）
const pads = { dark: textProbe.dark.pads, light: textProbe.light.pads };
report.pads = pads;
const hex = (s) => s.toLowerCase();
console.log(`  焊盘令牌 亮色 { 空闲 ${pads.light.pad} / 固定 ${pads.light.fixed} }  暗色 { 空闲 ${pads.dark.pad} / 固定 ${pads.dark.fixed} }`);
check(hex(pads.light.fixed) === "#afb8c1", `[light] --pin-fixed-pad = ${pads.light.fixed}（应为 #afb8c1，本版新补的亮色覆盖）`);
check(hex(pads.light.pad) === "#d0d7de", `[light] --pin-pad = ${pads.light.pad}（空闲焊盘，应为 #d0d7de）`);
check(hex(pads.light.fixed) !== hex(pads.light.pad), "[light] 固定焊盘与空闲焊盘取值不同（保留「谁不能点」的层次）");
check(hex(pads.dark.fixed) === "#171b21", `[dark] --pin-fixed-pad = ${pads.dark.fixed}（暗色应逐字节不变 #171b21）`);
check(hex(pads.dark.pad) === "#21262d", `[dark] --pin-pad = ${pads.dark.pad}（暗色应逐字节不变 #21262d）`);

await browser.close();

if (JSON_OUT) {
  writeFileSync(JSON_OUT, JSON.stringify({ base: BASE, health, report, textProbe, pads }, null, 2), "utf-8");
  console.log(`\n读数已落盘：${JSON_OUT}`);
}
const total = 1 + TABS.length * 2 + 6 + 2 + 3 * 2 + 2 * 3 + 5; // ①1 ②24 ③6 ④2 ⑤规则6 ⑤计算6 ⑤焊盘5 = 50
console.log(`\n${failures.length === 0 ? "全部通过" : `不通过 ${failures.length} 条`}（共 ${total} 条判据）`);
process.exit(failures.length === 0 ? 0 : 1);
