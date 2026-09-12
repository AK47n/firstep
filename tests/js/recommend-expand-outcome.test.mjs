// 展开收尾决策单测（工单 09）：`/api/selection/expand` 三种结局的后续动作。
//
// 背景：原实现把「结果被作废」（令牌 / 快照拦下）与「请求失败」合并成 `!ok` 一起
// 重跑，于是失败 → 立刻同参数重打 → 再失败，实测恒 500 时打出 ~10 次/秒，
// 且按钮永久禁用、报错被自己清空。本测试把三条分支钉死：
//   discarded → 必须用当前选择集重跑（工单 07 的收敛口径，不许回退）
//   failed    → 绝不重跑（否则自激），且必须 keepError（原因留在界面上）
//   applied   → 只有在途期间被触发过（pending）才补跑一次
// 运行：node --test tests/js/recommend-expand-outcome.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { expandOutcomeDecision } from "../../src/contest_generator/static/js/fx/recommend.js";

const CTX = { pending: false, platform: "stm32", count: 3 };

test("applied：无 pending 不重跑，不报错", () => {
  const d = expandOutcomeDecision({ status: "applied" }, CTX);
  assert.equal(d.retry, false);
  assert.equal(d.keepError, false);
});

test("applied + pending：补跑一次（在途期间被触发过 = 排队语义）", () => {
  const d = expandOutcomeDecision({ status: "applied" }, { ...CTX, pending: true });
  assert.equal(d.retry, true);
  assert.equal(d.clearPending, true);
});

test("discarded：必须用当前选择集重跑（工单 07 收敛口径不许回退）", () => {
  const d = expandOutcomeDecision({ status: "discarded" }, CTX);
  assert.equal(d.retry, true, "结果被作废却不重跑 → 界面会停在「未展开依赖」");
  assert.equal(d.keepError, false);
});

test("failed：**绝不重跑**（同参数立刻重打 = 自激；工单 09 的核心判据）", () => {
  for (const pending of [false, true]) {
    const d = expandOutcomeDecision({ status: "failed", message: "内部错误" },
      { ...CTX, pending });
    assert.equal(d.retry, false, `failed（pending=${pending}）重跑了 → 失败即自激打后台`);
    assert.equal(d.keepError, true, "failed 必须 keepError：原因要留在界面上");
    assert.equal(d.clearPending, true, "failed 必须清掉挂起意图，否则下次点击行为不可预期");
  }
});

test("failed：看不到状态字段的旧形状（无 status）按 applied 处理，不误报错", () => {
  const d = expandOutcomeDecision({}, CTX);
  assert.equal(d.retry, false);
  assert.equal(d.keepError, false);
});

test("缺平台 / 空选择集：重跑没有意义（重跑只会立刻撞回前置检查）", () => {
  assert.equal(expandOutcomeDecision({ status: "discarded" }, { ...CTX, platform: "" }).retry, false);
  assert.equal(expandOutcomeDecision({ status: "discarded" }, { ...CTX, count: 0 }).retry, false);
  assert.equal(expandOutcomeDecision({ status: "applied" }, { ...CTX, pending: true, count: 0 }).retry, false);
});

test("结构守卫：ui 层不得再自带重跑判据（单一来源在 fx/recommend.js）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
    "utf8",
  );
  assert.match(ui, /expandOutcomeDecision\(/, "ui 层没有用 fx 层的收尾决策 = 判据漂了");
  // 原实现的自激源头：`!ok` 与 pending 合并成立即重跑
  assert.ok(!/\(\s*expandPending\s*\|\|\s*!ok\s*\)/.test(ui),
    "ui 层又出现「pending || !ok」合并重跑 —— failed 会被一起重跑（工单 09 的自激根因）");
});
