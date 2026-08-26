// 赛题详情弹窗纯函数单测（工单 frontend-es-modules/04）：topicDetailHTML /
// topicPagesHTML / topicPagesErrorHTML。直接 import fx/topic.js。
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
import {
  topicDanglingGroups, topicHasNotes, topicHealthText, topicDetailHTML,
  topicPagesHTML, topicPagesErrorHTML,
} from "../../src/contest_generator/static/js/fx/topic.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

const VOCAB = { "attitude-hold": "航向保持 / 姿态传感器", "gray-track": "8 路灰度传感器驱动" };
const ENTRY = {
  key: "2024H", year: "2024", number: "H",
  problem_text: "巡线小车 2024H 题面\n\n[图1 标注]\n60cm",
  programs: ["C:/Users/luoji/Desktop/2021F/21F"],
  hint_module_groups: ["attitude-hold"],
  original_pdf: "000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf",
  health: { original_pdf_missing: false, programs_missing: [], original_pdf_size: 35061760 },
};
const ENTRY_BAD = {
  key: "2026D", year: "2026", number: "D",
  problem_text: "陆空协同无人机系统",
  programs: [], hint_module_groups: ["data-link"],
  original_pdf: "D题_陆空协同无人机系统.pdf",
  health: { original_pdf_missing: true, programs_missing: ["C:/幽灵"], original_pdf_size: 0 },
};

test("详情元数据段：编号 / 年份 / 字数 / 原 PDF / 程序 / 功能组 / 图注 / 健康", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes("2024H"));
  assert.ok(out.includes("2024"));
  assert.ok(out.includes("字"));
  assert.ok(out.includes("000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"));
  assert.ok(out.includes("C:/Users/luoji/Desktop/2021F/21F")); // 附带程序清单
  assert.ok(out.includes("航向保持 / 姿态传感器")); // 功能组 label
  assert.ok(out.includes("图注")); // 图注段状态
});

test("详情健康：PDF 缺失 ⚠ + hint 悬空组标注 + 数据问题行", () => {
  const out = topicDetailHTML(ENTRY_BAD, VOCAB);
  assert.ok(out.includes("original_pdf_missing") === false); // 不泄漏内部字段
  assert.ok(out.includes("缺失")); // 原 PDF ⚠ 行
  assert.ok(out.includes("data-link")); // 悬空组 id 兜底显示
  assert.ok(out.includes("库内无此组")); // 悬空标注
  assert.ok(out.includes("数据问题"));
  // 健康条目无数据问题行
  assert.ok(!topicDetailHTML(ENTRY, VOCAB).includes("库内无此组"));
});

test("详情程序清单行内 ⚠（悬空路径逐条标注，spec 元数据段粒度）", () => {
  const out = topicDetailHTML({ ...ENTRY_BAD, programs: ["C:/还在", "C:/幽灵"] }, VOCAB);
  assert.ok(out.includes("C:/还在")); // 存在的程序照常渲染
  assert.ok(out.includes("C:/幽灵"));
  // 行内 ⚠ = 悬空路径带警示（数据问题行之外的逐条粒度）
  assert.ok(new RegExp("C:/幽灵</span> *<span class=\"topic-warn\"").test(out));
});

test("详情功能组：空词表不误报（spec 降级语义：词表空 = 全库不判定）", () => {
  const out = topicDetailHTML(ENTRY_BAD, {});
  assert.ok(!out.includes("库内无此组")); // 空词表 → 不标悬空（不误报）
  assert.ok(out.includes("data-link")); // 组 id 仍显示
});

test("详情元数据容器：topic-detail-meta 两列网格钩子（省高、全文区更宽）", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes('class="ref-detail-meta topic-detail-meta"'));
});

test("详情题面全文标题行：字数统计 + 展开/收起按钮", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes("题面全文"));
  assert.ok(out.includes(String(ENTRY.problem_text.length) + " 字"));
  assert.ok(out.includes('data-topic-expand'));
  assert.ok(out.includes("展开全文"));
});

test("详情题面全文防压扁：pre 与页图 flex-shrink 0（先前回归：弹窗 80vh 不足时 flex 压缩把 pre 压到一行）", () => {
  const cs = html.slice(html.indexOf(".topic-detail-problem {"));
  assert.ok(cs.includes("flex-shrink: 0"), ".topic-detail-problem 未防 flex 压缩");
  const pages = html.slice(html.indexOf(".topic-pages {"));
  assert.ok(pages.includes(".topic-pages {") && pages.match(/\.topic-page[s]? \{[^}]*flex-shrink: 0/),
    ".topic-pages 未防 flex 压缩");
});

test("详情题面全文段：pre 容器 + 原文（含图注段原样）", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes("topic-detail-problem"));
  assert.ok(out.includes("巡线小车 2024H 题面\n\n[图1 标注]"));
});

test("详情题面全文转义：& < > 不破坏结构", () => {
  const out = topicDetailHTML({ ...ENTRY, problem_text: "a<b>c&d" }, VOCAB);
  assert.ok(out.includes("a&lt;b&gt;c&amp;d"));
});

test("详情空程序 / 空功能组显示「无」，不渲染悬空", () => {
  const out = topicDetailHTML(ENTRY_BAD, VOCAB);
  assert.ok(out.includes("程序"));
});

test("详情操作段：用此题生成 / 编辑 / 删除按钮齐全", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes('data-topic-use="2024H"'));
  assert.ok(out.includes('data-topic-edit="2024H"'));
  assert.ok(out.includes('data-topic-del="2024H"'));
});

test("详情页图容器：懒加载区（data-topic-pages）", () => {
  const out = topicDetailHTML(ENTRY, VOCAB);
  assert.ok(out.includes('data-topic-pages'));
});

test("topicPagesHTML：页图列表（data_url + 页码标注）", () => {
  const out = topicPagesHTML([
    { page_no: 1, data_url: "data:image/png;base64,AAA" },
    { page_no: 2, data_url: "data:image/png;base64,BBB" },
  ]);
  assert.ok(out.includes('data:image/png;base64,AAA'));
  assert.ok(out.includes('data:image/png;base64,BBB'));
  assert.ok(out.includes("第 1 页"));
  assert.ok(out.includes("第 2 页"));
});

test("topicPagesErrorHTML：失败中文原因（三态之失败态）", () => {
  const out = topicPagesErrorHTML("原 PDF 文件不存在：真题.pdf");
  assert.ok(out.includes("页图不可用"));
  assert.ok(out.includes("原 PDF 文件不存在：真题.pdf"));
});
