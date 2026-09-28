// .scratch/ui-density/probe-05-covered-detail.mjs —— 把"被盖住"的那一个控件挖开看（诊断用，一次性）。
//
// 只回答一件事：生成页上那个没有 id/class 的输入框，**到底是什么盖住了它**——
// 是布局重叠（真 bug）、还是探针的取样口径问题（假红）。
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.click('nav button[data-tab="generate"]');
  await page.waitForTimeout(500);

  const detail = await page.evaluate(() => {
    const out = [];
    const headerBottom = document.querySelector("header").getBoundingClientRect().bottom;
    for (const el of document.querySelectorAll("#tab-generate input, #tab-generate textarea, #tab-generate select")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      if (cy <= headerBottom + 2 || cy >= innerHeight - 2) continue;
      const top = document.elementFromPoint(cx, cy);
      if (top === el || el.contains(top) || (top && top.contains(el))) continue;
      const stack = document.elementsFromPoint(cx, cy).slice(0, 4).map((n) => ({
        tag: n.tagName.toLowerCase(),
        id: n.id || "",
        cls: typeof n.className === "string" ? n.className : "",
        rect: (() => { const b = n.getBoundingClientRect();
          return `${Math.round(b.left)},${Math.round(b.top)} ${Math.round(b.width)}x${Math.round(b.height)}`; })(),
      }));
      const owner = el.closest(".card, .gen-step, section");
      out.push({
        input: {
          tag: el.tagName.toLowerCase(), id: el.id, cls: el.className,
          type: el.type, ph: el.getAttribute("placeholder"),
          rect: `${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)}`,
          html: el.outerHTML.slice(0, 160),
          parentChain: (() => { const c = []; let n = el.parentElement; let i = 0;
            while (n && i < 4) { c.push(`${n.tagName.toLowerCase()}.${typeof n.className === "string" ? n.className : ""}`); n = n.parentElement; i++; }
            return c.join(" < "); })(),
        },
        ownerCard: owner ? { tag: owner.tagName.toLowerCase(), cls: owner.className,
          html: owner.outerHTML.slice(0, 120) } : null,
        stack,
      });
    }
    return out;
  });
  console.log(JSON.stringify(detail, null, 2));
} finally {
  await browser.close();
  await server.stop();
}
