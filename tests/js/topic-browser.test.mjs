// 赛题库浏览区纯函数组（工单 frontend-es-modules/04）：过滤 / 排序 / 统计 /
// 组词表派生 / hint 悬空判定 / 图注判定 / 健康描述 / 卡片扩展渲染。
// 直接 import fx/topic.js（不再字符串提取）；只测外部行为，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  topicHasNotes, topicGroupVocabulary, topicDanglingGroups, topicHealthText,
  topicFilterEntries, topicSortEntries, topicStats, topicStatsText,
  topicChipRowHTML, topicCardHTML,
} from "../../src/contest_generator/static/js/fx/topic.js";

// 测试母本：两条健康 / 一条带图注 / 一条 hint 悬空
const ENTRIES = [
  { key: "2024H", year: "2024", problem_text: "巡线小车 2024H 题面", programs: [], hint_module_groups: ["attitude-hold"],
    health: { original_pdf_missing: false, programs_missing: [], original_pdf_size: 300 } },
  { key: "2026C", year: "2026", problem_text: "数字钥匙实验系统 如图1所示。\n\n[图1 标注：60cm]", programs: ["C:/2026C"], hint_module_groups: [],
    health: { original_pdf_missing: false, programs_missing: ["C:/2026C"], original_pdf_size: 1024 } },
  { key: "2026D", year: "2026", problem_text: "陆空协同无人机系统", programs: [], hint_module_groups: ["data-link"],
    original_pdf: "D题_陆空协同无人机系统.pdf",
    health: { original_pdf_missing: true, programs_missing: [], original_pdf_size: 0 } },
];
const VOCAB = { "attitude-hold": "航向保持 / 姿态传感器", "gray-track": "8 路灰度传感器驱动" };

test("topicFilterEntries：关键字命中 key / 年份 / 题面全文，大小写不敏感", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "2024" }).map((t) => t.key), ["2024H"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "无人机" }).map((t) => t.key), ["2026D"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "数字钥匙" }).map((t) => t.key), ["2026C"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "2026c" }).map((t) => t.key), ["2026C"]); // 大小写不敏感
  assert.equal(topicFilterEntries(ENTRIES, { q: "不存在的词" }).length, 0);
  assert.equal(topicFilterEntries(ENTRIES, {}).length, 3); // 空条件 = 全量
});

test("topicFilterEntries：年份维度精确过滤", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { year: "2026" }).map((t) => t.key), ["2026C", "2026D"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { year: "" }).map((t) => t.key), ["2024H", "2026C", "2026D"]);
});

test("topicFilterEntries：健康维度只看有问题条目（三类任一）", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { health: true, groupIds: Object.keys(VOCAB) }).map((t) => t.key),
    ["2026C", "2026D"]); // 程序悬空 + PDF 缺失 + hint 悬空
});

test("topicFilterEntries：关键字 × 年份 × 健康正交组合", () => {
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "2026", health: true, groupIds: Object.keys(VOCAB) }).map((t) => t.key),
    ["2026C", "2026D"]);
  assert.deepEqual(topicFilterEntries(ENTRIES, { q: "无人机", health: true, groupIds: Object.keys(VOCAB) }).map((t) => t.key),
    ["2026D"]);
});

test("topicSortEntries：编号升序/降序 + 题面字数排序", () => {
  assert.deepEqual(topicSortEntries(ENTRIES, { by: "key", dir: "asc" }).map((t) => t.key),
    ["2024H", "2026C", "2026D"]);
  assert.deepEqual(topicSortEntries(ENTRIES, { by: "key", dir: "desc" }).map((t) => t.key),
    ["2026D", "2026C", "2024H"]);
  assert.deepEqual(topicSortEntries(ENTRIES, { by: "chars", dir: "asc" }).map((t) => t.key),
    ["2026D", "2024H", "2026C"]); // 11 < 18 < 34 字（长度按 UTF-16 码元）
});

test("topicSortEntries：稳定排序，同键保序（不改原数组）", () => {
  const dup = [
    { key: "2026C", year: "2026", problem_text: "a", programs: [], hint_module_groups: [], health: {} },
    { key: "2026C", year: "2026", problem_text: "a", programs: [], hint_module_groups: [], health: {} },
    { key: "2024H", year: "2024", problem_text: "a", programs: [], hint_module_groups: [], health: {} },
  ];
  const out = topicSortEntries(dup, { by: "key", dir: "asc" });
  assert.equal(out[0].key, "2024H");
  assert.equal(out[1].key, "2026C");
  assert.equal(out[2].key, "2026C");
  assert.equal(dup[0].key, "2026C"); // 原数组不动
});

