// 复现：文件树「点文件名打不开文件」——行内 hover 操作按钮容器把指针吃掉了。
//
// 三步自检（deep-audit 文件头口径）：
//   ① DIP（document.elementFromPoint）在文件名文字处命中的是哪个元素？
//   ② 该元素的 rect 与「行」的 rect 各是多少（横向覆盖率）？
//   ③ 反向验证：给它加 width:fit-content → hover/click 恢复（证明断点就在这条 CSS）。
import { chromium } from "playwright";
import { startServer } from "./server.mjs";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const TMP = mkdtempSync(join(tmpdir(), "firstep-tree-probe-"));
const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.route("**/api/recommend", (r) => r.fulfill({ status: 502, contentType: "application/json", body: '{"detail":"x"}' }));
try {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.locator('#module-grid .module-card[data-add="motor"]').click();
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 30000 });
  await page.uncheck("#desktop-topic-output").catch(() => {});
  const outDir = join(TMP, "proj");
  await page.fill("#problem", "");
  await page.fill("#output-dir", outDir);
  await page.fill("#main-c", "int main(void) { return 0; }");
  await page.waitForTimeout(200);
  await page.click("#btn-generate");
  await page.waitForFunction(() => !document.getElementById("btn-generate").disabled, undefined, { timeout: 120000 });
  console.log(`前置生成：${existsSync(join(outDir, "main.c")) ? "OK" : "失败"}`);

  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(dir);
  }, outDir);
  await page.waitForFunction((d) => document.getElementById("code-dir-label").textContent === d, outDir, { timeout: 15000 });
  await page.waitForFunction(() => !document.getElementById("code-tree").innerText.includes("加载中"), undefined, { timeout: 20000 });
  await page.waitForTimeout(400);

  const probe = async (label) => {
    const r = await page.evaluate(() => {
      const el = document.querySelector('#code-tree .code-tree-btn[data-code-file="main.c"]');
      if (!el) return { miss: true };
      const r = el.getBoundingClientRect();
      const x = r.left + r.width * 0.4, y = r.top + r.height / 2;
      const hit = document.elementFromPoint(x, y);
      const act = el.closest(".code-tree-file").querySelector(".code-tree-actions");
      const ar = act ? act.getBoundingClientRect() : null;
      const cs = act ? getComputedStyle(act) : null;
      return {
        rowW: Math.round(r.width),
        hitTag: hit ? hit.tagName + "." + String(hit.className || "").split(" ")[0] : "（无）",
        hitIsInsideBtn: !!(hit && el.contains(hit)),
        hitIsActions: !!(hit && act && act.contains(hit)),
        actRect: ar ? { x: Math.round(ar.x), w: Math.round(ar.width), h: Math.round(ar.height) } : null,
        coverPct: ar ? Math.round(Math.max(0, Math.min(ar.right, r.right) - ar.left) / r.width * 100) : 0,
        actDisplay: cs ? cs.display : null, actWidth: cs ? cs.width : null,
        actPointerEvents: cs ? cs.pointerEvents : null,
      };
    });
    console.log(`\n【${label}】`);
    console.log(`  行宽 ${r.rowW}px；文件名文字处 DIP 命中 = ${r.hitTag}（在按钮内=${r.hitIsInsideBtn}，在操作容器内=${r.hitIsActions}）`);
    console.log(`  操作容器 rect=${JSON.stringify(r.actRect)} display=${r.actDisplay} width=${r.actWidth} PE=${r.actPointerEvents}`);
    console.log(`  横向覆盖行宽 = ${r.coverPct}%`);
    return r;
  };

  // ① 真鼠标 hover 一次，让 .code-tree-actions 显形（display:none → inline-flex）
  const btn = page.locator('#code-tree .code-tree-btn[data-code-file="main.c"]');
  const hoverOk = await btn.hover({ timeout: 6000 }).then(() => true).catch(() => false);
  console.log(`\n① playwright hover(鼠标移到文件名按钮中央) 成功=${hoverOk}`);
  const before = await probe("hover 之后（操作按钮已显形）");

  // 真鼠标点击（不用 force）：能否打开文件？
  let clickOk = false, clickErr = "";
  try {
    await btn.click({ position: { x: before.rowW * 0.4, y: 8 }, timeout: 6000 });
    clickOk = true;
  } catch (e) { clickErr = (e.message || "").split("\n")[0]; }
  const editorOpen = await page.evaluate(() => !!document.querySelector("#code-viewer .code-edit .code-ta"));
  console.log(`② 真鼠标点文件名：click 成功=${clickOk}${clickErr ? "（" + clickErr + "）" : ""}；编辑器打开=${editorOpen}`);

  // ③ 反向验证：给操作容器加 width:fit-content → 再 hover 看 DIP 是否落到按钮上
  await page.addStyleTag({ content: ".code-tree-actions { width: fit-content; }" });
  await page.mouse.move(5, 5);
  await page.waitForTimeout(120);
  const hoverOk2 = await btn.hover({ timeout: 6000 }).then(() => true).catch(() => false);
  const after = await probe("③ 加 width:fit-content 之后");
  let clickOk2 = false;
  try { await btn.click({ position: { x: 60, y: 8 }, timeout: 6000 }); clickOk2 = true; } catch {}
  const editorOpen2 = await page.evaluate(() => !!document.querySelector("#code-viewer .code-edit .code-ta"));
  console.log(`\n③ hover 成功=${hoverOk2}；真鼠标点：click 成功=${clickOk2}；编辑器打开=${editorOpen2}`);
  console.log(`\n结论：修前 DIP 命中「${before.hitTag}」（点文件名无效）→ 修后命中「${after.hitTag}」（点文件名打开文件）`);
} finally {
  await browser.close();
  await server.stop();
  try { rmSync(TMP, { recursive: true, force: true }); } catch {}
}
