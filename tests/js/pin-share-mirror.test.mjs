// 同脚多角色 共享/冲突 判据的**跨语言对拍**（工单 cross-lang-mirror-c5a/02）。
//
// 后端 `pin_bindings._shared_groups` 与前端 `fx/generate.js` 的 `pinShareClass`
// 是同一条判据的两份实现（后端守 CLI / 脚本 / 旧页面直打端点 / 生成前门禁；
// 前端守即时反馈：角色行黄字与板图点脚菜单）。仓库先例是「跨语言镜像 + 守卫」
// （tests/test_group_choice_mirror.py ↔ 本目录的 group-choice 对拍）——两份必须
// 给出同一结论，改一侧忘了另一侧就红。
//
// fixture 出自 Python 侧的场景表（tests/test_pin_share_mirror.py），期望值由后端
// 判据现算；本文件只在 JS 侧复算并比对，**不自己写期望值**。只对账 kind
// （share / conflict / none）：原因文案前端自有，不进对拍。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { pinShareClass } from "../../src/contest_generator/static/js/fx/generate.js";

const fixture = JSON.parse(
  readFileSync(new URL("./pin-share-mirror.fixture.json", import.meta.url), "utf8")
);

/** 复算一个场景：每个脚调一次 pinShareClass，规范化成 [[pin, roleKey, kind]]。 */
function mirrorOf(c) {
  const board = { pins: fixture.boards[c.platform].pins };
  const rows = [];
  for (const [pin, roles] of Object.entries(c.roles_by_pin)) {
    const cls = pinShareClass(
      roles.map((r) => ({ key: r.key, slug: r.slug, decl: { type: r.type } })),
      pin,
      board,
      c.instances,
    );
    if (cls.kind === "none") continue;   // 后端也不报单角色组（不标注 = 不出现在结果里）
    for (const r of roles) rows.push([pin, r.key, cls.kind]);
  }
  return rows.sort((a, b) => (a.join("|") < b.join("|") ? -1 : 1));
}

test("镜像 fixture 在位、场景够多、板定义按平台备好", () => {
  assert.ok(Array.isArray(fixture.cases) && fixture.cases.length >= 10, "fixture 场景太少");
  for (const c of fixture.cases) {
    assert.ok(fixture.boards[c.platform], "缺平台板定义：" + c.platform);
  }
  // 三类结论都要有场景（只测 share 的镜像守不住冲突侧，反之亦然）
  const categories = new Set(fixture.cases.map((c) => c.category));
  assert.deepEqual([...categories].sort(), ["conflict", "none", "share"]);
});

for (const c of fixture.cases) {
  test("镜像：" + c.name, () => {
    assert.deepEqual(
      mirrorOf(c),
      c.expected,
      "前端 pinShareClass 与后端 _shared_groups 结论不一致（场景：" + c.name + "）",
    );
  });
}

test("镜像：场景表留着本轮修的 adc 共读同槽（回归守卫的立身之本）", () => {
  const drift = fixture.cases.find((c) => c.name.startsWith("adc 共读同槽："));
  assert.ok(drift, "fixture 里必须有 adc 共读同槽场景（前端 adc 分支的回归守卫）");
  assert.deepEqual(
    drift.expected.map((row) => row[2]),
    ["share", "share"],
    "后端的结论是 share；前端若判 conflict，上面的对拍用例会红",
  );
});
