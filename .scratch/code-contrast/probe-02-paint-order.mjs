// .scratch/code-contrast/probe-02-paint-order.mjs —— **高亮层压在字上还是垫在字下**（真 Chromium 像素）。
//
// 为什么这一支是本轮的前置：静态判据把高亮层当"文字压在合成底上"算（`contrast(over(fg,bg), bg)`），
// 但代码页的标记层（`.code-marks`，z-index 0）与选区（`.code-ta::selection`，z-index 1）
// **画在高亮层（`.code-hl`，静态流）之上**——半透明色压在字上时，**字形本身也被染色**，
// 真实比值比"垫在字下"的算法**更低**。这一支用真像素把这件事钉死。
//
// 它同时是"观感零变化"的取证工具（工单 01）：同一个样例在**改动前/后**各跑一遍
// （`--tag before` / `--tag after`，靠 `git stash` 切树），两份 PNG 与 JSON 并存，
// 由 probe-02-paint-order-read.py 逐像素对照。
//
// **取样口径（02 单评审整改，别退回去）**：
//   · 覆盖**十个令牌**：`.c` 出 com/str/pre/kw/num/fn/const，`.syscfg`（XML）出 tag/attr/val/com/pre；
//   · **选区那一发必须只叠一层**：把选区末端伸到**下一行**，让光标落在下一行——
//     否则 `.code-pre-line.active`（当前行 .07）会垫在同一格里，量到的是**叠加态**
//     （评审实测：那样量出来的底是 `over(选区, over(.07, 代码底))`，比单层严，且余量只剩 0.05）。
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

const C_SAMPLE = [
  "/* 块注释：tok-com —— 电赛工程生成器 */",
  "#include <stdint.h>",
  "#define LED_PIN 13",
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
  '  <pin name="PA24" role="A0_3"/>',
  "</config>",
].join("\n");

//: `[文件, [[样本名, 选择器], …]]`——每个选择器取**第一个**命中元素；取不到就跳过并报出来。
const TARGETS = [
  ["sample.c", [
    ["com", ".code-hl .tok-com"],
    ["pre", ".code-hl .tok-pre"],
    ["kw", ".code-hl .tok-kw"],
    ["num", ".code-hl .tok-num"],
    ["fn", ".code-hl .tok-fn"],
    ["const", ".code-hl .tok-const"],
    ["str", ".code-hl .tok-str"],
  ]],
  ["sample.syscfg", [
    ["tag", ".code-hl .tok-tag"],
    ["attr", ".code-hl .tok-attr"],
    ["val", ".code-hl .tok-val"],
    ["com", ".code-hl .tok-com"],
    ["pre", ".code-hl .tok-pre"],
  ]],
];

