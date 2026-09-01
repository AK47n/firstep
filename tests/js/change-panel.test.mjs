// fx/change-panel.js 纯函数单测（工单 code-ide-flow/03 + code-ide-ai/08 泛化）：
// 「磁盘变更」面板条目渲染纯件——条目（新/变/消失 + 跳转 data + 置灰）+
// 计数摘要 + 行级 diff 区（details 折叠；hasLineDiffSource 决定显隐——任意文件，
// main.c 无路径特判）。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  changesPanelHTML,
  changeSummaryText,
} from "../../src/contest_generator/static/js/fx/change-panel.js";

const SAMPLE_ENTRIES = [
  { status: "added", path: "src/oled.c", mtime_ns: "100", size_bytes: 12 },
  { status: "modified", path: "main.c", mtime_ns: "200", size_bytes: 340, hasLineDiffSource: true,
    mainDiff: { stats: { additions: 3, deletions: 1, hunks: 1 },
      hunks: [{ line: 5, title: "填充 TODO「init motor」",
        lines: [{ kind: "del", text: "// TODO: init motor" }, { kind: "add", text: "motor_init();" }] }] } },
  { status: "removed", path: "old.c", mtime_ns: "", size_bytes: 0 },
];

test("changesPanelHTML：三类条目——状态徽章/跳转 data/消失置灰", () => {
  const html = changesPanelHTML(SAMPLE_ENTRIES);
  assert.match(html, /class="code-change-badge b-added"/);
  assert.match(html, /class="code-change-badge b-modified"/);
  assert.match(html, /class="code-change-badge b-removed"/);
  assert.match(html, /data-change-path="src\/oled\.c"/);
  assert.match(html, /data-change-path="main\.c"/);
  // removed 置灰不可点：span.code-change-item.disabled（非 button——事件层
  // 委托只认 button[data-change-path]，span 天然不可点）
  assert.match(html, /<span class="code-change-item disabled" data-change-path="old\.c" data-change-status="removed"/);
  assert.ok(!/<button[^>]*data-change-path="old\.c"/.test(html));
});

test("changesPanelHTML：转义（路径含 < > &）", () => {
  const html = changesPanelHTML([{ status: "added", path: "a<b&c.h", mtime_ns: "1", size_bytes: 2 }]);
  assert.match(html, /a&lt;b&amp;c\.h/);
  assert.ok(!html.includes("a<b&c.h"));
});

test("changesPanelHTML：hasLineDiffSource 条目带行级 diff 区（details 默认折叠 + stats 行）", () => {
  const html = changesPanelHTML(SAMPLE_ENTRIES);
  assert.match(html, /<details class="code-change-diff"><summary>/);
  assert.match(html, /行级改动（main\.c）/);
  assert.match(html, /diff-stats/);
  assert.match(html, /diff-hunk/);
  assert.match(html, /填充 TODO「init motor」/);
});

test("changesPanelHTML：非 main.c 文件同样带行级区（泛化——无路径特判）", () => {
  const app = changesPanelHTML([{ status: "modified", path: "src/app.c", mtime_ns: "5",
    size_bytes: 1, hasLineDiffSource: true, mainDiff: SAMPLE_ENTRIES[1].mainDiff }]);
  assert.match(app, /<details class="code-change-diff"><summary>/);
  assert.match(app, /行级改动（src\/app\.c）/);
});

test("changesPanelHTML：hasLineDiffSource 但无 mainDiff 数据 → 占位文案（路径泛化）；无 hasLineDiffSource → 无区", () => {
  const mc = changesPanelHTML([{ status: "modified", path: "main.c", mtime_ns: "5",
    size_bytes: 1, hasLineDiffSource: true }]);
  assert.match(mc, /main\.c 行级差异不可用/);
  assert.match(mc, /data-change-status="modified"/);
  const app = changesPanelHTML([{ status: "modified", path: "app.c", mtime_ns: "5", size_bytes: 1 }]);
  assert.ok(!app.includes("code-change-diff"));   // 无 hasLineDiffSource：无行级 diff 区
  const app2 = changesPanelHTML([{ status: "modified", path: "src/app.c", mtime_ns: "5",
    size_bytes: 1, hasLineDiffSource: true }]);
  assert.match(app2, /src\/app\.c 行级差异不可用/);   // 占位文案路径泛化
});

test("changeSummaryText：计数摘要（中文顿号联结 + 空 = 没有变更）", () => {
  assert.equal(changeSummaryText([]), "没有磁盘变更");
  assert.equal(changeSummaryText(SAMPLE_ENTRIES), "1 个新增 · 1 个修改 · 1 个消失");
  assert.equal(changeSummaryText([{ status: "added", path: "a.c" }]), "1 个新增");
});

test("changesPanelHTML：空数组 → 空串（空态由调用方展示）", () => {
  assert.equal(changesPanelHTML([]), "");
});
