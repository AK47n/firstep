// .scratch/ui-density/probe-06-design-audit.mjs —— 自查（工单 01/02/04 之后）：
// 用数值回答四个问题，不靠"看着还行"：
//
//   ① **窄屏**：1600 / 1366 / 1280 / 1024 四个宽度下，检测页有没有横向溢出？
//      标题换行后段落还读得下去吗？（令牌级放大最容易在这里翻车）
//   ② **空态降级真的生效了吗**：六张"空着的结果卡"的标题颜色，是否真的比有内容的卡弱一档？
//      （`:has()` 命中与否，肉眼看不出来，得读计算样式）
//   ③ **键盘焦点**：新增的两个入口锚用 **Tab** 走到时，有没有可见的焦点指示？
//      （`<a>` 不在 `button:focus-visible` 那条全局规则里——这正是新元素常漏的一格）
//   ④ **残余的"完整描边"**：检测页卡片内部还有多少元素是四边都描边的？
//      （02 的目标是"一屏一层"，得数出来，不能凭印象）
//
// 用法：node .scratch/ui-density/probe-06-design-audit.mjs
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const lines = [];
const say = (s) => { lines.push(s); console.log(s); };
const VIEWPORTS = [
  { w: 1600, h: 1000 }, { w: 1366, h: 900 }, { w: 1280, h: 800 }, { w: 1024, h: 768 },
];

