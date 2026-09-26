// tests/browser/hwcheck-capacity-note.spec.mjs — 真机验收（工单 hwcheck-hygiene/04）：
// **母版里没有 mspm0.syscfg** 时，检测页要把「这一趟没判装不装得下」**说出来**。
//
// 为什么这条判据只能在真浏览器里验：工单的验收标准是"响应里 / **页面上**要能看出来"。
// 响应那一半由 pytest 钉住（`wiring.capacity_note` 进了载荷）；"页面真的把它渲染在
// 接线那一块"是 ui 接线行为——按 spec 的测试决策，ui 行为只由真浏览器作证。
//
// 为什么单独一个 spec（而不是并进 `hwcheck.spec.mjs`）：这条判据的前提要换掉服务端的
// **库根**，而配置在**起服务前**读 `FIRSTEP_BROWSER_CONFIG_EXTRA`（`server.mjs` 的
// `extraConfigKeys`）——一个进程一份配置，与共用真母版的那份 spec 起不了同一个服务。
//
// 为什么造的是"母版在、但没有 syscfg"这一档（而不是"母版整个没导入"）：**后者在页面上
// 根本走不到这一步**——平台卡在 `status !== "ready"` 时是置灰不可点的（母版没导入 =
// 平台不可用），学生连 mspm0 都选不上。可到达的那一档正是"平台可用、这份配置不在"。
//
// 前置：npm install && npx playwright install chromium
// 运行：node --test tests/browser/hwcheck-capacity-note.spec.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

const REPO_MASTERS = fileURLToPath(new URL("../../library/masters/", import.meta.url));
// 「母版已导入、但没带 mspm0.syscfg」的库根（`hwcheck_view` 对它是"判不了就不判"，
// 并如实把原因写进 `wiring.capacity_note`）。
const mastersDir = mkdtempSync(join(tmpdir(), "firstep-nosyscfg-"));
cpSync(join(REPO_MASTERS, "mspm0.json"), join(mastersDir, "mspm0.json"));
cpSync(join(REPO_MASTERS, "mspm0"), join(mastersDir, "mspm0"), {
  recursive: true,
  filter: (src) => basename(src) !== "mspm0.syscfg",
});
// ⚠ 必须在 `startServer()` **之前**设：`seedConfig()` 在起子进程那一刻读它
// （静态 import 只把模块取进来，不读 env）。
process.env.FIRSTEP_BROWSER_CONFIG_EXTRA = JSON.stringify({ masters_dir: mastersDir });

let server = null;
let browser = null;
let page = null;

test.before(async () => {
  server = await startServer();
  browser = await chromium.launch();
  page = await browser.newPage();
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();
  try { rmSync(mastersDir, { recursive: true, force: true }); } catch { /* 临时目录 */ }
});

test("母版里没有 mspm0.syscfg：检测页在接线区如实说「这一趟没判装不装得下」（工单 hwcheck-hygiene/04）", async () => {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#hwcheck-platforms .platform-card",
    { state: "attached", timeout: 30000 });
  await page.click('nav button[data-tab="hwcheck"]');
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });

  await page.click('[data-hwcheck-platform="mspm0"]');
  await page.click("#btn-hwcheck-preview");

  // 接线区里那句话（`wiring.capacity_note` → `hwcheckPinCapacityNoteHTML`）
  await page.waitForSelector("#hwcheck-wiring .hwcheck-warn", { timeout: 30000 });
  const shown = await page.textContent("#hwcheck-wiring");
  assert.ok(shown.includes("没判"), `接线区没有「没判」那句话：${(shown || "").slice(0, 200)}`);
  assert.ok(shown.includes("母版"), `那句话没说清前提（母版没导入）：${(shown || "").slice(0, 200)}`);
  // 页面上**不许**出现 markdown 粗体标记（工单 02 的口径：域层文案也在射程内）
  assert.ok(!shown.includes("**"), `页面上出现了字面星号：${(shown || "").slice(0, 200)}`);
});
