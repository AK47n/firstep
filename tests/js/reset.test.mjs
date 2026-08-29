// tests/js/reset.test.mjs — 「重置本地记录」键判定纯件（reset-local-records/02）：
// 四类题相关键命中、UI 偏好/全局统计/无关键不命中、collect 保序去重。
// 仿 wiring.test.mjs 先例（node:test + assert/strict）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  RESETTABLE_EXACT_KEYS,
  RESETTABLE_KEY_PREFIXES,
  collectResettableKeys,
  isResettableKey,
} from "../../src/contest_generator/static/js/fx/reset.js";

test("四类题相关键全部命中", () => {
  assert.equal(isResettableKey("firstep.checklist.v1.t1/1"), true);
  assert.equal(isResettableKey("firstep.checklist.v1.any/deep"), true);
  assert.equal(isResettableKey("firstep.draft.v1"), true);
  assert.equal(isResettableKey("score-checklist:D:/contest/demo"), true);
  assert.equal(isResettableKey("firstep.buy-decisions.v1"), true);
});

test("UI 偏好 / 全局统计 / 无关键不命中", () => {
  assert.equal(isResettableKey("firstep.theme"), false);
  assert.equal(isResettableKey("firstep.mainc.zoom"), false);
  assert.equal(isResettableKey("firstep.settingsCollapse.v1"), false);
  assert.equal(isResettableKey("firstep.usage.v1"), false);
  assert.equal(isResettableKey("firstep_tab_id"), false); // sessionStorage，非清理范围
  assert.equal(isResettableKey("some-other-key"), false);
  assert.equal(isResettableKey(""), false);
  assert.equal(isResettableKey(null), false);
});

test("清单常量与判定一致（单源防线）", () => {
  // 任何条目 == 精确键 → 命中；任何前缀字符串 → 命中（防清单与判定漂移）
  for (const k of RESETTABLE_EXACT_KEYS) assert.equal(isResettableKey(k), true);
  for (const p of RESETTABLE_KEY_PREFIXES) {
    assert.equal(isResettableKey(p + "x"), true);
  }
});

test("collectResettableKeys 保序去重且只留命中键", () => {
  const keys = [
    "firstep.theme",          // 保留
    "firstep.checklist.v1.t1/1",
    "firstep.checklist.v1.t1/1", // 重复
    "firstep.draft.v1",
    "score-checklist:D:/x",
    "firstep.buy-decisions.v1",
    "firstep.usage.v1",       // 保留
  ];
  assert.deepEqual(collectResettableKeys(keys), [
    "firstep.checklist.v1.t1/1",
    "firstep.draft.v1",
    "score-checklist:D:/x",
    "firstep.buy-decisions.v1",
  ]);
});

test("collectResettableKeys 空输入", () => {
  assert.deepEqual(collectResettableKeys([]), []);
  assert.deepEqual(collectResettableKeys(["a", "b"]), []);
});
