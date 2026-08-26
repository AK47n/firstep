// 母版报告判定行 / 归档行纯函数单测（前端 ES 模块化阶段 2 工单 04）：
// decisionItem / archiveItem 已迁 static/js/fx/master.js，直接 import 直测。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { decisionItem, archiveItem } from "../../src/contest_generator/static/js/fx/master.js";

test("decisionItem：keep 行 = 路径 + 理由 + 归档按钮（无来源下拉）", () => {
  const html = decisionItem({ path: "src/main.c", action: "keep", reason: "保留" }, ["a", "b"]);
  assert.match(html, /src\/main\.c/);
  assert.match(html, /（保留）/);
  assert.ok(!html.includes("<select"), "keep 行不应有来源选择");
  assert.match(html, /data-archive="src\/main\.c"/);
  assert.match(html, /<div class="reason">保留<\/div>/);
});

test("decisionItem：merge 行带来源工程下拉并选中 d.source", () => {
  const html = decisionItem(
    { path: "a.c", action: "merge", source: "proj-b", reason: "同文件" },
    ["proj-a", "proj-b"]
  );
  assert.match(html, /<select data-path="a\.c">/);
  assert.match(html, /value="proj-b" selected/);
  assert.match(html, /（合并[\s\S]*?）/);
});

test("archiveItem：归档行 = 路径 + 赛题编号输入 + 移除按钮 + 理由缺省文案", () => {
  const html = archiveItem({ path: "x.c", topic: "2026C", reason: "" });
  assert.match(html, /data-topic="x\.c"/);
  assert.match(html, /value="2026C"/);
  assert.match(html, /data-unarchive="x\.c"/);
  assert.match(html, /（无理由）/);
});
