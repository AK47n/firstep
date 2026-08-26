import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
import {
  topicHasNotes, topicDanglingGroups, topicHealthText, topicCardHTML,
} from "../../src/contest_generator/static/js/fx/topic.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

test("卡片结构：key/year/preview/操作按钮齐全", () => {
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: "巡线小车" });
  assert.ok(out.includes('class="topic-card"'));
  assert.ok(out.includes('class="topic-key">2024H<'));
  assert.ok(out.includes('class="topic-year">2024<'));
  assert.ok(out.includes('class="topic-preview"'));
  assert.ok(out.includes("巡线小车"));
  assert.ok(out.includes('data-topic-use="2024H"'));
  assert.ok(out.includes('data-topic-del="2024H"'));
  assert.ok(out.includes("用此题生成"));
  assert.ok(out.includes("删除"));
});

test("题面预览截断：80 字 + 省略号，title 全文 200 字", () => {
  const long = "题".repeat(250);
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: long });
  const preview = out.match(/<div class="topic-preview"[^>]*>([^<]*)</)[1];
  assert.equal(preview.length, 81); // 80 字 + …
  assert.ok(preview.endsWith("…"));
  assert.ok(out.includes("title=\"" + "题".repeat(200) + "…"));
});

test("题面不足 200 字：title 显示全文无省略号，preview 仍截断 80", () => {
  const short = "题".repeat(150);
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: short });
  assert.ok(out.includes("title=\"" + short + "\""));
  const preview = out.match(/<div class="topic-preview"[^>]*>([^<]*)</)[1];
  assert.equal(preview.length, 81);
  assert.ok(preview.endsWith("…"));
});

test("特殊字符转义：key/year/题面中的 & < > \" '", () => {
  const out = topicCardHTML({ key: "A&B", year: "2024", problem_text: "a<b>c\"d'e" });
  assert.ok(out.includes("A&amp;B"));
  assert.ok(!out.includes("data-topic-use=\"A&B\"")); // 未转义会破坏属性
  assert.ok(out.includes("a&lt;b&gt;c&quot;d&#39;e"));
});

test("空字段兜底：key/year/problem_text 缺失不抛错", () => {
  const out = topicCardHTML({});
  assert.ok(out.includes('class="topic-key"></span>'));
  assert.ok(out.includes('class="topic-year"></span>'));
  assert.ok(out.includes('<div class="topic-preview" title=""></div>'));
});

test("HTML 已改用 #topic-grid 容器，无 tbody#topic-rows", () => {
  assert.ok(html.includes('<div id="topic-grid" class="topic-grid">'));
  assert.ok(!html.includes("topic-rows"));
  assert.ok(html.includes('grid.querySelectorAll("[data-topic-del]")'));
  assert.ok(html.includes('grid.querySelectorAll("[data-topic-use]")'));
});

// =================== 工单 topic-library-ui/03 扩展断言（追加进同文件） ===================
// 卡片扩展：元数据小行 / 健康 ⚠ / 图注 ✓ / 详情按钮（既有断言语义保持兼容）。

const VOCAB = { "attitude-hold": "航向保持 / 姿态传感器", "gray-track": "8 路灰度传感器驱动" };
const ENTRY_BAD = { key: "2026D", year: "2026", problem_text: "陆空协同无人机系统",
  programs: [], hint_module_groups: ["data-link"], original_pdf: "D题_陆空协同无人机系统.pdf",
  health: { original_pdf_missing: true, programs_missing: [], original_pdf_size: 0 } };
const ENTRY_OK = { key: "2024H", year: "2024", problem_text: "巡线小车 2024H 题面",
  programs: [], hint_module_groups: ["attitude-hold"],
  health: { original_pdf_missing: false, programs_missing: [], original_pdf_size: 10 } };
const ENTRY_NOTES = { key: "2026C", year: "2026", problem_text: "数字钥匙实验系统 如图1所示。\n\n[图1 标注：60cm]",
  programs: ["C:/2026C"], hint_module_groups: [],
  health: { original_pdf_missing: false, programs_missing: ["C:/2026C"], original_pdf_size: 1024 } };

test("扩展：元数据小行（题面字数 / 程序数）+ 详情按钮 + 健康 ⚠", () => {
  const out = topicCardHTML(ENTRY_BAD, VOCAB);
  assert.ok(out.includes('class="topic-card"'));
  assert.ok(out.includes('data-topic-view="2026D"')); // 详情按钮
  assert.ok(out.includes("数据问题")); // ⚠ title 含健康描述
  assert.ok(out.includes("9 字")); // 题面字数小行
  assert.ok(out.includes("程序 0")); // 程序数小行
});

test("扩展：健康条目不渲染 ⚠；无 vocab 降级（旧调用兼容）", () => {
  const healthy = topicCardHTML(ENTRY_OK, VOCAB);
  assert.ok(!healthy.includes("数据问题"));
  assert.ok(!healthy.includes("⚠"));
  const noVocab = topicCardHTML(ENTRY_OK); // 词表缺失 → 不判定
  assert.ok(!noVocab.includes("数据问题"));
});

test("扩展：图注 ✓ 徽章（题面含图注段）", () => {
  const out = topicCardHTML(ENTRY_NOTES, VOCAB);
  assert.ok(out.includes("图注 ✓"));
  assert.ok(out.includes("程序 1"));
});
