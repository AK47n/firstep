// 危险操作确认文案纯函数单测（工单 ux-walkthrough-02/01）：
// reviseApplyConfirmMessage / platformSwitchConfirmMessage / pinResetConfirmMessage
// 只测外部行为（输入 → 文案），不测 ui/* 接线。
import test from "node:test";
import assert from "node:assert/strict";
import {
  reviseApplyConfirmMessage,
  platformSwitchConfirmMessage,
  pinResetConfirmMessage,
  overwriteBakHint,
  draftDeleteMessage,
  recentDeleteMessage,
} from "../../src/contest_generator/static/js/fx/danger.js";

test("reviseApplyConfirmMessage：有 diff 时展示新增/移除/不变计数", () => {
  const msg = reviseApplyConfirmMessage(
    { added: ["a", "b"], removed: ["c"], unchanged: ["d", "e", "f"] },
    6
  );
  assert.match(msg, /模块集变更：新增 2 · 移除 1 · 不变 3/);
  assert.match(msg, /覆盖重建/);
  assert.match(msg, /整树备份/);
  assert.match(msg, /可回滚/);
  assert.match(msg, /确定继续/);
});

test("reviseApplyConfirmMessage：diff 为空时用 slugCount 兜底", () => {
  const msg = reviseApplyConfirmMessage(null, 4);
  assert.match(msg, /按确认模块集（4 个模块）/);
  assert.ok(!msg.includes("模块集变更"));
});

test("reviseApplyConfirmMessage：全新增时只列新增", () => {
  const msg = reviseApplyConfirmMessage({ added: ["a", "b"], removed: [], unchanged: [] }, 2);
  assert.match(msg, /模块集变更：新增 2 · 移除 0 · 不变 0/);
  assert.match(msg, /覆盖重建/);
});

test("reviseApplyConfirmMessage：全移除时只列移除", () => {
  const msg = reviseApplyConfirmMessage({ added: [], removed: ["c", "d"], unchanged: [] }, 0);
  assert.match(msg, /模块集变更：新增 0 · 移除 2 · 不变 0/);
  assert.match(msg, /覆盖重建/);
});

test("reviseApplyConfirmMessage：diff 为空且无计数时展示 0（不炸）", () => {
  assert.match(reviseApplyConfirmMessage(undefined, undefined), /（0 个模块）/);
});

test("platformSwitchConfirmMessage：带计数时列出明细", () => {
  const msg = platformSwitchConfirmMessage({ moduleCount: 3, pinCount: 5, instanceCount: 2 });
  assert.match(msg, /已选模块 3 个、引脚绑定 5 处、实例配置 2 组/);
  assert.match(msg, /清空已选模块、引脚绑定与实例配置/);
  assert.match(msg, /确定继续/);
});

test("platformSwitchConfirmMessage：无计数时用通用描述（不炸）", () => {
  const msg = platformSwitchConfirmMessage();
  assert.match(msg, /清空已选模块、引脚绑定与实例配置/);
  assert.ok(!msg.includes("（"));
});

test("platformSwitchConfirmMessage：部分计数只列已提供项", () => {
  const msg = platformSwitchConfirmMessage({ moduleCount: 1 });
  assert.match(msg, /（已选模块 1 个）/);
  assert.ok(!msg.match(/引脚绑定 \d+ 处/));   // 括号明细不含未提供的计数
  assert.ok(!msg.match(/实例配置 \d+ 组/));
});

test("pinResetConfirmMessage：N>0 时含数量与可重新配置说明", () => {
  const msg = pinResetConfirmMessage(7);
  assert.match(msg, /全部 7 处引脚绑定还原为默认/);
  assert.match(msg, /可重新配置/);
  assert.match(msg, /确定继续/);
});

test("pinResetConfirmMessage：0 / 空值 → 无需还原语义", () => {
  assert.match(pinResetConfirmMessage(0), /当前没有引脚绑定，无需还原/);
  assert.match(pinResetConfirmMessage(undefined), /当前没有引脚绑定，无需还原/);
  assert.match(pinResetConfirmMessage(NaN), /当前没有引脚绑定，无需还原/);
});

test("overwriteBakHint：带目录名时给出 .bak 改名找回说明", () => {
  const msg = overwriteBakHint("Auto_Car_STM32");
  assert.match(msg, /「Auto_Car_STM32\.bak」/);
  assert.match(msg, /改名回「Auto_Car_STM32」/);
  assert.match(msg, /结果区一键恢复/);
});

test("overwriteBakHint：无目录名时用通用描述", () => {
  const msg = overwriteBakHint();
  assert.match(msg, /同名 \.bak 备份/);
  assert.match(msg, /结果区一键恢复/);
});

test("draftDeleteMessage：点名草稿前 20 字（超长截断）+ 撤销入口", () => {
  const msg = draftDeleteMessage("进弯道前先减速，然后保持中线行驶，再观察下一个路口");
  assert.match(msg, /「进弯道前先减速，然后保持中线行驶，再观察…」/);
  assert.match(msg, /撤销/);
  const short = draftDeleteMessage("短草稿");
  assert.match(short, /「短草稿」/);
  assert.match(draftDeleteMessage(""), /未命名草稿/);
});

test("recentDeleteMessage：点名输出目录 + 磁盘不受影响 + 撤销", () => {
  const msg = recentDeleteMessage({ output_dir: "C:\\桌面\\Auto_Car" });
  assert.match(msg, /C:\\桌面\\Auto_Car/);
  assert.match(msg, /磁盘上的工程不受影响/);
  assert.match(msg, /撤销/);
  assert.match(recentDeleteMessage(null), /该记录/);
});
