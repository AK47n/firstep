// 功能组「未选」判据的**跨语言镜像**守卫（工单 group-choice-required/01 评审整改）。
//
// 后端 selection.missing_group_choices 与前端 pendingGroupChoices 是同一条判据的两份实现
// （后端守 CLI / 脚本 / 旧页面直打端点；前端守即时反馈：点选、就绪检查单、拦截文案）。
// 仓库先例是「跨语言镜像 + 守卫测试」（tests/test_library_invariants.py:619）——两份必须
// 给出同一结论，改一侧忘了另一侧就红。
//
// fixture 出自 Python 侧的场景表（tests/test_group_choice_mirror.py），期望值由后端判据
// 现算；本文件只在 JS 侧复算并比对，**不自己写期望值**。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { pendingGroupChoices } from "../../src/contest_generator/static/js/fx/module.js";

const fixture = JSON.parse(
  readFileSync(new URL("./group-choice-mirror.fixture.json", import.meta.url), "utf8")
);

test("镜像 fixture 在位且有场景", () => {
  assert.ok(Array.isArray(fixture.cases) && fixture.cases.length >= 10, "fixture 场景太少");
});

for (const c of fixture.cases) {
  test(`镜像：${c.name}`, () => {
    const got = pendingGroupChoices(c.groups, c.choices, c.selected).map((g) => g.id);
    assert.deepEqual(got, c.expected_pending,
      `前端 pendingGroupChoices 与后端 missing_group_choices 结论不一致（场景：${c.name}）`);
  });
}