test("topicStats：总数 / 含程序 / 含图注 / 题面合计字数 / 问题条目数", () => {
  const stats = topicStats(ENTRIES, Object.keys(VOCAB));
  assert.equal(stats.total, 3);
  assert.equal(stats.withPrograms, 1);
  assert.equal(stats.withNotes, 1);
  assert.equal(stats.totalChars,
    ENTRIES.reduce((sum, t) => sum + String(t.problem_text || "").length, 0));
  assert.equal(stats.issues, 2); // 程序悬空 + PDF 缺失 + hint 悬空 → 2 条有问题
});

test("topicStatsText：统计条文案子串", () => {
  const text = topicStatsText({ total: 15, withPrograms: 3, withNotes: 8, totalChars: 12345, issues: 2 });
  assert.ok(text.includes("共 15 题"));
  assert.ok(text.includes("含附带程序 3"));
  assert.ok(text.includes("含图注 8"));
  assert.ok(text.includes("题面合计"));
  assert.ok(text.includes("12.3K")); // 12345 → 12.3K 字
});

test("topicGroupVocabulary：/api/modules → 组 id→label 唯一表（保序）", () => {
  const vocab = topicGroupVocabulary([
    { slug: "huidu", exclusive_group: { id: "gray-track", label: "8 路灰度传感器驱动" } },
    { slug: "pid", exclusive_group: { id: "gray-track", label: "8 路灰度传感器驱动" } },
    { slug: "imu_uart", exclusive_group: { id: "attitude-hold", label: "航向保持 / 姿态传感器" } },
    { slug: "delay", exclusive_group: null },
  ]);
  assert.deepEqual(Object.keys(vocab), ["gray-track", "attitude-hold"]); // 去重保序
  assert.equal(vocab["gray-track"], "8 路灰度传感器驱动");
  assert.equal(vocab["attitude-hold"], "航向保持 / 姿态传感器");
});

test("topicGroupVocabulary：模块库空 / 全无组 = 空词表", () => {
  assert.deepEqual(topicGroupVocabulary([]), {});
  assert.deepEqual(topicGroupVocabulary([{ slug: "x", exclusive_group: null }]), {});
});

test("topicDanglingGroups：命中词表不悬空、词表外列出、词表空降级", () => {
  assert.deepEqual(topicDanglingGroups(ENTRIES[0], Object.keys(VOCAB)), []);  // attitude-hold 命中
  assert.deepEqual(topicDanglingGroups(ENTRIES[2], Object.keys(VOCAB)), ["data-link"]); // 词表外
  assert.deepEqual(topicDanglingGroups(ENTRIES[2], []), []); // 词表空 = 降级不判定
  assert.deepEqual(topicDanglingGroups({}, Object.keys(VOCAB)), []); // 无 hint = 空
});

test("topicHasNotes：示意图段 / 图N 标注段（含冒号形态）", () => {
  assert.equal(topicHasNotes("系统如图1所示。\n\n[示意图1：布局]"), true);
  assert.equal(topicHasNotes("系统如图1所示。\n\n[图1 标注]\n60cm"), true);
  assert.equal(topicHasNotes("系统如图1所示。\n\n[图1 标注：红实线走向]"), true);
  assert.equal(topicHasNotes("巡线小车题面"), false);
  assert.equal(topicHasNotes(""), false);
});

test("topicHealthText：三类健康描述 + 健康条目空数组", () => {
  const desc = topicHealthText(ENTRIES[2], VOCAB);
  assert.deepEqual(desc, [
    "原 PDF 缺失（D题_陆空协同无人机系统.pdf 不在条目目录）",
    "功能组 data-link 库内无此组（推荐链路会忽略）",
  ]);
  assert.deepEqual(topicHealthText(ENTRIES[1], VOCAB), ["附带程序目录不存在：C:/2026C"]);
  assert.deepEqual(topicHealthText(ENTRIES[0], VOCAB), []);
});

// topicCardHTML 扩展断言在 topic-cards.test.mjs（spec 测试决策：卡片扩展追加进原文件）

test("topicChipRowHTML：年份 chips 渲染（全部 + 计数 + on 态）", () => {
  const out = topicChipRowHTML([
    { value: "", label: "全部", count: 15 },
    { value: "2026", label: "2026", count: 8 },
  ], "2026");
  assert.ok(out.includes('class="lib-chip" data-topic-chip=""'));
  assert.ok(out.includes('class="lib-chip on" data-topic-chip="2026"'));
  assert.ok(out.includes("全部（15）"));
  assert.ok(out.includes("2026（8）"));
});
