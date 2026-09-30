// .scratch/light-contrast/_debug-sweep.mjs — 定位渲染面扫描里那几处"可疑"是什么。
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  await page.waitForTimeout(600);
  await page.click('nav button[data-tab="generate"]');
  await page.waitForTimeout(400);
  const out = await page.evaluate(() => {
    const pick = ["#btn-recommend", "#btn-expand", "#btn-topic-preread", ".step-no", ".ov-sep"];
    const rows = [];
    for (const sel of pick) {
      const el = document.querySelector(sel);
      if (!el) { rows.push({ sel, missing: true }); continue; }
      const cs = getComputedStyle(el);
      const parent = getComputedStyle(el.parentElement);
      rows.push({
        sel, tag: el.tagName, cls: el.className, text: (el.textContent || "").trim().slice(0, 18),
        color: cs.color, bg: cs.backgroundColor, bgImage: cs.backgroundImage.slice(0, 60),
        opacity: cs.opacity, parentOpacity: parent.opacity,
        parentBg: parent.backgroundColor, parentBgImage: parent.backgroundImage.slice(0, 60),
        disabled: el.disabled === true, aria: el.getAttribute("aria-disabled"),
        box: `${el.getBoundingClientRect().width}x${el.getBoundingClientRect().height}`,
      });
    }
    return rows;
  });
  for (const r of out) console.log(JSON.stringify(r, null, 1));
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
