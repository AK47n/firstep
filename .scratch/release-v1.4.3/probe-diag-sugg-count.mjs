// 量具自证（发版 v1.4.3，工单 03 的诊断脚本，**不作判据**）：
// 探针第一版在 [light] `.sugg-count` 上报了一条红（计算色 = 暗色的 `--muted`）。
// 本脚本回答一个问题：那是**产品的问题**（有规则把 `.sugg-count` 钉在旧值），
// 还是**量具的口径问题**（切主题后没等稳定就读）？
//
// 做法：同款结构挂进真 DOM → 先切暗色读一遍作对照 → 切亮色，**立刻 / 50ms / 200ms / 600ms**
// 各读一次 → 打印元素与其祖先链上的 `transition-*` → 再把真样式表里所有会给 `.sugg-count`
// 或 `.chip.out` 上色的规则列出来。
//
// 跑法（沙箱在 8020 起着）：node .scratch\release-v1.4.3\probe-diag-sugg-count.mjs

import { chromium } from "playwright";

const BASE = process.argv.includes("--base")
  ? process.argv[process.argv.indexOf("--base") + 1]
  : "http://127.0.0.1:8020";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.waitForSelector("button[data-tab]", { timeout: 15000 });

await page.evaluate(() => {
  const host = document.createElement("div");
  host.id = "diag-host";
  host.innerHTML = '<span class="chip out" id="d-chip"><span class="sugg-count" id="d-count">⤵ 3 方案</span></span>';
  document.body.appendChild(host);
});

const readColor = () => page.evaluate(() => {
  const el = document.getElementById("d-count");
  const chip = document.getElementById("d-chip");
  const chain = [];
  for (let n = el; n && n !== document.documentElement.parentNode; n = n.parentElement) {
    const cs = getComputedStyle(n);
    chain.push({
      node: n.id || n.className || n.tagName.toLowerCase(),
      color: cs.color,
      transitionProperty: cs.transitionProperty,
      transitionDuration: cs.transitionDuration,
    });
  }
  return { color: getComputedStyle(el).color, chipColor: getComputedStyle(chip).color, chain };
});

await page.evaluate(() => document.documentElement.removeAttribute("data-theme"));
await page.waitForTimeout(300);
console.log("== 暗色（对照）==", (await readColor()).color);

await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));
for (const wait of [0, 50, 200, 600]) {
  if (wait) await page.waitForTimeout(wait);
  const got = await readColor();
  const muted = await page.evaluate(() => {
    const el = document.createElement("span");
    el.style.color = "var(--muted)";
    document.getElementById("diag-host").appendChild(el);
    const c = getComputedStyle(el).color;
    el.remove();
    return c;
  });
  console.log(`== 亮色 +${wait}ms == .sugg-count=${got.color}  .chip.out=${got.chipColor}  --muted=${muted}`);
  if (wait === 0) {
    console.log("   祖先链（看谁在过渡）：");
    for (const row of got.chain) {
      console.log(`     ${row.node.padEnd(28)} color=${row.color.padEnd(22)} transition=${row.transitionProperty} / ${row.transitionDuration}`);
    }
  }
}

const rules = await page.evaluate(() => {
  const flat = (rs, bag) => {
    for (const r of rs) {
      if (r.selectorText) bag.push([r.selectorText, r.style.cssText]);
      if (r.cssRules && r.cssRules.length) flat(r.cssRules, bag);
    }
    return bag;
  };
  const all = [];
  for (const s of document.styleSheets) { try { flat(s.cssRules, all); } catch { /* 跨域跳过 */ } }
  return all.filter(([sel]) => /sugg-count|\.chip\.out|\.sugg\b/.test(sel));
});
console.log("\n== 真样式表里会给 .sugg-count / .chip.out 上色的规则 ==");
for (const [sel, body] of rules) console.log(`  ${sel}  { ${body} }`);

await browser.close();
