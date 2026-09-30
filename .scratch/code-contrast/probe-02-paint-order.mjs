// .scratch/code-contrast/probe-02-paint-order.mjs —— **高亮层压在字上还是垫在字下**（真 Chromium 像素）。
//
// 为什么这一支是本轮的前置：静态判据把高亮层当"文字压在合成底上"算（`contrast(over(fg,bg), bg)`），
// 但代码页的标记层（`.code-marks`，z-index 0）与选区（`.code-ta::selection`，z-index 1）
// **画在高亮层（`.code-hl`，静态流）之上**——半透明色压在字上时，**字形本身也被染色**，
// 真实比值比"垫在字下"的算法**更低**。这一支用真像素把这件事钉死：
// 同一个字形，选区前后各截一次，看像素往哪边跑。
//
// 它同时是"观感零变化"的取证工具（工单 01）：同一个样例在**改动前/后**各跑一遍
// （`--tag before` / `--tag after`，靠 `git stash` 切树），两份 PNG 与 JSON 并存，
// 由 probe-02-paint-order-read.py 逐像素对照。
//
// 跑法（仓库根；跑完接 probe-02-paint-order-read.py）：
//     node .scratch/code-contrast/probe-02-paint-order.mjs --tag before
//     node .scratch/code-contrast/probe-02-paint-order.mjs --tag after
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const TAG = (() => {
  const i = process.argv.indexOf("--tag");
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1].replace(/[^\w-]/g, "") : "cur";
})();

const SAMPLE = [
  "// 行一：注释（tok-com）",
  "int main(void) {",
  '    const char *s = "字符串（tok-str）";',
  "    return 0;",
  "}",
].join("\n");

const dir = mkdtempSync(join(tmpdir(), "cc-paint-"));
writeFileSync(join(dir, "sample.c"), SAMPLE, "utf8");

const server = await startServer();
const browser = await chromium.launch();
const shots = [];
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(600);
  await page.evaluate(async (d) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(d);
  }, dir);
  await page.waitForFunction(() => !document.getElementById("code-tree").innerText.includes("加载中"),
    undefined, { timeout: 20000 });
  await page.click('#code-tree .code-tree-btn[data-code-file="sample.c"]');
  await page.waitForSelector(".code-hl .tok-com", { timeout: 15000 });
  await page.waitForTimeout(300);

  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(200);
    // 清掉选区 + 失焦（保证"未选中"那一发是干净的基准）
    await page.evaluate(() => {
      const ta = document.querySelector(".code-ta");
      if (ta) { ta.blur(); ta.setSelectionRange(0, 0); }
      const s = window.getSelection();
      if (s) s.removeAllRanges();
    });
    await page.waitForTimeout(200);

    const targets = [
      ["com", ".code-hl .tok-com"],
      ["str", ".code-hl .tok-str"],
    ];
    for (const [name, sel] of targets) {
      const loc = page.locator(sel).first();
      if ((await loc.count()) === 0) continue;
      const box = await loc.boundingBox();
      if (!box) continue;

      // ① 基准：没选中
      const before = `probe-02-${TAG}-${theme}-${name}-before.png`;
      await page.screenshot({ path: join(HERE, before), clip: box });

      // ② 只选中这个区间（textarea 的真选区 → ::selection）
      const info = await page.evaluate((t) => {
        const el = document.querySelector(t);
        const hl = document.querySelector(".code-hl");
        const r = document.createRange();
        r.setStart(hl, 0);
        r.setEndBefore(el);
        const start = r.toString().length;
        const len = el.textContent.length;
        const ta = document.querySelector(".code-ta");
        ta.focus();
        ta.setSelectionRange(start, start + len);
        return { start, len, text: el.textContent };
      }, sel);
      await page.waitForTimeout(250);
      const selShot = `probe-02-${TAG}-${theme}-${name}-selection.png`;
      await page.screenshot({ path: join(HERE, selShot), clip: box });

      // ③ 真双击（选中词 → 标记层 .code-mark-word 也上）
      await page.evaluate(() => {
        const ta = document.querySelector(".code-ta");
        ta.setSelectionRange(0, 0); ta.blur();
      });
      await page.waitForTimeout(200);
      await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(350);
      const marks = await page.evaluate(() => ({
        word: document.querySelectorAll(".code-mark-word").length,
        hit: document.querySelectorAll(".code-mark-hit").length,
        current: document.querySelectorAll(".code-mark-current").length,
      }));
      const dblShot = `probe-02-${TAG}-${theme}-${name}-dblclick.png`;
      await page.screenshot({ path: join(HERE, dblShot), clip: box });

      shots.push({ theme, name, box, info, marks,
        files: { before, selection: selShot, dblclick: dblShot } });
      console.log(`[${TAG}][${theme}/${name}] 字形「${info.text}」起点 ${info.start} 长 ${info.len}；`
        + `双击后标记数 ${JSON.stringify(marks)}`);
    }

    // ④ 标记层单独验：括号彩虹（`.code-mark-bracket-depth-N`）**恒定渲染**（与选区无关），
    //    它压在括号字形上——括号在语法高亮里没有 token 类，字色 = `--code-text`。
    const brace = await page.evaluate(() => {
      const hl = document.querySelector(".code-hl");
      const walker = document.createTreeWalker(hl, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walker.nextNode())) {
        const i = n.textContent.indexOf("{");
        if (i < 0) continue;
        const r = document.createRange();
        r.setStart(n, i);
        r.setEnd(n, i + 1);
        const b = r.getBoundingClientRect();
        return { x: b.x, y: b.y, width: b.width, height: b.height,
          color: getComputedStyle(n.parentElement).color,
          marks: document.querySelectorAll('.code-marks span[class*="code-mark"]').length };
      }
      return null;
    });
    if (brace) {
      await page.evaluate(() => {
        const ta = document.querySelector(".code-ta");
        if (ta) { ta.blur(); ta.setSelectionRange(0, 0); }
      });
      await page.waitForTimeout(200);
      const braceShot = `probe-02-${TAG}-${theme}-brace.png`;
      await page.screenshot({ path: join(HERE, braceShot),
        clip: { x: brace.x, y: brace.y, width: brace.width, height: brace.height } });
      shots.push({ theme, name: "brace", box: brace, info: { text: "{", color: brace.color },
        marks: { marksLayerSpans: brace.marks }, files: { before: braceShot } });
      console.log(`[${TAG}][${theme}/brace] 括号字色 ${brace.color}；标记层 span 数 ${brace.marks}`);
    }
  }

  writeFileSync(join(HERE, `probe-02-shots-${TAG}.json`), JSON.stringify({ tag: TAG, shots }, null, 2), "utf8");
  console.log(`已落盘 probe-02-shots-${TAG}.json（每格一张 PNG）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
  try { rmSync(dir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); }
  catch { console.log(`[after] 临时目录清理失败（句柄未释放，可手动删）：${dir}`); }
}