const dir = mkdtempSync(join(tmpdir(), "cc-paint-"));
writeFileSync(join(dir, "sample.c"), C_SAMPLE, "utf8");
writeFileSync(join(dir, "sample.syscfg"), XML_SAMPLE, "utf8");

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

  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(200);

    for (const [file, targets] of TARGETS) {
      const stem = file.replace(/\./g, "-");
      await page.click(`#code-tree .code-tree-btn[data-code-file="${file}"]`);
      await page.waitForSelector(".code-hl", { timeout: 15000 });
      await page.waitForTimeout(350);
      // **把"当前行"钉到文件末尾**（真鼠标点一下）：`.code-hl-line.active` 是**粘的**——
      // 程序化的 `setSelectionRange` 不会更新它（实测：取样行的底里混着上一轮交互留下的 .07）。
      {
        // 点在**最后一行**上（不是视图底——`.code-edit` 比视图矮时点在空白处不会移动光标）
        const last = await page.locator(".code-hl-line").last().boundingBox();
        if (last) {
          await page.mouse.click(last.x + 40, last.y + last.height / 2);
          await page.waitForTimeout(200);
        }
      }

      for (const [name, sel] of targets) {
        // 每一发都从"清干净"开始（失焦 + 清选区 + **补一次真事件**）：
        // `.code-marks` 的命中/词标记由 App 的处理器重算，程序化 `setSelectionRange` 不触发它
        // ——不补事件，上一发的标记会**留在原地**，下一发的底里就掺进别人的层（实测踩到）。
        await page.evaluate(() => {
          const ta = document.querySelector(".code-ta");
          if (ta) {
            ta.blur();
            ta.setSelectionRange(0, 0);
            ta.dispatchEvent(new Event("select", { bubbles: true }));
            ta.dispatchEvent(new Event("keyup", { bubbles: true }));
          }
          const s = window.getSelection();
          if (s) s.removeAllRanges();
        });
        await page.waitForTimeout(250);

        const loc = page.locator(sel).first();
        if ((await loc.count()) === 0) { console.log(`[${TAG}][${theme}/${stem}/${name}] 没命中，跳过`); continue; }
        const box = await loc.boundingBox();
        if (!box) { console.log(`[${TAG}][${theme}/${stem}/${name}] 无盒，跳过`); continue; }
        // **取样盒收窄到字行中线**（02 单评审整改）：行盒比字身高，整盒会把**上下相邻行**的底
        // 也框进来——那样"主色"可能来自另一层（实测：把下一行的 .07 当成了选区底）。
        const clip = { x: box.x, y: box.y + Math.round(box.height * 0.28),
          width: box.width, height: Math.max(6, Math.round(box.height * 0.44)) };

        const before = `probe-02-${TAG}-${theme}-${stem}-${name}-before.png`;
        await page.screenshot({ path: join(HERE, before), clip });

        // ② 只选中这个区间（textarea 的真选区 → ::selection）。
        //    **末端伸到下一行**：光标落在下一行 ⇒ 这一格的底只有选区一层（不吃当前行 .07）。
        const info = await page.evaluate((args) => {
          const [t] = args;
          const el = document.querySelector(t);
          const hl = document.querySelector(".code-hl");
          // ⚠ **不能用 `hl.textContent` 的偏移**：行元素是 `display:block`，块之间**没有换行字符**
          //   （实测 line 1 之后 `indexOf("\n")` 就是 -1）——那样算出来的偏移从第 2 行起全错位。
          //   正确算法：按 `.code-hl-line` 逐行累加（每行末尾补一个 \n）+ 行内 Range 偏移。
          const lines = [...hl.querySelectorAll(".code-hl-line")];
          const lineEl = el.closest(".code-hl-line");
          const lineIdx = lines.indexOf(lineEl);
          const before = lines.slice(0, Math.max(0, lineIdx))
            .reduce((n, l) => n + l.textContent.length + 1, 0);
          const r = document.createRange();
          r.setStart(lineEl, 0);
          r.setEndBefore(el);
          const start = before + r.toString().length;
          const len = el.textContent.length;
          const after = lines.slice(lineIdx + 1)
            .reduce((n, l) => n + l.textContent.length + 1, 0);
          // 选区**两头都往外伸**：起点伸到**上一行**、终点伸到**下一行**。
          // 为什么两头都要：`.code-hl-line.active`（当前行 .07）跟着光标的行——只伸终点时
          // 起点仍在目标行上，那一行的底就变成 `over(选区, over(.07, 代码底))`（实测：
          // 主色 #b6deec 而不是单层的 #c4e4f0）。两头都伸出去，目标行的底只剩选区一层。
          const prevStart = lineIdx > 0
            ? lines.slice(0, lineIdx - 1).reduce((n, l) => n + l.textContent.length + 1, 0)
            : before;
          const end = Math.min(start + len, before + lineEl.textContent.length + after);
          const selEnd = lineIdx + 1 < lines.length
            ? before + lineEl.textContent.length + 2 : end;
          const ta = document.querySelector(".code-ta");
          ta.focus();
          ta.setSelectionRange(prevStart, Math.min(selEnd, (ta.value || "").length));
          return { start, len, end, text: el.textContent, line: lineIdx + 1,
            span: [prevStart, selEnd], nextLine: lineIdx + 1 < lines.length,
            lineActive: !!(lineEl && lineEl.classList.contains("active")) };
        }, [sel]);
        await page.waitForTimeout(250);
        const selShot = `probe-02-${TAG}-${theme}-${stem}-${name}-selection.png`;
        await page.screenshot({ path: join(HERE, selShot), clip });

        // ③ 真双击（选中词 → 标记层 .code-mark-word 也上；这一发**本来就是叠加态**）
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
        const dblShot = `probe-02-${TAG}-${theme}-${stem}-${name}-dblclick.png`;
        await page.screenshot({ path: join(HERE, dblShot), clip });

        shots.push({ theme, file: stem, name, box, clip, info, marks,
          files: { before, selection: selShot, dblclick: dblShot } });
        console.log(`[${TAG}][${theme}/${stem}/${name}] 字形「${info.text}」`
          + `选区 [${info.start}, ${info.end})${info.nextLine ? "（末端伸到下一行）" : "（末行，无下一行）"}`
          + `${info.lineActive ? " ⚠ 该行同时是当前行（这一发掺了 .07）" : " ✅ 该行不是当前行"}；`
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
        const braceShot = `probe-02-${TAG}-${theme}-${stem}-brace.png`;
        const braceClip = { x: brace.x, y: brace.y + Math.round(brace.height * 0.28),
          width: brace.width, height: Math.max(6, Math.round(brace.height * 0.44)) };
        await page.screenshot({ path: join(HERE, braceShot), clip: braceClip });
        shots.push({ theme, file: stem, name: "brace", box: brace, clip: braceClip,
          info: { text: "{", color: brace.color },
          marks: { marksLayerSpans: brace.marks }, files: { before: braceShot } });
        console.log(`[${TAG}][${theme}/${stem}/brace] 括号字色 ${brace.color}；标记层 span 数 ${brace.marks}`);
      }
    }
  }

  writeFileSync(join(HERE, `probe-02-shots-${TAG}.json`),
    JSON.stringify({ tag: TAG, shots }, null, 2), "utf8");
  console.log(`已落盘 probe-02-shots-${TAG}.json（${shots.length} 格）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
  try { rmSync(dir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); }
  catch { console.log(`[after] 临时目录清理失败（句柄未释放，可手动删）：${dir}`); }
}