const server = await startServer();
const browser = await chromium.launch();
try {
  // ---------- ① 窄屏：横向溢出 + 标题块几何 ----------
  say("== ① 窄屏（检测页）==");
  for (const vp of VIEWPORTS) {
    const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });
    await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
    await page.click('nav button[data-tab="hwcheck"]');
    await page.waitForSelector("#hwcheck-device-grid .module-card");
    const info = await page.evaluate(() => {
      const over = [];
      for (const el of document.querySelectorAll("#tab-hwcheck *")) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && (r.right > document.documentElement.clientWidth + 1
          || r.left < -1)) {
          over.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}`
            + `${typeof el.className === "string" && el.className ? "." + el.className.split(" ")[0] : ""}`
            + ` [${Math.round(r.left)},${Math.round(r.right)}]`);
        }
      }
      const h2 = document.querySelector("#tab-hwcheck .card h2");
      const jumps = [...document.querySelectorAll(".hwcheck-jump-row .hwcheck-jump")]
        .map((a) => { const r = a.getBoundingClientRect();
          return { w: Math.round(r.width), y: Math.round(r.top) }; });
      return {
        docScroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
        h2Size: getComputedStyle(h2).fontSize,
        h2Height: Math.round(h2.getBoundingClientRect().height),
        jumpWrap: jumps.length === 2 ? Math.abs(jumps[0].y - jumps[1].y) > 4 : null,
        overflowing: over.slice(0, 6),
        gridMax: getComputedStyle(document.querySelector("#hwcheck-device-grid")).maxHeight,
      };
    });
    say(`  ${vp.w}×${vp.h}：文档宽 ${info.docScroll} / 视口 ${info.client}`
      + `${info.docScroll > info.client + 1 ? " ⚠ 横向溢出" : " ✓ 无横向滚动"}`
      + ` ｜ 卡片标题 ${info.h2Size}（高 ${info.h2Height}px）`
      + ` ｜ 入口锚换行：${info.jumpWrap === null ? "?" : info.jumpWrap ? "是" : "否"}`
      + ` ｜ 器件网格 max-height ${info.gridMax}`);
    if (info.overflowing.length) say(`     溢出元素：${info.overflowing.join(" ｜ ")}`);
    await page.close();
  }

  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.click('nav button[data-tab="hwcheck"]');
  await page.waitForSelector("#hwcheck-device-grid .module-card");
  await page.waitForTimeout(600);

  // ---------- ② 空态降级是否生效（读计算样式）----------
  say("");
  say("== ② 空卡降级（`:has()` 命中与否）==");
  const empties = await page.evaluate(() => {
    const ids = ["hwcheck-wiring", "hwcheck-conflicts", "hwcheck-order", "hwcheck-sections",
      "hwcheck-console", "hwcheck-project", "hwcheck-checklist", "hwcheck-recent"];
    const out = [];
    for (const id of ids) {
      const box = document.getElementById(id);
      const card = box && box.closest(".card");
      if (!card) continue;
      const h2 = card.querySelector("h2");
      const shell = getComputedStyle(card);
      out.push({
        id,
        childCount: box.children.length,
        onlyChild: box.children.length === 1
          ? (box.children[0].className || box.children[0].tagName.toLowerCase()) : null,
        titleColor: getComputedStyle(h2).color,
        shadow: shell.boxShadow === "none" ? "无" : "有",
        bar: getComputedStyle(h2, "::before").backgroundColor,
      });
    }
    const filled = document.querySelector("#tab-hwcheck .card h2");
    return { out, filledColor: getComputedStyle(filled).color,
      filledBar: getComputedStyle(filled, "::before").backgroundColor };
  });
  say(`  有内容的卡（第 1 张）：标题 ${empties.filledColor} ｜ 记号码 ${empties.filledBar}`);
  for (const e of empties.out) {
    const quiet = e.titleColor !== empties.filledColor;
    say(`  #${e.id.padEnd(18)} 孩子 ${e.childCount} 个（${e.onlyChild || "-"}）`
      + ` ｜ 标题 ${e.titleColor} ${quiet ? "✓ 已降级" : "✗ 没降级"} ｜ 阴影 ${e.shadow} ｜ 记号码 ${e.bar}`);
  }

  // ---------- ③ 键盘焦点：Tab 走到入口锚 ----------
  say("");
  say("== ③ 入口锚的键盘焦点 ==");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.click("body", { position: { x: 5, y: 300 } });
  let hit = null;
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    hit = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || !el.classList || !el.classList.contains("hwcheck-jump")) return null;
      const st = getComputedStyle(el);
      return { text: el.textContent.trim(), outline: `${st.outlineStyle} ${st.outlineWidth} ${st.outlineColor}`,
        boxShadow: st.boxShadow, matchesFocusVisible: el.matches(":focus-visible") };
    });
    if (hit) break;
  }
  if (!hit) say("  ✗ Tab 走了 40 次都没走到入口锚（键盘不可达？）");
  else say(`  「${hit.text}」焦点可见：${hit.matchesFocusVisible ? "是" : "否（!）"}`
    + ` ｜ outline=${hit.outline} ｜ box-shadow=${hit.boxShadow}`);

  // ---------- ④ 残余的"四边都描边" ----------
  say("");
  say("== ④ 卡片内部残余的完整描边（四边都有 1px+ 实线）==");
  const borders = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("#tab-hwcheck *")) {
      const st = getComputedStyle(el);
      const sides = ["Top", "Right", "Bottom", "Left"].map((s) => st[`border${s}Width`]);
      const styles = ["Top", "Right", "Bottom", "Left"].map((s) => st[`border${s}Style`]);
      const solid = styles.every((s) => s === "solid" || s === "dashed");
      const thick = sides.every((w) => parseFloat(w) >= 1);
      if (!solid || !thick) continue;
      if (el.closest("button") || el.tagName === "BUTTON" || el.tagName === "INPUT"
        || el.tagName === "SELECT" || el.tagName === "TEXTAREA") continue; // 控件不算
      if (el.closest("header") || el.classList.contains("card")) continue; // 卡片那一层 + 顶栏
      const r = el.getBoundingClientRect();
      if (r.width < 40 || r.height < 20) continue;
      out.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}`
        + `${typeof el.className === "string" && el.className ? "." + el.className.split(" ")[0] : ""}`);
    }
    return out;
  });
  say(borders.length ? "  " + borders.join(" ｜ ") : "  （无）");

  // ---------- ⑤ 竖向节奏：分组带 / 卡片之间到底差多少 ----------
  say("");
  say("== ⑤ 竖向节奏（相邻块的实际间隙）==");
  const rhythm = await page.evaluate(() => {
    const kids = [...document.querySelectorAll("#tab-hwcheck > *")];
    const out = [];
    for (let i = 1; i < kids.length; i++) {
      const prev = kids[i - 1].getBoundingClientRect();
      const cur = kids[i].getBoundingClientRect();
      const gap = Math.round(cur.top - prev.bottom);
      const name = (el) => el.classList.contains("hwcheck-band") ? "分组带"
        : el.classList.contains("card") ? "卡片" : el.tagName.toLowerCase();
      out.push(`${name(kids[i - 1])} → ${name(kids[i])}：${gap}px`);
    }
    return out;
  });
  say("  " + rhythm.join(" ｜ "));

  // ---------- ⑥ 卡片标题的记号在换行时对齐到哪一行 ----------
  say("");
  say("== ⑥ `h2::before` 记号码的对齐（窄屏标题换行时）==");
  for (const w of [1600, 1024]) {
    const p = await browser.newPage({ viewport: { width: w, height: 900 } });
    await p.goto(server.url + "/", { waitUntil: "domcontentloaded" });
    await p.click('nav button[data-tab="hwcheck"]');
    await p.waitForSelector("#tab-hwcheck .card h2");
    const geo = await p.evaluate(() => {
      const h2 = document.querySelector("#tab-hwcheck .card h2");
      const bar = getComputedStyle(h2, "::before");
      const r = h2.getBoundingClientRect();
      // 伪元素没法直接量 box，只能读它的对齐声明 + 宿主高度
      return { h: Math.round(r.height), align: bar.alignSelf, transform: bar.transform,
        lineHeight: getComputedStyle(h2).lineHeight, fontSize: getComputedStyle(h2).fontSize };
    });
    say(`  ${w}px：h2 高 ${geo.h}px / 行高 ${geo.lineHeight} / 字号 ${geo.fontSize}`
      + ` ｜ 记号码 align-self=${geo.align}`);
    await p.close();
  }
} finally {
  await browser.close();
  await server.stop();
}

writeFileSync(join(HERE, "probe-06-design-audit.txt"), lines.join("\n") + "\n", "utf8");
