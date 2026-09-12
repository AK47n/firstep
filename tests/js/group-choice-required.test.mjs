// 功能组「必须由用户显式选择」纯函数单测（工单 group-choice-required/01）：
// 组卡不再默认选中 AI 推荐件、未选组浮出「请选择」、用户点选即记账并重算集合、
// 未选组进拦截图文案（前端拦住生成 + 服务端 400 同口径）。
// 直接 import fx/module.js（沿用 group-cards.test.mjs 先例）；不碰 DOM / fetch。
// 运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  renderableGroupCards, groupChoiceRequired, groupMemberPick, pendingGroupChoices,
  applyGroupChoices, recordGroupChoice, clearGroupChoiceForSlug, pruneGroupChoices,
  renderGroupCards, groupRequirementNote, groupChoiceGapText,
} from "../../src/contest_generator/static/js/fx/module.js";

// 命中卡（AI 推荐了 pid，choice_required = 新载荷字段）
const hit = {
  id: "attitude-hold", label: "航向保持 / 姿态传感器", hint: false, choice_required: true,
  members: [
    { slug: "imu_uart", role: "UART 串口陀螺仪" },
    { slug: "jy61p", role: "软 I2C + 器件内卡尔曼融合" },
    { slug: "ml_mpu6050", role: "I2C + DMP 姿态解算" },
  ],
  recommended: ["imu_uart"], candidates: ["jy61p", "ml_mpu6050"], dropped: ["jy61p"],
};
const hintCard = {
  id: "gray-track", label: "8 路灰度传感器驱动", hint: true, choice_required: false,
  members: [{ slug: "huidu", role: "r" }, { slug: "pid", role: "r" }],
  recommended: [], candidates: ["huidu", "pid"], dropped: [],
};
const legacy = {   // 旧载荷：无 choice_required（历史缓存）
  id: "zigbee-rx", label: "Zigbee 无线链路", hint: false,
  members: [{ slug: "zigbee_link", role: "r" }, { slug: "zigbee_uart", role: "r" }],
  recommended: ["zigbee_link"], candidates: ["zigbee_uart"], dropped: [],
};
const single = {
  id: "lone", label: "单成员组", hint: false, choice_required: true,
  members: [{ slug: "only", role: "r" }], recommended: ["only"], candidates: [], dropped: [],
};
const modules = [{ slug: "imu_uart", reason: "串口陀螺仪直出 yaw" }];

test("未选：组卡不画选中态 + 标题挂「请选择」", () => {
  const html = renderGroupCards([hit], modules, ["imu_uart"], {});
  assert.doesNotMatch(html, /checked/, "未选时不得有任何 radio 选中");
  assert.match(html, /请选择/);
  assert.match(html, /needs-choice/);
  // AI 推荐徽标仍在（推荐信息不丢，只是不替用户选）
  assert.match(html, /AI 推荐/);
});

test("已选：选中态跟着用户的选择走（含换到非推荐成员）", () => {
  const html = renderGroupCards([hit], modules, ["imu_uart"], { "attitude-hold": "jy61p" });
  assert.equal((html.match(/checked/g) || []).length, 2, "checked 出现在 label 与 input 各一次");
  assert.match(html, /data-group-slug="jy61p"[\s\S]*checked|checked[\s\S]*data-group-slug="jy61p"/);
  assert.doesNotMatch(html, /needs-choice/);
  assert.doesNotMatch(html, /请选择/);
});

test("待选判据：命中卡算、hint 卡与旧载荷不算、单成员组不算", () => {
  assert.equal(groupChoiceRequired(hit), true);
  assert.equal(groupChoiceRequired(hintCard), false);
  assert.equal(groupChoiceRequired(legacy), false);
  assert.equal(groupChoiceRequired(single), false);
  const sel = ["imu_uart"];
  assert.deepEqual(pendingGroupChoices([hit, hintCard, legacy, single], {}, sel).map((g) => g.id),
    ["attitude-hold"]);
  assert.deepEqual(pendingGroupChoices([hit, hintCard, legacy], { "attitude-hold": "imu_uart" }, sel), []);
  // 越界 / 不存在的成员 = 没选（宁严勿松）
  assert.deepEqual(pendingGroupChoices([hit], { "attitude-hold": "motor" }, sel).map((g) => g.id),
    ["attitude-hold"]);
  assert.deepEqual(pendingGroupChoices([hit], { "unknown-group": "imu_uart" }, sel).map((g) => g.id),
    ["attitude-hold"]);
  // 组内一个成员都没进选中集（用户把模块删了 / hint 卡形态）→ 不拦（与后端条件②同口径）
  assert.deepEqual(pendingGroupChoices([hit], {}, ["pid"]), []);
  assert.deepEqual(pendingGroupChoices([hintCard], {}, ["pid"]).map((g) => g.id), []);
});

