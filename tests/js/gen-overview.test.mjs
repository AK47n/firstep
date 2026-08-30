// genOverviewChipsHTML / genOverviewSummaryHTML / cardStepStatusHTML /
// hasWarnContent 纯函数单测（工单 frontend-es-modules/07）：
// 生成页顶部就绪总览的 chips 渲染、摘要文案、卡片状态徽章与警告判定。
// 直接 import fx/overview.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  genOverviewChipsHTML, genOverviewSummaryHTML, cardStepStatusHTML,
  hasWarnContent,
} from "../../src/contest_generator/static/js/fx/overview.js";

const titles = [
  { n: 1, title: "赛题原文" },
  { n: 2, title: "赛题预读" },
  { n: 3, title: "目标平台" },
  { n: 4, title: "参考资料" },
  { n: 5, title: "AI 推荐" },
  { n: 6, title: "模块清单" },
  { n: 7, title: "引脚配置" },
  { n: 8, title: "main.c 骨架" },
  { n: 9, title: "输出并生成" },
  { n: 10, title: "修复中心" },
  { n: 11, title: "修订与深化" },
  { n: 12, title: "交接提示词" },
];

test("genOverviewChipsHTML 生成 chips：done 打勾、current 高亮、未完成显示数字", () => {
  const out = genOverviewChipsHTML(titles, [1, 6], 9);
  assert.ok(out.includes('data-step="1"'));
  assert.ok(out.includes('class="ov-chip done"'));
  assert.ok(out.includes('<span class="ov-dot">✓</span>'));
  assert.ok(out.includes('<span class="ov-label">赛题原文</span>'));
  // 未完成：数字 + 无 done 类
  assert.ok(out.includes('<button type="button" class="ov-chip" data-step="2"'));
  assert.ok(out.includes('<span class="ov-dot">2</span>'));
  // current 单独类
  assert.ok(out.includes('class="ov-chip current"'));
  assert.ok(!out.includes('class="ov-chip done current"'));
});

test("genOverviewChipsHTML 转义标题引号（label 与 title）", () => {
  const out = genOverviewChipsHTML([{ n: 7, title: '引脚配置"板图"' }], [], NaN);
  assert.ok(out.includes('title="引脚配置&quot;板图&quot;"'));
  assert.ok(out.includes('<span class="ov-label">引脚配置&quot;板图&quot;</span>'));
});

test("genOverviewSummaryHTML 摘要：已就绪计数 + 还差关键路径 + 建议软步骤", () => {
  const out = genOverviewSummaryHTML(
    [1, 3, 6],
    titles,
    [1, 3, 6, 9],
    [5, 8]
  );
  assert.ok(out.includes("已就绪 3/12"));
  assert.ok(out.includes("还差："));
  assert.ok(out.includes("输出并生成"));
  assert.ok(out.includes("建议顺带完成：AI 推荐、main.c 骨架"));
  assert.ok(out.includes("·"));  // 段间分隔符
});

test("genOverviewSummaryHTML 关键路径齐了：提示可生成、无还差", () => {
  const out = genOverviewSummaryHTML(
    [1, 3, 6, 9],
    titles,
    [1, 3, 6, 9],
    [5, 8]
  );
  assert.ok(out.includes("关键步骤齐了，可以点「生成工程」"));
  assert.ok(!out.includes("还差："));
});

test("genOverviewSummaryHTML 软建议全部完成时不再出现建议段", () => {
  const out = genOverviewSummaryHTML(
    [1, 3, 6, 9, 5, 8],
    titles,
    [1, 3, 6, 9],
    [5, 8]
  );
  assert.ok(!out.includes("建议顺带完成"));
});

test("genOverviewSummaryHTML 还差提示跟随导航 hint（缺省不渲染）", () => {
  // 宽屏：左侧 step-nav 可见，提示指向左侧步骤条
  const wide = genOverviewSummaryHTML([1], titles, [1, 3, 6, 9], [], "（点左侧步骤条直达）");
  assert.ok(wide.includes("（点左侧步骤条直达）"));
  // 窄屏：chips 在顶部
  const narrow = genOverviewSummaryHTML([1], titles, [1, 3, 6, 9], [], "（点上方步骤条直达）");
  assert.ok(narrow.includes("（点上方步骤条直达）"));
  // 缺省：不渲染任何括号提示（纯函数调用方未传时静默）
  const plain = genOverviewSummaryHTML([1], titles, [1, 3, 6, 9], []);
  assert.ok(!plain.includes("直达"));
});

test("cardStepStatusHTML 四态：done / warn / current / 无状态", () => {
  assert.ok(cardStepStatusHTML(true, false, false).includes('class="card-step-status done"'));
  assert.ok(cardStepStatusHTML(true, false, false).includes("✓ 已就绪"));
  assert.ok(cardStepStatusHTML(false, true, false).includes('class="card-step-status warn"'));
  assert.ok(cardStepStatusHTML(false, true, false).includes("⚠ 有警告"));
  assert.ok(cardStepStatusHTML(false, false, true).includes('class="card-step-status current"'));
  assert.ok(cardStepStatusHTML(false, false, true).includes("● 当前"));
  assert.equal(cardStepStatusHTML(false, false, false), "");
});

test("hasWarnContent：空 / null / 全 ok 盒不算警告，有非 ok 子元素才算", () => {
  assert.equal(hasWarnContent(null), false);
  assert.equal(hasWarnContent(undefined), false);
  assert.equal(hasWarnContent({ children: [] }), false);
  const okBox = { children: [{ classList: { contains: (c) => c === "ok" } }] };
  assert.equal(hasWarnContent(okBox), false);
  const mixed = {
    children: [
      { classList: { contains: (c) => c === "ok" } },
      { classList: { contains: (c) => c === "warn-box" } },
    ],
  };
  assert.equal(hasWarnContent(mixed), true);
  const plain = { children: [{ classList: null }] };
  assert.equal(hasWarnContent(plain), true);
});

test("genOverviewSummaryHTML 输出目录预警：传 dirWarn 追加 ⚠ 段，缺省不渲染（工单 07）", () => {
  const out = genOverviewSummaryHTML(
    [1, 3, 6, 9, 5, 8],
    titles,
    [1, 3, 6, 9],
    [5, 8],
    "",
    { title: "输出目录", reason: "桌面已有同名工程（生成时会把旧工程备份为 .bak 再覆盖；也可以先去删除旧工程）" }
  );
  assert.ok(out.includes('class="ov-missing ov-dir-warn"'), "缺 ov-dir-warn 段");
  assert.ok(out.includes("⚠ 输出目录：桌面已有同名工程"), "缺 ⚠ 标题前缀与原因");
  const plain = genOverviewSummaryHTML([1, 3, 6, 9, 5, 8], titles, [1, 3, 6, 9], [5, 8]);
  assert.ok(!plain.includes("ov-dir-warn"), "不传时不应渲染");
  assert.ok(!plain.includes("⚠"), "不传时摘要不应出现 ⚠");
});

test("genOverviewSummaryHTML 输出目录预警：第 9 步已就绪也照常显示（软警告与就绪无关）", () => {
  const out = genOverviewSummaryHTML(
    [1, 3, 6, 9],
    titles,
    [1, 3, 6, 9],
    [5, 8],
    "",
    { title: "输出目录", reason: "目录已存在且非空——生成会被拒绝；建议先清空目录或换个位置" }
  );
  assert.ok(out.includes("关键步骤齐了，可以点「生成工程」"), "就绪文案不应被预警替代");
  assert.ok(out.includes("⚠ 输出目录：目录已存在且非空"), "已就绪也应显示软预警");
});
