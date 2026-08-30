// instanceGapCount 纯函数单测（工单 ux-walkthrough-02/02）：
// 6.5 多实例卡「还差 N 个实例」徽章 / 导航点完成态的计数口径。
// 缺口 = 多实例模块中当前没有任何实例配置的个数（列表存在且非空即不算）。
import test from "node:test";
import assert from "node:assert/strict";
import { instanceGapCount } from "../../src/contest_generator/static/js/fx/module.js";

const mi = (slug) => ({ slug, multi_instance: { max: 3 } });
const plain = (slug) => ({ slug });

test("instanceGapCount：未展开（expanded 空）→ 0", () => {
  assert.equal(instanceGapCount([], {}), 0);
  assert.equal(instanceGapCount(undefined, {}), 0);
});

test("instanceGapCount：无多实例模块 → 0", () => {
  assert.equal(instanceGapCount([plain("led"), plain("key")], {}), 0);
});

test("instanceGapCount：全部未配 → 全部算缺口", () => {
  assert.equal(instanceGapCount([mi("led"), mi("key")], {}), 2);
  // 键存在但清空（用户删光）同样算缺口
  assert.equal(instanceGapCount([mi("led")], { led: [] }), 1);
});

test("instanceGapCount：部分配 → 只计未配模块", () => {
  const instances = {
    led: [{ name: "灯 1", variant: "red", pin: "PA1" }],
  };
  assert.equal(instanceGapCount([mi("led"), mi("key")], instances), 1);
});

test("instanceGapCount：全配 → 0（含多实例与普通模块混合）", () => {
  const instances = {
    led: [{ name: "灯 1", variant: "red", pin: "PA1" }],
    key: [{ name: "键 1", variant: "start", pin: "" }],
  };
  assert.equal(instanceGapCount([mi("led"), mi("key"), plain("lcd")], instances), 0);
});
