// step7DoneState 纯函数单测（工单 step7-done/01）：步骤 7「引脚配置」完成判定修正
// —— 原逻辑只在 pinBindings 非空时才标完成，默认布线 / 无需配置情况下永不显示完成。
// 修正后：平台已选且已展开模块，且满足其一——无角色（无需配置）/ 已显式绑定 /
// 多实例已配引脚 / 已按默认布线生成成功。直接 import fx/draft.js。
import test from "node:test";
import assert from "node:assert/strict";
import { step7DoneState } from "../../src/contest_generator/static/js/fx/draft.js";

const base = { chosenPlatform: "stm32", expandedCount: 2, roles: [], roleBound: false, instBound: false, generated: false };

test("未选平台：不予完成（引脚无从谈起）", () => {
  assert.equal(step7DoneState({ ...base, chosenPlatform: "" }), false);
});

test("已选平台但未展开模块：premature，不予完成", () => {
  assert.equal(step7DoneState({ ...base, expandedCount: 0 }), false);
});

test("已展开但无引脚角色：无需配置 = 完成", () => {
  assert.equal(step7DoneState(base), true);
});

test("有角色未绑定未生成：未完成（默认流程生成前保持待办）", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}] }), false);
});

test("有角色已显式绑定：完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], roleBound: true }), true);
});

test("有角色未绑定但已生成成功：默认布线被隐式接受 = 完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], generated: true }), true);
});

test("多实例已配引脚（无角色绑定、未生成）：完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}, {}], instBound: true }), true);
});

test("多实例未配引脚：维持未完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], instBound: false }), false);
});
