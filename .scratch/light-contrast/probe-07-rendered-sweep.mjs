// .scratch/light-contrast/probe-07-rendered-sweep.mjs — **渲染面全站对比度扫描**（05 单的量具）。
//
// 为什么要有它：腿⑧腿⑨ 是**静态**判据（读 `<style>` 块与 JS 里的声明），它们看不见
// ① 继承来的底色、② 渐变、③ JS 运行期改过的样式。这一支在**真 Chromium** 里量**真元素**，
// 把两面的读数对上：
//   · 底 = **从根往下把所有祖先背景按 alpha 合成**后的颜色（不是"第一个不透明的祖先"——
//     那是上一轮三个乐观数（6.11 / 5.19 / 3.39）的口径错处）；
//   · 文字 = 有直接文本子节点的元素（文本型 input/select/textarea/button 也算）；
//     自绘控件（checkbox/radio）**没有文字**，不算——那是 v1.4.0 验收踩过的假红口径；
//   · 阈值 = 小字 4.5 / 大字（≥24px 或 ≥18.66px+bold）3.0，与静态面同一套；
//   · 每个页签先**展开所有 `<details>`**（折叠区里的字也是字）。
//
// 跑法（仓库根）：
//     node .scratch/light-contrast/probe-07-rendered-sweep.mjs
// ⚠ 不要与全量 pytest 同时跑（本机负载下浏览器用例会抖）。
import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

// 阈值与大字判据**从守卫源码解析**（单源：不另抄一份口径——本仓纪律"注释里的数按脚本复算"）。
const GUARD = readFileSync(new URL("../../tests/js/css-tokens.test.mjs", import.meta.url), "utf8");
const grab = (re, what) => {
  const m = GUARD.match(re);
  if (!m) throw new Error("守卫里解析不到 " + what + "——口径变了就改这里");
  return m;
};
const TH = grab(/const CONTRAST_THRESHOLDS = \{([^}]*)\};/, "CONTRAST_THRESHOLDS");
const SMALL = Number(/small:\s*([0-9.]+)/.exec(TH[1])[1]);
const LARGE = Number(/large:\s*([0-9.]+)/.exec(TH[1])[1]);
const LT = grab(/const LARGE_TEXT = \{([^}]*)\};/, "LARGE_TEXT");
const LARGE_PX = Number(/px:\s*([0-9.]+)/.exec(LT[1])[1]);
const BOLD_PX = Number(/bold_px:\s*([0-9.]+)/.exec(LT[1])[1]);

const TABS = ["generate", "hwcheck", "settings", "guide", "changelog", "code",
  "master", "library", "reference", "pdf", "md", "topic"];

