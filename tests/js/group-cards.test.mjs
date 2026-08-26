// 功能组选择卡纯函数单测（工单 recommend-exclusive-groups/04）：组卡渲染
// （radio/徽标/role/hint 标注）、autoAdd 同组去重、换选 swap、取消整组、
// 同组多选警告、旧载荷（无 exclusive_groups）容错。直接 import fx/module.js
//（不再字符串提取）；不碰 DOM / fetch。
// 接线静态断言按归属指向 ui/generate-recommend.js（阶段 2 工单 12 重指向）。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import {
  groupOfSlug, applyGroupRadio, autoAddDedup, groupConflicts,
  renderGroupCards, groupRequirementNote,
} from "../../src/contest_generator/static/js/fx/module.js";

const src = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
  "utf8"
);

const groups = [
  {
    id: "gray-track", label: "8 路灰度传感器驱动", hint: false,
    members: [
      { slug: "huidu", role: "仅 8 路灰度读取，不含巡线核心" },
      { slug: "pid", role: "灰度读取 + PID 巡线 + 编码器速度环" },
      { slug: "xunji", role: "灰度读取 + 加权质心巡线（开环）" },
    ],
    recommended: ["pid", "xunji"],
  },
  {
    id: "attitude-hold", label: "航向保持 / 姿态传感器", hint: true,
    members: [
      { slug: "imu_uart", role: "UART 串口陀螺仪" },
      { slug: "ml_mpu6050", role: "I2C + DMP 姿态解算" },
    ],
    recommended: [],
  },
];
const modules = [
  { slug: "pid", reason: "PID 循迹，双平台" },
  { slug: "xunji", reason: "质心巡线，2024H 真机验证" },
];

test("组卡渲染：label + hint 标注 + 成员行（radio/slug/role）+ AI 推荐徽标与理由", () => {
  const rendered = renderGroupCards(groups, modules, []);

  assert.match(rendered, /8 路灰度传感器驱动/);
  assert.match(rendered, /航向保持 \/ 姿态传感器/);
  // hint 卡带「AI 未推荐，题面疑似需要——请确认」标注
  assert.match(rendered, /AI 未推荐，题面疑似需要——请确认/);
  // 成员行含 radio + slug + role
  assert.match(rendered, /data-group-slug="huidu"/);
  assert.match(rendered, /data-group-slug="pid"/);
  assert.match(rendered, /data-group-slug="xunji"/);
  assert.match(rendered, /data-group-slug="imu_uart"/);
  assert.match(rendered, /data-group-slug="ml_mpu6050"/);
  assert.match(rendered, /仅 8 路灰度读取，不含巡线核心/);
  assert.match(rendered, /UART 串口陀螺仪/);
  // AI 推荐徽标只给命中成员（pid/xunji 两个），hint 卡（recommended 空）无徽标
  assert.equal((rendered.match(/AI 推荐/g) || []).length, 2);
  assert.match(rendered, /PID 循迹，双平台/);
  assert.match(rendered, /质心巡线，2024H 真机验证/);
  // 无已选成员 → 无 checked
  assert.doesNotMatch(rendered, /checked/);
});

test("组卡渲染：已选成员为默认选中（同组多个按 data.modules 序 = AI 推荐序取第一个）", () => {
  const rendered = renderGroupCards(groups, modules, ["xunji"]);
  assert.match(rendered, /data-group-slug="xunji" checked/);
  // 同组两个成员都在 selectedSlugs（手动添加所致）→ 按 data.modules 序取第一个
  // 命中成员（spec:107：AI 首选由 data.modules 顺序决定）
  const both = renderGroupCards(groups, modules, ["xunji", "pid"]);
  assert.match(both, /data-group-slug="pid" checked/);
  assert.doesNotMatch(both, /data-group-slug="xunji" checked/);
  // data.modules 序与成员登记序不同（xunji 先于 pid）→ data.modules 序优先
  const swapOrder = renderGroupCards(groups, [{ slug: "xunji" }, { slug: "pid" }], ["pid", "xunji"]);
  assert.match(swapOrder, /data-group-slug="xunji" checked/);
  // 成员都不在 data.modules（全为手动添加）→ 按组成员登记序兜底
  const manualOnly = renderGroupCards(groups, [], ["huidu", "xunji"]);
  assert.match(manualOnly, /data-group-slug="huidu" checked/);
});

test("组卡渲染：转义模型文本，避免注入可交互控件", () => {
  const rendered = renderGroupCards(
    [{
      id: "g", label: "<b>L</b>", hint: false,
      members: [{ slug: "<script>", role: "<input>alert(1)</input>" }],
      recommended: ["<script>"],
    }],
    [],
    []
  );
  assert.match(rendered, /data-group-slug="&lt;script&gt;"/);
  assert.match(rendered, /&lt;input&gt;alert\(1\)&lt;\/input&gt;/);
  assert.doesNotMatch(rendered, /<script\b/);
});

