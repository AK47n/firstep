// genOverviewChipsHTML / genOverviewSummaryHTML / cardStepStatusHTML /
// hasWarnContent 纯函数单测（工单 gen-overview/01、02）：
// 生成页顶部就绪总览的 chips 渲染、摘要文案、卡片状态徽章与警告判定。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取：函数体内含 `} else {` / 箭头块时，naive 的 [\s\S]*?\n\}
// 会在第一个顶格 `}` 处截断，这里按花括号深度配平到真正的函数结尾
function extract(name) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        return new Function("return (" + html.slice(start, i + 1) + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const genOverviewChipsHTML = extract("genOverviewChipsHTML");
const genOverviewSummaryHTML = extract("genOverviewSummaryHTML");
const cardStepStatusHTML = extract("cardStepStatusHTML");
const hasWarnContent = extract("hasWarnContent");

const titles = [
  { n: 1, title: "赛题原文" },
  { n: 2, title: "赛题简介" },
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
