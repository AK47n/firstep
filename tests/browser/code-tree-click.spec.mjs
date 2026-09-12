// 真机验收：代码栏文件树「点文件名 → 打开文件」必须真的打得开（工单 gen-chain-audit/02）。
//
// 为什么要有这一层：`tests/js/code-tree-actions-width.test.mjs` 只是 CSS 结构守卫
// ——它能证明「操作区不再浮在文件名按钮上」，证明不了**点下去真的打开文件**。
// 真机 bug 的形态正是「点了没反应」：`.code-tree-actions`（行右 ✎/🗑）原先是绝对
// 定位浮层（right:0 + z-index:2），hover 显形后吃掉指针——实测文件按钮 225px 宽、
// 操作容器 131px 且横向覆盖 58%，按钮正中央（playwright hover 的落点）命中的是
// `✎ 重命名`：playwright 连 hover 都做不了（`✎ rename intercepts pointer events`），
// 用户点文件名没有任何反应。修法 = 文件行改 flex 兄弟布局（两区几何上不重叠）。
//
// 运行：node --test tests/browser/code-tree-click.spec.mjs
// 依赖：python 后端可起 + playwright chromium（生成真工程；零 LLM：题面留空 + 手输目录）
import test from "node:test";
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let server = null;
let browser = null;
let TMP = null;

test.before(async () => {
  server = await startServer();
  browser = await chromium.launch();
  TMP = mkdtempSync(join(tmpdir(), "firstep-tree-click-"));
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();
  // Windows：刚关掉的浏览器/服务进程还握着句柄，立即删会 EBUSY/EPERM 静默失败
  // ——实测不重试就会在 %TEMP% 攒一圈 firstep-tree-click-*。maxRetries 是
  // node:fs 内建退避（每次 100ms），比手写 setTimeout 循环可靠。
  // Windows：刚 taskkill 掉的 python 服务/浏览器进程句柄释放晚于本钩子（实测
  // `EPERM Permission denied: …firstep-tree-click-XXXX`）。node:fs 的 maxRetries
  // 退避窗口太短，所以自己退避重试（最多 ~3s）；实在删不掉只提示，不让验收变红
  // ——证据已经打在 stdout，残留目录名也打出来供手动清理。
  if (TMP) {
    for (let i = 0; i < 10; i++) {
      try { rmSync(TMP, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); break; }
      catch (e) {
        if (i === 9) console.log(`[after] 临时目录清理失败（句柄未释放，可手动删）：${TMP}`);
        else await new Promise((r) => setTimeout(r, 300));
      }
    }
  }
});

// 生成一个最小 stm32 工程并打开代码栏（零 LLM：题面留空 + 手输目录 + 自带 main.c）
async function openProjectTree() {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("dialog", (d) => d.dismiss());
  for (const p of ["**/api/recommend", "**/api/skeleton", "**/api/fix-errors"]) {
    await page.route(p, (r) => r.fulfill({ status: 502, contentType: "application/json", body: '{"detail":"用例注入"}' }));
  }
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
  assert.ok(existsSync(join(outDir, "main.c")), "前置：生成应落盘 main.c（否则代码栏无可点的文件）");

  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(dir);
  }, outDir);
  await page.waitForFunction((d) => document.getElementById("code-dir-label").textContent === d, outDir, { timeout: 15000 });
  await page.waitForFunction(() => !document.getElementById("code-tree").innerText.includes("加载中"), undefined, { timeout: 20000 });
  await page.waitForTimeout(300);
  return { page, problems };
}

// 把鼠标挪开再 hover 回来：点开文件后鼠标停在行上，直接再 hover 同一位置浏览器
// 不会再算一次 :hover（实测拿到 0×0 的假失败）。
async function hoverRow(page, locator) {
  await page.mouse.move(5, 5);
  await page.waitForTimeout(120);
  await locator.hover({ timeout: 8000 });
  await page.waitForTimeout(250);
}

