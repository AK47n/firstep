// generateReadinessChecks / readinessSoftChecks / readinessRowHTML /
// readinessRowsHTML 纯函数单测（工单 frontend-es-modules/08）：
// 「检查能否生成」的判据（与 btn-generate 前置校验同源）与检查单行渲染。
// 直接 import fx/readiness.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  generateReadinessChecks, readinessSoftChecks, readinessRowHTML,
  readinessRowsHTML, readinessSummaryHTML, outputDirWarnRow,
} from "../../src/contest_generator/static/js/fx/readiness.js";

test("generateReadinessChecks 全空（桌面模式默认）：3/6/5/1 ❌，输出目录 ✅", () => {
  const checks = generateReadinessChecks({
    chosenPlatform: "", selectedSlugs: [], problem: "",
    desktopOutput: true, outputDir: "",
  });
  // 工单 group-choice-required/01 插了一条硬判据「功能组选择」（step 5，紧随模块清单）
  assert.equal(checks.length, 5);
  assert.deepEqual(
    checks.map((c) => c.step),
    [3, 6, 5, 1, 9]
  );
  assert.equal(checks[0].ok, false);
  assert.equal(checks[0].reason, "请先选择目标平台");
  assert.equal(checks[0].autoFixable, false);
  assert.equal(checks[1].ok, false);
  assert.equal(checks[1].reason, "请先选择模块");
  assert.equal(checks[1].autoFixable, true);
  assert.equal(checks[2].ok, true);   // 没有未选功能组（旧载荷 / 无组）→ 该条已就绪
  assert.equal(checks[3].ok, false);
  assert.equal(checks[3].reason, "请先填写赛题原文");
  assert.equal(checks[4].ok, true);   // 桌面模式：输出目录不强制
});

test("generateReadinessChecks 手动模式：题面不强制，输出目录必填", () => {
  const checks = generateReadinessChecks({
    chosenPlatform: "stm32", selectedSlugs: ["led"], problem: "",
    desktopOutput: false, outputDir: "",
  });
  assert.equal(checks[3].ok, true);   // 手动模式题面可空
  assert.equal(checks[4].ok, false);
  assert.equal(checks[4].reason, "请填写输出目录");
});

test("generateReadinessChecks 全齐：4 项全 ok；桌面模式忽略输出目录", () => {
  const checks = generateReadinessChecks({
    chosenPlatform: "mspm0", selectedSlugs: ["led", "uart"],
    problem: "2026 电赛……", desktopOutput: true, outputDir: "D:\\x",
  });
  assert.ok(checks.every((c) => c.ok));
  // 桌面模式即使 outputDir 空也不拦
  const d = generateReadinessChecks({
    chosenPlatform: "mspm0", selectedSlugs: ["led"], problem: "题面",
    desktopOutput: true, outputDir: "",
  });
  assert.equal(d[4].ok, true);
});

test("readinessSoftChecks：推荐未跑 / 骨架未生成 → ⚠（中性可选项措辞）；空模块不重复提示推荐", () => {
  const both = readinessSoftChecks({
    selectedSlugs: ["led"], recommended: false, hasMainC: false,
  });
  assert.deepEqual(both.map((c) => c.step), [5, 8]);
  assert.equal(both[0].ok, false);
  assert.ok(both[0].reason.includes("可选项"));
  assert.equal(both[1].ok, false);
  assert.ok(both[1].reason.includes("可选项"));

  const recDone = readinessSoftChecks({
    selectedSlugs: ["led"], recommended: true, hasMainC: false,
  });
  assert.deepEqual(recDone.map((c) => c.step), [8]);

  const noSlugs = readinessSoftChecks({
    selectedSlugs: [], recommended: false, hasMainC: false,
  });
  assert.deepEqual(noSlugs.map((c) => c.step), [8]);

  const allDone = readinessSoftChecks({
    selectedSlugs: ["led"], recommended: true, hasMainC: true,
  });
  assert.deepEqual(allDone, []);
});

test("readinessRowHTML：❌ 行显示原因 + 去第 N 步；✅ 行无动作", () => {
  const bad = readinessRowHTML(
    { step: 3, title: "目标平台", reason: "请先选择目标平台", ok: false, autoFixable: false },
    { recommendEnabled: true }
  );
  assert.ok(bad.includes('class="rc-row bad"'));
  assert.ok(bad.includes('data-step="3"'));
  assert.ok(bad.includes("✗"));
  assert.ok(bad.includes("请先选择目标平台"));
  assert.ok(bad.includes('class="rc-go" data-step="3"'));
  assert.ok(!bad.includes("一键跑推荐"));   // 平台不可自动补

  const ok = readinessRowHTML(
    { step: 9, title: "输出目录并生成", reason: "请填写输出目录", ok: true, autoFixable: false },
    { recommendEnabled: true }
  );
  assert.ok(ok.includes('class="rc-row ok"'));
  assert.ok(ok.includes("✓"));
  assert.ok(ok.includes("已就绪"));
  assert.ok(!ok.includes("rc-go"));
  assert.ok(!ok.includes("rc-recommend"));
});

