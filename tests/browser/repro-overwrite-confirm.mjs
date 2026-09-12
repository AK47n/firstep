// 复现：桌面「同名工程 → 覆盖确认」链路（工单 generate-overwrite/01）**不可达**。
//
// 真机取证三步（deep-audit 文件头口径）：
//   ① 真后端在真桌面上已有同名工程 → /api/generate 真返回那条「桌面上已有同名工程…」400；
//   ② 用**真前端**的纯函数链（parseHttpError → isConflictError）跑一遍，看判据取到的是什么；
//   ③ 反向验证：把判据改成「包含」而非「开头」→ 弹窗当场出现（证明断点就在这）。
//
// 清理：本脚本会在桌面建 `zz_audit_conflict_probe_STM32`（stm32 平台后缀）并在结束时删除；
// 同时把同名 .bak 一并清掉。不动用户其它任何文件。
import { chromium } from "playwright";
import { startServer } from "./server.mjs";
import { existsSync, rmSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const NAME = "zz_audit_conflict_probe_STM32";
const desktop = join(process.env.USERPROFILE, "Desktop");
const dir = join(desktop, NAME);
const cleanup = () => { for (const p of [dir, dir + ".bak"]) { try { rmSync(p, { recursive: true, force: true }); } catch {} } };

cleanup();
// 造一个「完整工程」标记（.contest_context.json）→ desktop_topic_dir_verdict 判 exists
mkdirSync(dir, { recursive: true });
writeFileSync(join(dir, ".contest_context.json"), "{}");
writeFileSync(join(dir, "main.c"), "// 旧工程（审计探针）\n");
console.log(`桌面探针目录已建：${dir}（含 .contest_context.json + main.c → verdict=exists）`);

const server = await startServer();
try {
  // ① 真后端：同名工程 → 400 与真实文案
  const raw = await fetch(server.url + "/api/generate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ platform: "stm32", slugs: ["motor"], main_c: "int main(void){return 0;}",
      problem_text: "审计探针：桌面同名工程覆盖链路", create_desktop_topic_dir: true,
      output_dir: ".", topic_id: NAME.replace(/_(STM32)$/, "") }),
  });
  const body = await raw.json().catch(() => ({}));
  console.log(`\n① 真后端 /api/generate → HTTP ${raw.status}\n   detail = ${JSON.stringify(body.detail)}`);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.route("**/api/recommend", (r) => r.fulfill({ status: 502, contentType: "application/json", body: '{"detail":"x"}' }));
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.querySelectorAll("#platforms .platform-card").length > 0);

  // ② 真前端纯函数链：app.js 的 handle() → new Error(parseHttpError(400, data).text) → isConflictError(msg)
  const verdict = await page.evaluate((detail) => {
    // 与 app.js handle() 里抛出的那一句逐字同形
    const parsed = window.parseHttpError(400, { detail });
    const msg = parsed.text;
    const out = {
      msg,
      isConflict: window.isConflictError(msg),
      startsWithPrefix: msg.indexOf(window.CONFLICT_MSG_PREFIX) === 0,
      prefix: window.CONFLICT_MSG_PREFIX,
      containsPrefix: msg.includes(window.CONFLICT_MSG_PREFIX),
    };
    // ③ 反向验证：判据改「包含」→ 立刻为真（断点就在「开头」这一条上）
    out.isConflictIfContains = msg.includes(window.CONFLICT_MSG_PREFIX);
    return out;
  }, body.detail);
  console.log(`\n② 真前端判据（app.js handle → fx/errors.parseHttpError → fx/generate.isConflictError）：`);
  console.log(`   抛出的 message = ${JSON.stringify(verdict.msg)}`);
  console.log(`   CONFLICT_MSG_PREFIX = ${JSON.stringify(verdict.prefix)}`);
  console.log(`   msg.indexOf(prefix)===0  → ${verdict.startsWithPrefix}`);
  console.log(`   isConflictError(msg)     → ${verdict.isConflict}   ← 决定「弹不弹覆盖确认」`);
  console.log(`   ③ 反向验证：若判据改「包含」→ ${verdict.isConflictIfContains}`);

  // 真机端到端：桌面模式点生成，看有没有确认弹窗
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.locator('#module-grid .module-card[data-add="motor"]').click();
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 30000 });
  await page.fill("#problem", "审计探针：桌面同名工程覆盖链路");
  await page.fill("#main-c", "int main(void) { return 0; }");
  await page.waitForTimeout(1500);
  console.log(`\n桌面输出勾选 = ${await page.locator("#desktop-topic-output").isChecked()}`);
  await page.click("#btn-generate");
  await page.waitForTimeout(4000);
  const modal = await page.locator(".ref-files-overlay").count();
  const msg = (await page.locator("#generate-msg").innerText().catch(() => "")).trim();
  console.log(`④ 真机点生成：确认弹窗=${modal}；#generate-msg=「${msg.slice(0, 220)}」`);
  console.log(`   结论：${modal === 0 && verdict.isConflict === false
    ? "覆盖确认链路不可达（用户只会看到一条报错，没有任何覆盖入口）"
    : "覆盖确认链路可用"}`);
  await browser.close();
} finally {
  cleanup();
  await server.stop();
  console.log(`\n清理：桌面探针目录与 .bak 已删除（存在残留 = ${existsSync(dir) || existsSync(dir + ".bak")}）`);
}
