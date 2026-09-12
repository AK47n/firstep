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
  groupOfSlug, applyGroupChoices, recordGroupChoice, autoAddDedup, groupConflicts,
  renderGroupCards, groupRequirementNote,
} from "../../src/contest_generator/static/js/fx/module.js";

const src = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
  "utf8"
);

const groups = [
  {
    id: "gray-track", label: "8 路灰度传感器驱动", hint: false, choice_required: true,
    members: [
      { slug: "huidu", role: "仅 8 路灰度读取，不含巡线核心" },
      { slug: "pid", role: "灰度读取 + PID 巡线 + 编码器速度环" },
      { slug: "xunji", role: "灰度读取 + 加权质心巡线（开环）" },
    ],
    recommended: ["pid", "xunji"],
  },
  {
    id: "attitude-hold", label: "航向保持 / 姿态传感器", hint: true, choice_required: false,
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

test("组卡渲染：只有用户点过的组才画选中态（工单 group-choice-required/01 改口径）", () => {
  // 旧口径：从 selectedSlugs 反推默认选中（AI 推荐件自动勾上）——已由用户拍板换成
  // 「不预选、用户点过才算」。这里逐条改写为 choices 驱动。
  const rendered = renderGroupCards(groups, modules, ["xunji"], { "gray-track": "xunji" });
  assert.match(rendered, /data-group-slug="xunji" checked/);
  // 同一份集合、但没有 choices（用户没点过）→ 一律不画选中
  const untouched = renderGroupCards(groups, modules, ["xunji"], {});
  assert.doesNotMatch(untouched, /checked/);
  // 点的是非推荐成员也照样选中（用户说了算）
  const picked = renderGroupCards(groups, modules, ["pid"], { "gray-track": "huidu" });
  assert.match(picked, /data-group-slug="huidu" checked/);
  assert.doesNotMatch(picked, /data-group-slug="pid" checked/);
});

test("组卡渲染：转义模型文本，避免注入可交互控件", () => {
  const rendered = renderGroupCards(
    [{
      id: "g", label: "<b>L</b>", hint: false, choice_required: false,
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

// 同组互斥收敛（工单 real-acceptance/04）：载荷 recommended ≤1 + dropped =
// 被收敛剔掉的成员（AI 也推荐过它，只是组内只能留一个）——本卡标注可见，
// 用户点它即换选（换选语义由 applyGroupChoices / recordGroupChoice 保证——工单 group-choice-required/01 取代了 applyGroupRadio）。
const convergedGroups = [
  {
    id: "zigbee-rx", label: "Zigbee 无线链路（接收侧）", hint: false, choice_required: true,
    members: [
      { slug: "zigbee_link", role: "任意字节帧收发" },
      { slug: "zigbee_uart", role: "固定 DIP-4 ID 帧接收" },
    ],
    recommended: ["zigbee_link"],
    candidates: ["zigbee_uart"],
    dropped: ["zigbee_uart"],
  },
];

test("组卡渲染：收敛后的组卡 = 一个推荐态 + 被剔成员标「同组互斥·未选中」", () => {
  const rendered = renderGroupCards(
    convergedGroups,
    [{ slug: "zigbee_link", reason: "透传链路满足3m以上通信" }],
    ["zigbee_link"],
    { "zigbee-rx": "zigbee_link" }   // 用户点过这一组（工单 group-choice-required/01）
  );

  assert.equal((rendered.match(/AI 推荐/g) || []).length, 1);
  assert.match(rendered, /data-group-slug="zigbee_link" checked/);
  assert.match(rendered, /同组互斥·未选中/);
  assert.match(rendered, /透传链路满足3m以上通信/);
  // 被剔成员仍可点选（radio 在场），不是灰字死行
  assert.match(rendered, /data-group-slug="zigbee_uart"/);
  assert.equal((rendered.match(/同组互斥·未选中/g) || []).length, 1);
});

test("组卡渲染：无 dropped 字段（旧载荷）→ 零标注、零报错", () => {
  const legacy = [{ ...convergedGroups[0], dropped: undefined, candidates: undefined }];
  const rendered = renderGroupCards(legacy, [], ["zigbee_link"], { "zigbee-rx": "zigbee_link" });
  assert.doesNotMatch(rendered, /同组互斥·未选中/);
  assert.match(rendered, /data-group-slug="zigbee_link"/);
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

test("换选 swap：用户点成员 → 记录选择 + 同组旧成员被顶替（取代 applyGroupRadio）", () => {
  const g = groups.map((x) => ({ ...x, choice_required: true }));
  let choices = recordGroupChoice({}, g, "gray-track", "pid");
  assert.deepEqual(applyGroupChoices(["huidu"], g, choices), ["pid"]);
  choices = recordGroupChoice(choices, g, "gray-track", "huidu");
  assert.deepEqual(applyGroupChoices(["xunji", "motor"], g, choices), ["motor", "huidu"]);
});

test("取消 = 从已选清单移除模块（不再有「再点已选 = 取消整组」的隐式行为）", () => {
  const g = groups.map((x) => ({ ...x, choice_required: true }));
  // 点过的选择仍在，但集合里原本没有该组成员 → 只把所选那一个加回来
  assert.deepEqual(applyGroupChoices([], g, { "gray-track": "pid" }), ["pid"]);
  // 未点过 + 集合里没有 → 原样
  assert.deepEqual(applyGroupChoices([], g, {}), []);
});

test("换选：未知组 id 不进 choices / 不影响集合", () => {
  assert.deepEqual(recordGroupChoice({}, groups, "no-such-group", "pid"), {});
  assert.deepEqual(applyGroupChoices(["motor"], groups, { "no-such-group": "pid" }), ["motor"]);
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
  const note = groupRequirementNote(groups, "pid", "PID 循迹，双平台", { "gray-track": "pid" });
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
  assert.match(src, /renderGroupCards\(groups, data\.modules, selectedSlugs, groupChoices\)/);
  assert.match(src, /selectedSlugs = autoAddDedup\(groups, selectedSlugs, data\.modules\)/);
  assert.match(src, /recordGroupChoice\(groupChoices, groups, input\.dataset\.groupId, input\.dataset\.groupSlug\)/);
  assert.match(src, /groupConflicts\(\(lastRecommend \|\| \{\}\)\.exclusive_groups \|\| \[\], selectedSlugs\)/);
});
