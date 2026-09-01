// 分类标记（工单 topics-control-2023-2025/01）：筛选维度 / 卡片 chip /
// 编辑表单下拉 / payload 带出。直接 import fx/topic.js。
import test from "node:test";
import assert from "node:assert/strict";
import {
  topicFilterEntries, topicCardHTML, topicEditHTML, topicEditPayload,
  topicCategoryChip, topicCategoryOptionsHTML, topicCategoryFilterOptionsHTML,
} from "../../src/contest_generator/static/js/fx/topic.js";

const CATEGORIES = ["control", "other"];
const VOCAB = { "attitude-hold": "航向保持 / 姿态传感器" };
const ENTRIES = [
  { key: "2023E", year: "2023", problem_text: "运动目标控制题面", programs: [], hint_module_groups: [], category: "control" },
  { key: "2026A", year: "2026", problem_text: "电源题面", programs: [], hint_module_groups: [], category: "other" },
  { key: "2024H", year: "2024", problem_text: "巡线题面", programs: [], hint_module_groups: [] },
];

test("topicFilterEntries：分类维度精确过滤（空串 = 不过滤）", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "control" }).map((t) => t.key), ["2023E"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "other" }).map((t) => t.key), ["2026A"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "" }).map((t) => t.key), ["2023E", "2026A", "2024H"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, {}).map((t) => t.key), ["2023E", "2026A", "2024H"]);
});

test("topicFilterEntries：分类 × 关键字正交组合", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "control", q: "2023" }).map((t) => t.key), ["2023E"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "control", q: "电源" }).map((t) => t.key), []);
  assert.deepEqual(topicFilterEntries(ENTRIES, { category: "other", year: "2026" }).map((t) => t.key), ["2026A"]);
});

test("topicCategoryChip：control / other 显示中文徽标；空 = 不标注", () => {
  assert.ok(topicCategoryChip(ENTRIES[0]).includes("控制题"));
  assert.ok(topicCategoryChip(ENTRIES[1]).includes("其他"));
  assert.equal(topicCategoryChip(ENTRIES[2]), "");
});

test("topicCategoryChip：词表外值显示原值（无映射回退，不误标中文）", () => {
  const out = topicCategoryChip({ key: "2026X", category: "mystery" });
  assert.ok(out.includes("mystery"));
  assert.ok(!out.includes("控制题")); // 未知值不映射成已知标签
});

test("topicCardHTML：分类徽标渲染；未标记不渲染", () => {
  assert.ok(topicCardHTML(ENTRIES[0], {}).includes("控制题"));
  assert.ok(topicCardHTML(ENTRIES[1], {}).includes("其他"));
  assert.ok(!topicCardHTML(ENTRIES[2], {}).includes("控制题"));
});

test("topicCategoryOptionsHTML：（未标记）+ 词表选项 + 当前值选中", () => {
  const out = topicCategoryOptionsHTML(CATEGORIES, "other");
  assert.ok(out.includes('<option value="">（未标记）</option>'));
  assert.ok(out.includes('<option value="control">控制题</option>'));
  assert.ok(out.includes('<option value="other" selected>其他</option>'));
});

test("topicCategoryOptionsHTML：词表外当前值兜底选项（保存时后端拒绝）", () => {
  const out = topicCategoryOptionsHTML(CATEGORIES, "mystery");
  assert.ok(out.includes("mystery"));
  assert.ok(out.includes("词表外"));
});

test("topicEditHTML：分类下拉 = （未标记）+ 词表选项 + 当前值选中", () => {
  const out = topicEditHTML({ ...ENTRIES[0], category: "other" }, VOCAB, CATEGORIES);
  assert.ok(out.includes("topic-edit-category"));
  assert.ok(out.includes('<option value="">（未标记）</option>'));
  assert.ok(out.includes('<option value="control">控制题</option>'));
  assert.ok(out.includes('<option value="other" selected>其他</option>'));
});

test("topicEditHTML：词表外当前值兜底显示（不静默丢弃）", () => {
  const out = topicEditHTML({ ...ENTRIES[0], category: "mystery" }, VOCAB, CATEGORIES);
  assert.ok(out.includes("mystery"));
  assert.ok(out.includes("词表外"));
});

test("topicCategoryFilterOptionsHTML：筛选下拉 = 全部 + 词表值（中文标签）", () => {
  const out = topicCategoryFilterOptionsHTML(CATEGORIES);
  assert.ok(out.includes('<option value="">全部</option>'));
  assert.ok(out.includes('<option value="control">控制题</option>'));
  assert.ok(out.includes('<option value="other">其他</option>'));
  assert.equal(topicCategoryFilterOptionsHTML([]).includes("control"), false); // 词表空 = 只有全部
});

test("topicEditPayload：category 字段带出（下拉值）", () => {
  const payload = topicEditPayload({
    problem_text: "题面", programs: "", hint_module_groups: [], category: "control",
  });
  assert.equal(payload.category, "control");
});
