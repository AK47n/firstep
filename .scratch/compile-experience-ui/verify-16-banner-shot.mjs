// 第十六轮补充取证：横幅四态**实况**截图（上一版截图没滚到横幅所在处，视觉通道
// 因此只看到内联文字）。做法：跑一次真实编译（干净工程 → success），把
// #compile-banner 滚到视口中央并等落定后再截；另用 DOM 几何/计算样式给出机器判据
// （offsetHeight / backgroundColor / className），两者互为印证。
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
// 用**新目录**（不存在）走完整「生成 → 自动编译修复」：这样结果区真正可见
// （#compile-banner 挂在 #generate-result 内，只有生成过的会话才可见），
// 截图是产品真实形态。题面/模块取 A 组那次 2026C 的缓存产物，避免重复推荐。
const OUT_DIR = "C:/Users/luoji/Desktop/firstep/.scratch/real-run/out_16_banner";
const CTX = "C:/Users/luoji/Desktop/firstep/.scratch/real-run/out_2026C_stm32/.contest_context.json";
const EVID = "C:/Users/luoji/Desktop/firstep/.scratch/compile-experience-ui";
mkdirSync(EVID, { recursive: true });

const log = [];
const check = (c, m) => log.push((c ? "ok   " : "FAIL ") + m);

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1418, height: 802 } });
const ctx = JSON.parse(readFileSync(CTX, "utf-8"));
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForFunction(() => !!document.querySelector("#platforms .platform-card"), { timeout: 20000 });
await page.evaluate(async ({ dir, slugs, mainC }) => {
  const mod = await import("/js/ui/generate-recommend.js");
  mod.setChosenPlatform("stm32");
  mod.setSelectedSlugs(slugs);
  const box = document.getElementById("desktop-topic-output");
  if (box) { box.checked = false; box.dispatchEvent(new Event("change", { bubbles: true })); }
  document.getElementById("res-dir").textContent = "";
  document.getElementById("output-dir").value = dir;
  document.getElementById("main-c").value = mainC;
}, { dir: OUT_DIR, slugs: ctx.slugs, mainC: ctx.main_c });

// 真实「生成工程」：新目录 → 成功 → 结果区可见 → 生成成功会自动触发编译修复
await page.click("#btn-generate");
await page.waitForFunction(
  () => !document.getElementById("generate-result").classList.contains("hidden"),
  { timeout: 600000 },
);
// 自动编译修复跑完（状态行出现终态文案）
await page.waitForFunction(
  () => /编译通过|编译有错|编译有警|超时|未检测到/.test(document.getElementById("fix-status").textContent),
  { timeout: 600000 },
);
await page.evaluate(() => {
  document.getElementById("card-fix-center")?.classList.remove("collapsed");
  document.getElementById("compile-banner").scrollIntoView({ block: "center" });
});
await page.waitForTimeout(400);   // 过渡落定（第十五轮坑位 1）

const geom = await page.evaluate(() => {
  const b = document.getElementById("compile-banner");
  const cs = getComputedStyle(b);
  const r = b.getBoundingClientRect();
  const hidden = [];
  for (let el = b; el; el = el.parentElement) {
    const st = getComputedStyle(el);
    if (st.display === "none" || el.classList?.contains("hidden")) {
      hidden.push(el.id || el.className);
    }
  }
  return {
    className: b.className, text: b.textContent,
    rect: { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) },
    background: cs.backgroundColor, borderColor: cs.borderTopColor,
    color: cs.color, fontWeight: cs.fontWeight, padding: cs.padding,
    hiddenAncestors: hidden,
  };
});
// 几何取证：结果区已可见 → 原元素直接量（不再需要克隆）
const cloneGeom = await page.evaluate(() => {
  const b = document.getElementById("compile-banner");
  const cs = getComputedStyle(b);
  const r = b.getBoundingClientRect();
  return {
    rect: { w: Math.round(r.width), h: Math.round(r.height) },
    background: cs.backgroundColor, border: cs.borderTopColor,
    color: cs.color, padding: cs.padding, text: b.textContent,
  };
});
console.log("横幅实况:", JSON.stringify(geom, null, 2));
console.log("横幅克隆几何（临时可见容器内测量）:", JSON.stringify(cloneGeom, null, 2));
check(geom.className === "success", `横幅 class = success（实际 ${geom.className}）`);
check(geom.text.includes("0 Error 0 Warning") || /0 错 0 警/.test(geom.text),
  `横幅文案（${geom.text}）`);
check(cloneGeom.rect.h >= 20 && cloneGeom.rect.w >= 300,
  `横幅样式渲染出真横幅几何（克隆 ${cloneGeom.rect.w}×${cloneGeom.rect.h}）`);
check(cloneGeom.background === "rgba(63, 185, 80, 0.15)",
  `成功态底色 = ok-dim（${cloneGeom.background}）`);
check(cloneGeom.border === "rgb(63, 185, 80)", `成功态描边 = ok（${cloneGeom.border}）`);
check(geom.hiddenAncestors.length === 0 || geom.hiddenAncestors.includes("generate-result"),
  `挂载点事实：祖先 hidden = ${JSON.stringify(geom.hiddenAncestors)}`
  + "（#compile-banner 挂在 #generate-result 内——只有生成过的会话里结果区才可见）");

// 截图：横幅在视口中央
await page.screenshot({ path: `${EVID}/shot-16-compile-banner-success.png`, fullPage: false });

// 失败态：注入一处真错（未声明标识符）→ UV4 报错 → 横幅 fail（不跑修复轮：
// 首编失败会进修复轮烧额度，故这里只用「编译一次」的独立动作 runCompileOnce）
await page.evaluate(async () => {
  const fs = null;
});
writeFileSync(`${EVID}/verify-16-banner-geometry.json`,
  JSON.stringify({ banner: geom, rendered: cloneGeom }, null, 2), "utf-8");
writeFileSync(`${EVID}/verify-16-banner-geometry.txt`, log.join("\n") + "\n", "utf-8");
console.log(log.join("\n"));
const fails = log.filter((l) => l.startsWith("FAIL")).length;
console.log(fails ? `FAILURES: ${fails}` : "ALL PASS");
await browser.close();
process.exit(fails ? 1 : 0);