test("文件树：真鼠标点文件名能打开编辑器（行内 ✎/🗑 不挡道）", async () => {
  const { page, problems } = await openProjectTree();
  const nameBtn = page.locator('#code-tree .code-tree-btn[data-code-file="main.c"]');
  assert.equal(await nameBtn.count(), 1, "树上应有 main.c 的文件行");

  // ① hover 必须做得了（修前：playwright 报 `✎ rename intercepts pointer events` 超时）
  await hoverRow(page, nameBtn);

  // ② 行内操作按钮（✎/🗑）仍在且不挡道（③ 才是硬判据：点文件名真的打开）。
  //    这里只断言它们存在于行内、且与文件名按钮**不是同一个盒子**（修前它们浮在
  //    按钮上面）——悬停可见性由第二条用例在 hover 显形下测，避免 :hover 抖动。
  const acts = await page.evaluate(() => {
    const row = document.querySelector(".code-tree-file")
      || null;
    const target = document.querySelector('#code-tree .code-tree-btn[data-code-file="main.c"]');
    const targetRow = target.closest(".code-tree-file");
    const nameBtn = targetRow.querySelector(".code-tree-btn");
    const list = [...targetRow.querySelectorAll(".code-tree-act")];
    return {
      count: list.length,
      buttons: list.map((b) => (b.getAttribute("aria-label") || b.title || "").trim()),
      insideNameBtn: list.some((b) => nameBtn.contains(b)),
      sameRowAsTarget: row === targetRow,
    };
  });
  assert.equal(acts.count, 2, `文件行内应有 ✎/🗑 两个操作按钮，实际 ${acts.count} 个`);
  assert.equal(acts.insideNameBtn, false,
    "操作按钮被塞进了文件名按钮内部（应当是同级的兄弟，否则又会变成指针重叠）");
  console.log(`    行内操作按钮：${acts.buttons.join(" / ")}`);

  // ③ 真鼠标点文件名（左侧文字区）→ 编辑器出现（点击同步派发、加载是异步的，必须等）
  const box = await nameBtn.boundingBox();
  await nameBtn.click({ position: { x: box.width * 0.4, y: box.height / 2 }, timeout: 8000 });
  await page.waitForSelector("#code-viewer .code-edit .code-ta", { timeout: 15000 });
  const tabName = await page.locator("#code-tabs .code-tab-name").first().innerText();
  assert.match(tabName, /main\.c/, `打开后活动标签应是 main.c，实际「${tabName}」`);
  assert.deepEqual(problems, []);
  await page.close();
});

test("文件树：行操作区只占自身宽度，不吃文件名的点击区", async () => {
  const { page } = await openProjectTree();
  const nameBtn = page.locator('#code-tree .code-tree-btn[data-code-file="main.c"]');
  await hoverRow(page, nameBtn);
  const geo = await page.evaluate(() => {
    const el = document.querySelector('#code-tree .code-tree-btn[data-code-file="main.c"]');
    const r = el.getBoundingClientRect();
    const act = el.closest(".code-tree-file").querySelector(".code-tree-actions");
    const cs = getComputedStyle(act);
    const ar = act.getBoundingClientRect();
    const x = r.left + r.width * 0.4;          // 文件名文字区（左侧 40%）
    const centre = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const hit = document.elementFromPoint(x, r.top + r.height / 2);
    return {
      rowW: Math.round(r.width), actW: Math.round(ar.width), display: cs.display,
      coverPct: Math.round(Math.max(0, Math.min(ar.right, r.right) - Math.max(ar.left, r.left)) / r.width * 100),
      hitInsideNameBtn: !!(hit && el.contains(hit)),
      hitTag: hit ? hit.tagName + "." + String(hit.className || "").split(" ")[0] : "（无）",
      centreInsideNameBtn: !!(centre && el.contains(centre)),
      centreTag: centre ? centre.tagName + "." + String(centre.className || "").split(" ")[0] : "（无）",
    };
  });
  // 注：本仓 .code-tree-actions 在文件行是 flex 兄弟（实测 getComputedStyle 报 "flex"
  // ——Chrome 对 inline-flex 的解析），故判据只要求「可见的 flex 族」而非逐字 inline-flex。
  assert.match(geo.display, /^(inline-)?flex$/, `hover 后行操作区应显形（display=${geo.display}）`);
  assert.ok(geo.actW > 0 && geo.actW <= 70, `行操作区应只占自身宽度（~55px），实际 ${geo.actW}px（行宽 ${geo.rowW}px）`);
  assert.ok(geo.coverPct <= 40, `行操作区横向覆盖了行的 ${geo.coverPct}% —— 会把文件名的点击区吃掉`);
  assert.equal(geo.centreInsideNameBtn, true,
    `文件名按钮正中央命中的是 ${geo.centreTag} —— 指针被别的元素接走（playwright hover 会因此超时，用户点名字无反应）`);
  assert.equal(geo.hitInsideNameBtn, true,
    `文件名文字处的命中元素是 ${geo.hitTag}，不是文件按钮`);
  await page.close();
});
