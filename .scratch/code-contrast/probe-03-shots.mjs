// .scratch/code-contrast/probe-03-shots.mjs —— **人眼复核用的整块截图**（代码页 × 两主题 × 三种状态）。
//
// 为什么单独一支：`probe-02` 采的是"字形核心那几个像素"（判据用），人眼要看的是**整块观感**——
// 语法色深浅、高亮强度、当前行/选区/查找命中叠在一起好不好看。机器只能证"过线"，证不了"好看"。
//
// 覆盖：`.c`（com/str/pre/kw/num/fn/const）+ `.syscfg`（XML：tag/attr/val）两种源，
// 每主题三态：原样 / 选中一段 / 查找命中（`#code-find-input` 注入查询）。
//
// 跑法（仓库根）：
//     node .scratch/code-contrast/probe-03-shots.mjs
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

const C_SAMPLE = [
  "/* 块注释：tok-com —— 电赛工程生成器 */",
  "#include <stdint.h>",
  "#define LED_PIN 13",
  "",
  "static const float kPid = 3.14159f;",
  "int main(void) {",
  '    char *msg = "hello 电赛";',
  "    uint32_t t = 1000;",
  "    return 0;",
  "}",
].join("\n");

const XML_SAMPLE = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  "<!-- SysConfig 片段：tok-com -->",
  '<config name="ADC12_0" mode="sequence">',
  '  <module name="adc" value="1"/>',
  "  <pin name=\"PA24\" role=\"A0_3\"/>",
  "</config>",
].join("\n");

const dir = mkdtempSync(join(tmpdir(), "cc-shots-"));
writeFileSync(join(dir, "sample.c"), C_SAMPLE, "utf8");
writeFileSync(join(dir, "sample.syscfg"), XML_SAMPLE, "utf8");

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(600);
  await page.evaluate(async (d) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(d);
  }, dir);
  await page.waitForFunction(() => !document.getElementById("code-tree").innerText.includes("加载中"),
    undefined, { timeout: 20000 });

  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(250);

    for (const file of ["sample.c", "sample.syscfg"]) {
      const stem = file.replace(/\./g, "-");
      await page.click(`#code-tree .code-tree-btn[data-code-file="${file}"]`);
      await page.waitForSelector(".code-hl", { timeout: 15000 });
      await page.waitForTimeout(400);
      const view = await page.locator(".code-view").first().boundingBox();
      const clip = { x: view.x, y: view.y, width: Math.min(view.width, 1100), height: Math.min(view.height, 420) };

      // ① 原样（含当前行 + 括号彩虹）
      await page.evaluate(() => { const ta = document.querySelector(".code-ta"); if (ta) ta.blur(); });
      await page.waitForTimeout(200);
      await page.screenshot({ path: join(HERE, `probe-03-${theme}-${stem}-plain.png`), clip });

      // ② 选中一段（::selection，压在字上）
      await page.evaluate(() => {
        const ta = document.querySelector(".code-ta");
        ta.focus();
        ta.setSelectionRange(0, 60);
      });
      await page.waitForTimeout(250);
      await page.screenshot({ path: join(HERE, `probe-03-${theme}-${stem}-selection.png`), clip });

      // ③ 查找命中（标记层：非当前命中 .18 + 当前命中 .24）
      await page.evaluate(() => {
        const ta = document.querySelector(".code-ta");
        ta.setSelectionRange(0, 0); ta.blur();
        const inp = document.getElementById("code-find-input");
        inp.value = "e";
        inp.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.waitForTimeout(400);
      await page.screenshot({ path: join(HERE, `probe-03-${theme}-${stem}-find.png`), clip });
      const marks = await page.evaluate(() => ({
        hit: document.querySelectorAll(".code-mark-hit").length,
        current: document.querySelectorAll(".code-mark-current").length,
        word: document.querySelectorAll(".code-mark-word").length,
        bracket: document.querySelectorAll('[class*="code-mark-bracket"]').length,
      }));
      console.log(`[${theme}/${file}] ${JSON.stringify(marks)}`);
    }
  }
  console.log("截图已落盘：probe-03-<主题>-<文件>-{plain,selection,find}.png");
  await page.close();
} finally {
  await browser.close();
  await server.stop();
  try { rmSync(dir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); }
  catch { console.log(`[after] 临时目录清理失败：${dir}`); }
}
