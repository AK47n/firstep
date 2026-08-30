// step7DoneState 纯函数单测（工单 step7-done/01）：步骤 7「引脚配置」完成判定修正
// —— 原逻辑只在 pinBindings 非空时才标完成，默认布线 / 无需配置情况下永不显示完成。
// 修正后：平台已选且已展开模块，且满足其一——无角色（无需配置）/ 已显式绑定 /
// 多实例已配引脚 / 已按默认布线生成成功。直接 import fx/draft.js。
import test from "node:test";
import assert from "node:assert/strict";
import { step7DoneState, step7WireMode } from "../../src/contest_generator/static/js/fx/draft.js";

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

// ---------------------------------------------------------------------------
// step7WireMode（ux-polish-02/01）：完成态细分——「已配置」与「按默认布线生成」
// 展示不同标记（完成计数不变，避免「已就绪」误导）
// ---------------------------------------------------------------------------

test("wireMode 未选平台/未展开模块：none（信息不足）", () => {
  assert.equal(step7WireMode({ ...base, chosenPlatform: "" }), "none");
  assert.equal(step7WireMode({ ...base, expandedCount: 0 }), "none");
});

test("wireMode 无角色需配置：configured（无需配置 = 已就绪）", () => {
  assert.equal(step7WireMode(base), "configured");
});

test("wireMode 有角色未绑定未生成：none（未完成）", () => {
  assert.equal(step7WireMode({ ...base, roles: [{}] }), "none");
});

test("wireMode 有角色已显式绑定：configured", () => {
  assert.equal(step7WireMode({ ...base, roles: [{}], roleBound: true }), "configured");
});

test("wireMode 多实例已配引脚：configured", () => {
  assert.equal(step7WireMode({ ...base, roles: [{}, {}], instBound: true }), "configured");
});

test("wireMode 有角色未绑定但已默认布线生成：default（非已就绪）", () => {
  assert.equal(step7WireMode({ ...base, roles: [{}], generated: true }), "default");
});