test("readinessRowHTML：模块 ❌ 时 recommendEnabled 控制「一键跑推荐」", () => {
  const m = { step: 6, title: "模块清单与平台警告", reason: "请先选择模块", ok: false, autoFixable: true };
  assert.ok(readinessRowHTML(m, { recommendEnabled: true }).includes("一键跑推荐"));
  assert.ok(!readinessRowHTML(m, { recommendEnabled: false }).includes("一键跑推荐"));
  // ok=true 即使 autoFixable 也不出自动按钮
  const okM = { step: 6, title: "模块清单与平台警告", reason: "请先选择模块", ok: true, autoFixable: true };
  assert.ok(!readinessRowHTML(okM, { recommendEnabled: true }).includes("一键跑推荐"));
});

test("readinessSummaryHTML：硬判据全就绪 → 绿色「点生成工程」总结；否则中性引导", () => {
  const ok = readinessSummaryHTML(true);
  assert.ok(ok.includes("硬判据全部就绪"));
  assert.ok(ok.includes("点「生成工程」即可"));
  assert.ok(ok.includes("rc-summary ok"));
  const notOk = readinessSummaryHTML(false);
  assert.ok(notOk.includes("还有未就绪项"));
  assert.ok(notOk.includes("去第 N 步"));
  assert.ok(!notOk.includes("rc-summary ok"));
});

test("readinessRowHTML：软行 ⚠ + 定位按钮，无自动按钮；标题引号转义", () => {
  const soft = readinessRowHTML(
    { step: 5, title: 'AI 推荐"模块"', reason: "建议跑一次 AI 推荐（可选）", ok: false, soft: true },
    { recommendEnabled: true }
  );
  assert.ok(soft.includes('class="rc-row soft"'));
  assert.ok(soft.includes("⚠"));
  assert.ok(soft.includes("建议跑一次 AI 推荐（可选）"));
  assert.ok(soft.includes('class="rc-go" data-step="5"'));
  assert.ok(!soft.includes("一键跑推荐"));
  assert.ok(soft.includes("AI 推荐&quot;模块&quot;"));
});

test("readinessRowsHTML：多项 join，每项一个 rc-row", () => {
  const items = generateReadinessChecks({
    chosenPlatform: "", selectedSlugs: [], problem: "", desktopOutput: true, outputDir: "",
  });
  const out = readinessRowsHTML(items, { recommendEnabled: false });
  assert.equal((out.match(/class="rc-row /g) || []).length, items.length);
  assert.equal(items.length, 5);   // 3 / 6 / 5（功能组选择）/ 1 / 9
  assert.ok(out.indexOf('data-step="3"') < out.indexOf('data-step="1"'));
});

test("outputDirWarnRow：exists/occupied 给软预警行，其它 verdict 返回 null（工单 06）", () => {
  const exists = outputDirWarnRow({ dir: "C:\\Desktop\\Auto_Car_STM32", verdict: "exists" });
  assert.equal(exists.step, 9);
  assert.equal(exists.soft, true);
  assert.equal(exists.ok, false);
  assert.ok(exists.reason.includes("备份为 .bak"));
  const occupied = outputDirWarnRow({ dir: "C:\\out\\occupied", verdict: "occupied" });
  assert.ok(occupied.reason.includes("非空"));
  // 不预警的情形：new/clean/absent/empty（无冲突或目录不存在）/ needs_title（拿不到名）
  assert.equal(outputDirWarnRow({ dir: "C:\\Desktop\\x", verdict: "new" }), null);
  assert.equal(outputDirWarnRow({ dir: "C:\\Desktop\\x", verdict: "clean" }), null);
  assert.equal(outputDirWarnRow({ dir: "C:\\out\\a", verdict: "absent" }), null);
  assert.equal(outputDirWarnRow({ dir: "C:\\out\\e", verdict: "empty" }), null);
  assert.equal(outputDirWarnRow({ dir: null, verdict: "needs_title" }), null);
  assert.equal(outputDirWarnRow(null), null);
  // 预警行走既有软行渲染：⚠ 展示 + 去第 9 步按钮
  const html = readinessRowHTML(outputDirWarnRow({ dir: "D:\\p", verdict: "exists" }), {});
  assert.ok(html.includes("rc-row soft"));
  assert.ok(html.includes("⚠"));
  assert.ok(html.includes('class="rc-go" data-step="9"'));
});
