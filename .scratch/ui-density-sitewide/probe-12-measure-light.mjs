// .scratch/ui-density-sitewide/probe-12-measure-light.mjs
// 工单 12（浅色人眼复核）的**量具**：把"看着可疑"的地方量成数，别靠猜。
//
// 量三件事（浅色 + 暗色各跑一遍，看是不是只在浅色下成立）：
//   ① 参考库表格：**简介 / 体量**两列的文本有没有溢出到"操作"列底下（scrollWidth > clientWidth，
//      以及"操作"列左边界 与 前一列右边界 的重叠像素）；
//   ② `.badge.ref-none`（未锚定，全站最多的那档灰）的**对比度**：WCAG 相对亮度比值
//      （正文要 ≥ 4.5:1，大字 / 非文本图形 ≥ 3:1）；
//   ③ "去框留淡底"的块与**页面底**的亮度差（`.guide-note` 的 panel-2 底 vs body 底），
//      用 ΔL（相对亮度的差）与对比度两个数表示——回答"浅色下分不分得开"。
//
//     node .scratch/ui-density-sitewide/probe-12-measure-light.mjs
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const VIEWPORT = { width: Number(process.env.SHOT_WIDTH || 1600), height: 1000 };

const MEASURE = () => {
  const lum = (rgb) => {
    const [r, g, b] = rgb.map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const parse = (c) => (c.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
  // 背景可能是 rgba(...) 透明 → 沿祖先链找第一个不透明的底色
  const bgOf = (el) => {
    let node = el;
    while (node) {
      const c = getComputedStyle(node).backgroundColor;
      const m = c.match(/rgba?\(([^)]+)\)/);
      if (m) {
        const parts = m[1].split(",").map((v) => parseFloat(v));
        if (parts.length < 4 || parts[3] > 0.9) return parts.slice(0, 3);
      }
      node = node.parentElement;
    }
    return [255, 255, 255];
  };
  const ratio = (a, b) => {
    const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };

  const out = { theme: document.documentElement.dataset.theme || "dark", tables: [], contrast: {}, panels: [] };

  // ① 表格溢出（参考库那 171 行；抽前 40 行看趋势）
  const rows = [...document.querySelectorAll("#ref-rows tr")].slice(0, 40);
  let overflow = 0, overlaps = 0;
  const samples = [];
  for (const tr of rows) {
    const tds = [...tr.children];
    if (tds.length < 6) continue;
    // ⚠ 列按**表头名字**定位，别按序号：参考库的表是 7 列（标题/类型/题型/锚定/简介/体量/操作），
    // 第一版按 6 列数，把"简介"当成了"体量"，量出来的数是错的（本单第一版就这么错了一次）。
    const heads = [...document.querySelectorAll("#tab-reference thead th")].map((th) => th.textContent.trim());
    const iDesc = heads.indexOf("简介"), iSize = heads.indexOf("体量"), iAct = heads.indexOf("操作");
    if (iAct < 0 || iDesc < 0 || iSize < 0) continue;
    const act = tds[iAct].getBoundingClientRect();
    const bad = [iDesc, iSize]
      .map((i) => ({ i, name: heads[i], over: tds[i].scrollWidth - tds[i].clientWidth,
                     text: tds[i].textContent.trim().slice(0, 20) }))
      .filter((x) => x.over > 1);
    if (bad.length) overflow++;
    const ov = Math.max(0, ...bad.map((x) => tds[x.i].getBoundingClientRect().right - act.left), 0);
    if (ov > 1) overlaps++;
    if (samples.length < 3 && (bad.length || ov > 1)) {
      samples.push({ heads: heads.join("/"), bad, overlapPx: Math.round(ov) });
    }
  }
  out.tables.push({ what: "#ref-rows", rows: rows.length, overflowRows: overflow, overlapRows: overlaps, samples });

  // ② 未锚定徽章的对比度
  const none = document.querySelector(".badge.ref-none");
  if (none) {
    const cs = getComputedStyle(none);
    const bg = bgOf(none);
    const fg = parse(cs.color);
    out.contrast.refNone = { color: cs.color, bg: `rgb(${bg.join(",")})`,
                             ratio: Math.round(ratio(fg, bg) * 100) / 100 };
  }
  // 顺带：套件（蓝）/ 赛题（accent）两档对照
  for (const [key, sel] of [["refKit", ".badge.ref-kit"], ["refTopic", ".badge.ref-topic"]]) {
    const el = document.querySelector(sel);
    if (el) {
      const bg = bgOf(el);
      out.contrast[key] = { color: getComputedStyle(el).color, bg: `rgb(${bg.join(",")})`,
                            ratio: Math.round(ratio(parse(getComputedStyle(el).color), bg) * 100) / 100 };
    }
  }

  // ③ "去框留淡底"的块 vs 页面底
  const bodyBg = bgOf(document.body);
  for (const [name, sel] of [["body", "body"], [".card", ".card"], [".guide-note", ".guide-note"],
                             [".card-details-body", ".card-details-body"]]) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const bg = bgOf(el);
    out.panels.push({ what: name, bg: `rgb(${bg.join(",")})`,
                      vsBody: Math.round(ratio(bg, bodyBg) * 100) / 100 });
  }
  return out;
};

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.click('nav button[data-tab="reference"]');
    // 等真行渲染出来再量（第一版没等，light 那次只看到 1 行 → 量出"0 行溢出"的假绿）
    await page.waitForFunction(() => document.querySelectorAll("#ref-rows tr").length > 20, { timeout: 30000 });
    await page.waitForTimeout(400);
    const data = await page.evaluate(MEASURE);
    console.log(`\n===== ${theme} =====`);
    for (const t of data.tables) {
      console.log(`表格 ${t.what}：${t.rows} 行里 **溢出 ${t.overflowRows} 行 / 重叠 ${t.overlapRows} 行**`);
      for (const s of t.samples) console.log("   样例：", JSON.stringify(s));
    }
    console.log("徽章对比度：", JSON.stringify(data.contrast));
    console.log("面板 vs 页面底：", data.panels.map((p) => `${p.what} ${p.bg} ×${p.vsBody}`).join("  |  "));
    // 指南页那张"提醒框"（去框留淡底 + accent 左条）的实拍也量一下
    await page.click('nav button[data-tab="guide"]');
    await page.waitForTimeout(400);
    const g = await page.evaluate(MEASURE);
    console.log("指南页面板：", g.panels.map((p) => `${p.what} ${p.bg} ×${p.vsBody}`).join("  |  "));
  }
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