test("点选即记账：recordGroupChoice 幂等、组外成员不认", () => {
  const first = recordGroupChoice({}, [hit], "attitude-hold", "jy61p");
  assert.deepEqual(first, { "attitude-hold": "jy61p" });
  assert.deepEqual(recordGroupChoice(first, [hit], "attitude-hold", "jy61p"), first, "重复点同一个 = no-op");
  assert.deepEqual(recordGroupChoice(first, [hit], "attitude-hold", "motor"), first, "组外成员不记");
  assert.deepEqual(recordGroupChoice(first, [hit], "no-such-group", "imu_uart"), first, "未知组不记");
});

test("用户选择重算集合：幂等 / 换选顶替 / 未点过不动作 / hint 卡点了也生效", () => {
  const groups = [hit, hintCard];
  const before = ["pid", "imu_uart"];
  assert.deepEqual(applyGroupChoices(before, groups, { "attitude-hold": "imu_uart" }), before,
    "已点过推荐件 = 集合不变");
  assert.deepEqual(applyGroupChoices(before, groups, { "attitude-hold": "jy61p" }),
    ["pid", "jy61p"], "换选 = 同组旧成员被顶替");
  assert.deepEqual(applyGroupChoices(before, groups, {}), before,
    "未点过的命中卡保持调用方集合（AI 收敛结果仍在，界面不显示为已选）");
  assert.deepEqual(applyGroupChoices(["pid"], groups, { "attitude-hold": "jy61p" }), ["pid", "jy61p"]);
  // hint 卡（AI 未推荐、题面疑似需要）：点组内**快照里已有**的成员 = 换选（顶替同组另一个）
  assert.deepEqual(applyGroupChoices(["pid"], [hintCard], { "gray-track": "huidu" }), ["huidu"],
    "点了 huidu：快照里同组的 pid 被顶替");
  // 点组内**快照里没有**的成员 = 只新增，不动别的
  assert.deepEqual(applyGroupChoices(["motor"], [hintCard], { "gray-track": "huidu" }), ["motor", "huidu"]);
  assert.deepEqual(applyGroupChoices(["motor"], [hit], { "attitude-hold": "jy61p" }), ["motor", "jy61p"],
    "组内原本一件都没选（AI 那件被用户删了）→ 只加不减");
});

test("pruneGroupChoices：换题 / 库变更后旧选择只在仍成立时保留", () => {
  assert.deepEqual(pruneGroupChoices([hit], { "attitude-hold": "jy61p" }), { "attitude-hold": "jy61p" });
  assert.deepEqual(pruneGroupChoices([hit], { "attitude-hold": "motor" }), {}, "成员已不在组内 = 丢弃");
  assert.deepEqual(pruneGroupChoices([hintCard], { "attitude-hold": "jy61p" }), {}, "组已不在载荷 = 丢弃");
});

test("需求句灰注：未选写「请选择」；换选后写「已由 <组> 的 <选中件> 替代」", () => {
  const pending = groupRequirementNote([hit], "imu_uart", "串口陀螺仪直出 yaw", {});
  assert.match(pending, /请选择/);
  assert.doesNotMatch(pending, /串口陀螺仪直出 yaw/);
  // 用户点了推荐件本身 → 照旧显示理由
  const chosen = groupRequirementNote([hit], "imu_uart", "串口陀螺仪直出 yaw", { "attitude-hold": "imu_uart" });
  assert.match(chosen, /串口陀螺仪直出 yaw/);
  assert.doesNotMatch(chosen, /请选择/);
  // 用户换选了同组另一个成员 → 别让需求句挂着一个已作废的模块名（照实说被谁替代）
  const swapped = groupRequirementNote([hit], "imu_uart", "串口陀螺仪直出 yaw", { "attitude-hold": "jy61p" });
  assert.match(swapped, /已由『航向保持 \/ 姿态传感器』的 jy61p 替代/);
  assert.doesNotMatch(swapped, /请选择/);
  assert.equal(groupRequirementNote([hit], "motor", "x", {}), null, "非组模块仍走 chip");
});

test("拦截图文案：带上组名，全选齐 = 空串（可以生成）", () => {
  const sel = ["imu_uart"];
  const text = groupChoiceGapText([hit, hintCard], {}, sel);
  assert.match(text, /航向保持 \/ 姿态传感器/);
  assert.match(text, /还需要你选择一项/);
  assert.equal(groupChoiceGapText([hit, hintCard], { "attitude-hold": "imu_uart" }, sel), "");
  assert.equal(groupChoiceGapText([], {}, []), "");
  assert.equal(groupChoiceGapText([hit], {}, ["pid"]), "", "组没进选中集 = 不拦（与后端同口径）");
});

test("renderableGroupCards：单成员组不出卡（与后端同判据）", () => {
  assert.deepEqual(renderableGroupCards([hit, single]).map((g) => g.id), ["attitude-hold"]);
  assert.deepEqual(renderableGroupCards(undefined), []);
});