const SWEEP = (payload) => {   // 参数化：page.evaluate 只吃**一个**入参（且看不到模块作用域）
  const { tabs: TABS, th: THRESH } = payload;
  const lin = (v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
  const parse = (c) => (c.match(/[\d.]+/g) || [0, 0, 0, 1]).map(Number);
  /** 从根往下把所有祖先背景按 alpha 合成（含元素自己）——**不是**"第一个不透明的祖先"。 */
  const effBg = (el) => {
    const chain = [];
    for (let n = el; n; n = n.parentElement) chain.unshift(n);
    let acc = [255, 255, 255];
    for (const n of chain) {
      const [r, g, b, a = 1] = parse(getComputedStyle(n).backgroundColor);
      if (a > 0) acc = [0, 1, 2].map((i) => Math.round(a * [r, g, b][i] + (1 - a) * acc[i]));
    }
    return acc;
  };
  const hasText = (el) => {
    const tag = el.tagName.toLowerCase();
    if (["input", "select", "textarea", "button"].includes(tag)) {
      if (tag === "input" && ["checkbox", "radio", "range", "file", "color"].includes(el.type)) return false;
      return true;
    }
    return [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && bits.length < 3; n = n.parentElement) {
      bits.unshift(n.id ? `#${n.id}` : (n.className && typeof n.className === "string"
        ? "." + n.className.trim().split(/\s+/).slice(0, 2).join(".") : n.tagName.toLowerCase()));
    }
    return bits.join(" > ");
  };
  const out = { theme: document.documentElement.dataset.theme || "dark", tabs: [], bad: [] };
  for (const tab of TABS) {
    const btn = document.querySelector(`nav button[data-tab="${tab}"]`);
    if (!btn) { out.tabs.push({ tab, missing: true }); continue; }
    btn.click();
    for (const d of document.querySelectorAll("details:not([open])")) d.open = true;
    const panel = document.getElementById(`tab-${tab}`);
    if (!panel) { out.tabs.push({ tab, panel: false }); continue; }
    let total = 0, grad = 0;
    const bad = [];
    for (const el of panel.querySelectorAll("*")) {
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.15) continue;
      const box = el.getBoundingClientRect();
      if (box.width < 1 || box.height < 1) continue;          // 零尺寸（不可见）
      if (el.disabled === true) continue;                     // 禁用控件：WCAG 明文豁免
      // **渐变底**（background-image 不是 none）：ackgroundColor 是 transparent，
      // 静态面会把它算到祖先底上（假红）。渐变有专项判据（CONTRAST_GRADIENT_ENDS），
      // 这里只**记账不判**——数量一并报出来。
      if (cs.backgroundImage !== "none") { grad++; continue; }
      if (!hasText(el)) continue;
      total++;
      const fg = parse(cs.color);
      if (fg[3] === 0) continue;                       // 全透明字（高亮层那类）不算
      const bg = effBg(el);
      const fgEff = fg[3] < 1 ? [0, 1, 2].map((i) => Math.round(fg[3] * fg[i] + (1 - fg[3]) * bg[i])) : fg.slice(0, 3);
      const px = parseFloat(cs.fontSize);
      const bold = Number(cs.fontWeight) >= 700;
      const need = (px >= THRESH.largePx || (px >= THRESH.boldPx && bold)) ? THRESH.large : THRESH.small;
      const r = ratio(fgEff, bg);
      if (r < need - 1e-9) {
        bad.push({ sel: path(el), ratio: Math.round(r * 100) / 100, need, px,
          color: cs.color, bg: `rgb(${bg.join(",")})`, text: (el.textContent || "").trim().slice(0, 24) });
      }
    }
    out.tabs.push({ tab, total, bad: bad.length, grad });
    out.bad.push(...bad.map((b) => ({ tab, ...b })));
  }
  return out;
};

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  console.log("口径（从守卫源码解析）：小字 ≥ " + SMALL + " / 大字（≥" + LARGE_PX + "px 或 ≥"
    + BOLD_PX + "px+bold）≥ " + LARGE);
  let grand = 0;
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(600);
    const data = await page.evaluate(SWEEP, { tabs: TABS,
    th: { small: SMALL, large: LARGE, largePx: LARGE_PX, boldPx: BOLD_PX } });
    console.log(`\n===== ${theme} =====`);
    for (const t of data.tabs) {
      if (t.missing || t.panel === false) { console.log(`  ${t.tab.padEnd(11)}（没找到页签按钮 / 面板）`); continue; }
      console.log(`  ${t.tab.padEnd(11)}有文字元素 ${String(t.total).padStart(4)}　不达标 ${t.bad}`);
    }
    console.log(`  —— ${theme} 合计不达标 **${data.bad.length}**`);
    for (const b of data.bad.slice(0, 40)) {
      console.log(`     ${b.ratio.toFixed(2)}/${b.need}  [${b.tab}] ${b.sel}`);
      console.log(`         ${b.color} on ${b.bg}  ${b.px}px  「${b.text}」`);
    }
    grand += data.bad.length;
  }
  console.log(`\n两主题合计不达标：**${grand}**`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