test("旧载荷（无 exclusive_groups / 空数组）→ 不渲染组卡、不抛错", () => {
  assert.equal(renderGroupCards(undefined, undefined, undefined), "");
  assert.equal(renderGroupCards([], [], []), "");
  assert.equal(renderGroupCards(null, [], []), "");
});

test("autoAdd 去重：同组多推只首个入集（按 data.modules 顺序）", () => {
  assert.deepEqual(
    autoAddDedup(groups, [], [{ slug: "pid" }, { slug: "xunji" }]),
    ["pid"]
  );
  assert.deepEqual(
    autoAddDedup(groups, [], [{ slug: "xunji" }, { slug: "pid" }]),
    ["xunji"]
  );
});

test("autoAdd 去重：已选同组任一成员 → 后续同组推荐跳过（保留既有）", () => {
  assert.deepEqual(
    autoAddDedup(groups, ["xunji"], [{ slug: "pid" }, { slug: "xunji" }]),
    ["xunji"]
  );
  assert.deepEqual(
    autoAddDedup(groups, ["imu_uart"], [{ slug: "pid" }, { slug: "motor" }]),
    ["imu_uart", "pid", "motor"]  // 不同组照常加入，非组模块照常加入
  );
});

test("autoAdd 去重：旧载荷 / 无组库 = 逐个照加（行为与现状一致）", () => {
  assert.deepEqual(autoAddDedup([], [], [{ slug: "a" }, { slug: "b" }]), ["a", "b"]);
  assert.deepEqual(autoAddDedup(undefined, undefined, undefined), []);
});

test("换选 swap：点击成员 → 移除同组其他成员后加入该成员", () => {
  assert.deepEqual(applyGroupRadio(groups, ["huidu"], "gray-track", "pid"), ["pid"]);
  assert.deepEqual(applyGroupRadio(groups, ["xunji", "motor"], "gray-track", "huidu"), ["motor", "huidu"]);
});

test("取消整组：再点已选成员 → 移除该组全部成员（不强制选）", () => {
  assert.deepEqual(applyGroupRadio(groups, ["pid"], "gray-track", "pid"), []);
  assert.deepEqual(applyGroupRadio(groups, ["xunji", "imu_uart"], "gray-track", "xunji"), ["imu_uart"]);
});

test("换选/取消：未知组 id 与旧载荷不炸（按无组处理 = 只加入）", () => {
  assert.deepEqual(applyGroupRadio(groups, ["motor"], "no-such-group", "pid"), ["motor", "pid"]);
  assert.deepEqual(applyGroupRadio([], ["motor"], "gray-track", "pid"), ["motor", "pid"]);
});

test("同组多选警告：同组 ≥2 成员在 selectedSlugs → 出冲突条目（不硬拦）", () => {
  assert.deepEqual(groupConflicts(groups, ["pid", "xunji", "imu_uart"]), [
    { id: "gray-track", label: "8 路灰度传感器驱动", slugs: ["pid", "xunji"] },
  ]);
  assert.deepEqual(groupConflicts(groups, ["huidu", "pid"]), [
    { id: "gray-track", label: "8 路灰度传感器驱动", slugs: ["huidu", "pid"] },
  ]);
});

test("同组多选警告：跨组各一成员 / 单成员 / 旧载荷 → 无冲突", () => {
  assert.deepEqual(groupConflicts(groups, ["pid", "imu_uart"]), []);
  assert.deepEqual(groupConflicts(groups, ["huidu"]), []);
  assert.deepEqual(groupConflicts(undefined, ["pid", "xunji"]), []);
  assert.deepEqual(groupConflicts([], ["pid", "xunji"]), []);
});

test("需求清单灰注：组内成员 → 灰注（含理由、不产出可移除 chip）", () => {
  const note = groupRequirementNote(groups, "pid", "PID 循迹，双平台");
  assert.match(note, /已在『功能组选择』中/);
  assert.match(note, /PID 循迹，双平台/);
  assert.doesNotMatch(note, /data-remove/);
  assert.match(note, /<span class="muted">/);
});

test("需求清单灰注：非组模块 → null（chips 交互不变）", () => {
  assert.equal(groupRequirementNote(groups, "motor", "驱动"), null);
  assert.equal(groupRequirementNote(undefined, "pid", ""), null);
  assert.equal(groupRequirementNote([], "pid", ""), null);
});

test("generate-recommend.js 推荐结果区接线：组卡渲染 / autoAdd 去重 / 单选交互 / 冲突警告", () => {
  assert.match(src, /renderGroupCards\(groups, data\.modules, selectedSlugs\)/);
  assert.match(src, /selectedSlugs = autoAddDedup\(groups, selectedSlugs, data\.modules\)/);
  assert.match(src, /applyGroupRadio\(\(lastRecommend \|\| \{\}\)\.exclusive_groups \|\| \[\],/);
  assert.match(src, /groupConflicts\(\(lastRecommend \|\| \{\}\)\.exclusive_groups \|\| \[\], selectedSlugs\)/);
});
