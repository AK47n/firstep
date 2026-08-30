// tests/js/clear-jargon-guard.test.mjs — 行话人话化守卫（工单 beginner-gap-closure/03）：
// 用户可见界面不再直接出现 .contest_*.json 原始文件名、「写盘」「锚已失效」「人工改标」
// 等工程行话，人话文案在场（静态读源断言，防退化回工程话——对齐 glossary-refs 先例）。
// 另含解析型守卫（评审整改）：本轮改动的 ui 模块逐一 node --check——静态 includes
// 断言防不住「改文案时顺坏拼接」这类语法回归（77ecfeb 评审实例）。
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const src = (p) =>
  readFileSync(
    new URL("../../src/contest_generator/static/js/" + p, import.meta.url),
    "utf8"
  );
const tasksUi = src("ui/generate-tasks.js");
const paramsUi = src("ui/params.js");
const paramsFx = src("fx/params.js");
const taskFx = src("fx/task.js");
const reviseUi = src("ui/generate-revise.js");

test("index.html：任务推进/全局商量/参数速调详情不再暴露 .contest_*.json 文件名", () => {
  assert.ok(!html.includes(".contest_ideas.json"), "草稿文件名仍出现在界面");
  assert.ok(!html.includes(".contest_idea_chat.json"), "全局商量历史文件名仍出现在界面");
  assert.ok(!html.includes(".contest_params.json"), "参数表文件名仍出现在界面");
  assert.ok(html.includes("草稿自动保存到工程内"));
  assert.ok(html.includes("历史自动保存到工程内"));
  assert.ok(html.includes("参数表自动保存到工程内"));
});

test("重新拆解确认：旧清单自动备份，不露 .bak 文件名", () => {
  assert.ok(!tasksUi.includes(".contest_tasks.json.bak"), "备份文件名仍出现在确认弹窗");
  assert.ok(tasksUi.includes("旧清单会自动备份"));
});

test("任务完成状态：不再出现「人工改标」", () => {
  assert.ok(!tasksUi.includes("人工改标"));
  assert.ok(tasksUi.includes("手动调整状态"));
});

test("参数应用状态：「写盘」改「保存」", () => {
  assert.ok(!paramsUi.includes("写盘"));
  assert.ok(paramsUi.includes("正在应用参数：备份 + 保存 + 编译验证…"));
});

test("参数失效徽章：「锚已失效」改「位置已变」", () => {
  assert.ok(!paramsFx.includes("锚已失效"));
  assert.ok(paramsFx.includes("位置已变"));
});

test("fx/task.js：下一步提示用「第 N 步」，不再拼原始任务 id", () => {
  assert.ok(taskFx.includes("下一步 → 第 "));
  assert.ok(!taskFx.includes('esc(next.id) + "："'));
});

test("想法结果卡：ui 层传 seqById（受影响任务序号人话，防漏传）", () => {
  assert.ok(tasksUi.includes("seqById"));
});

test("fx/task.js：备份展示不再输出原始 backup_id（迭代 meta 与变更明细）", () => {
  assert.ok(!taskFx.includes('备份 <span class="slug">'));
  assert.ok(!taskFx.includes('备份：<span class="slug">'));
  assert.ok(taskFx.includes("已备份"));
});

test("修订结果：备份不露 backup_id（已备份 · 修订时间）", () => {
  assert.ok(!reviseUi.includes('备份：<span class="slug">'));
  // 评审整改（02 轮 Standards 轴）：钉住正确拼接——错误写法「修订时间：\" + esc(…」
  // 把代码当文案仍会满足上方断言，故额外钉：正确闭合引号 + 错误字面量形式缺席
  assert.ok(reviseUi.includes("已备份 · 修订时间：'"));
  assert.ok(!reviseUi.includes('修订时间：" + esc'));
});

test("解析型守卫：本轮改动的 ui 模块均可解析（防语法回归）", () => {
  // 评审整改（77ecfeb 两轴评审）：includes 类静态断言防不住「改文案顺坏拼接」，
  // 模块级语法错误会让整个 ES 模块图加载失败——改动的 ui 文件逐一用
  // vm.SourceTextModule 解析（单进程多文件；node --check 会把 ESM 当 CJS 误报）。
  const files = [
    "src/contest_generator/static/js/ui/generate-revise.js",
    "src/contest_generator/static/js/ui/generate-tasks.js",
    "src/contest_generator/static/js/ui/params.js",
  ];
  const script = [
    'const fs=require("fs"),vm=require("vm");',
    "for(const f of process.argv.slice(1)){",
    '  new vm.SourceTextModule(fs.readFileSync(f,"utf8"),{identifier:f});',
    "}",
  ].join("");
  const r = spawnSync(process.execPath,
    ["--no-warnings", "--experimental-vm-modules", "-e", script, ...files],
    { cwd: new URL("../..", import.meta.url), encoding: "utf8" });
  assert.equal(r.status, 0, `模块解析失败：${r.stderr || r.stdout}`);
});
