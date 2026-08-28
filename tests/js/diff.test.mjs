// diff.test.mjs — fx/diff.js 效果 diff 渲染纯函数（工单 diff-restyle/01）：
// 统计行 / 三种行类型（add/del/ctx）符号列与转义 / hunk 标题回退 / 占位文案 /
// entity 文案参数 / 桥导出。
import test from "node:test";
import assert from "node:assert/strict";
import {
  diffStatsLineHTML, mainDiffHTML,
} from "../../src/contest_generator/static/js/fx/diff.js";

const DIFF = {
  stats: { additions: 3, deletions: 2, hunks: 1 },
  hunks: [
    {
      title: "TODO：启动条件",
      line: 42,
      lines: [
        { kind: "ctx", text: "  case XUNJI_STOP:" },
        { kind: "del", text: "  if (gray != 0) && (lab_arrived)" },
        { kind: "add", text: "  if ((gray != 0) && (lap_count < 4))" },
        { kind: "add", text: "  xunji_state = XUNJI_FOLLOW;" },
      ],
    },
  ],
};

test("mainDiffHTML: 统计行含实体名与三类数字", () => {
  const out = mainDiffHTML(DIFF, "任务");
  assert.ok(out.includes("任务效果："));
  assert.ok(out.includes('class="diff-stats reason"'));
  assert.ok(out.includes('class="diff-count add">+3</span>'));
  assert.ok(out.includes('class="diff-count del">−2</span>'));
  assert.ok(out.includes("1 处改动"));
});

test("mainDiffHTML: hunk 折叠块 + 三种行类型 + 符号列", () => {
  const out = mainDiffHTML(DIFF, "深化");
  assert.ok(out.includes('class="diff-hunk"'));
  assert.ok(out.includes("<summary>TODO：启动条件</summary>"));
  assert.ok(out.includes('class="diff-body"'));
  assert.ok(out.includes('class="diff-line diff-ctx"'));
  assert.ok(out.includes('class="diff-line diff-del"'));
  assert.ok(out.includes('class="diff-line diff-add"'));
  assert.ok(out.includes('<span class="diff-gutter">+</span>'));
  assert.ok(out.includes('<span class="diff-gutter">−</span>'));
  assert.ok(out.includes('<span class="diff-gutter"></span>'));
});

test("mainDiffHTML: 行内容转义（防注入）", () => {
  const out = mainDiffHTML({
    stats: {}, hunks: [{ title: "h", lines: [{ kind: "add", text: '<script>alert(1)</script>' }] }],
  }, "深化");
  assert.ok(!out.includes("<script>alert(1)</script>"));
  assert.ok(out.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
});

test("mainDiffHTML: hunk 标题缺省回退「第 N 行附近」", () => {
  const out = mainDiffHTML({
    stats: {}, hunks: [{ line: 7, lines: [{ kind: "ctx", text: "x" }] }],
  }, "深化");
  assert.ok(out.includes("<summary>第 7 行附近</summary>"));
});

test("mainDiffHTML: null / undefined / 空 hunks → 占位或空串", () => {
  assert.equal(mainDiffHTML(null, "深化"),
    '<div class="muted" style="margin-top:8px">深化未改动 main.c（无差异）。</div>');
  assert.ok(mainDiffHTML(undefined, "深化") === "");
  assert.ok(mainDiffHTML({ stats: {}, hunks: [] }, "任务").includes("任务未改动 main.c（无差异）。"));
});

test("mainDiffHTML: entity 缺省 → 深化", () => {
  assert.ok(mainDiffHTML(DIFF).includes("深化效果："));
});

test("diffStatsLineHTML: 空 stats 兜底 0", () => {
  const out = diffStatsLineHTML({}, "深化");
  assert.ok(out.includes(">+0</span>"));
  assert.ok(out.includes(">−0</span>"));
  assert.ok(out.includes("0 处改动"));
});
