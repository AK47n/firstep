// fx/code-tree-ops.js 纯函数单测（工单 code-tree-ops/02）：名称校验 /
// 受影响判定 / 重命名映射 / 目录判定 / 标题与文案 / 输入框 HTML。
// 直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  treeNameValidate,
  treeOpAffected,
  treeRenamedPath,
  treeOpIsDir,
  treeOpTitle,
  createPromptMessage,
  renamePromptMessage,
  treeOpConfirmMessage,
  treeNamePromptHTML,
  CODE_TREE_NAME_ILLEGAL,
  CODE_TREE_NAME_MAX,
} from "../../src/contest_generator/static/js/fx/code-tree-ops.js";

test("treeNameValidate：合法名（含中文 / 点开头文件）", () => {
  assert.deepEqual(treeNameValidate("sensor.c"), { ok: true, msg: "" });
  assert.deepEqual(treeNameValidate("新驱动_1.h"), { ok: true, msg: "" });
  assert.deepEqual(treeNameValidate(".gitignore"), { ok: true, msg: "" });
  assert.deepEqual(treeNameValidate("a.b.c"), { ok: true, msg: "" });
});

test("treeNameValidate：空 / 纯空白 / 首尾空白", () => {
  assert.equal(treeNameValidate("").ok, false);
  assert.equal(treeNameValidate("   ").ok, false);
  assert.equal(treeNameValidate(" a.c").ok, false);
  assert.equal(treeNameValidate("a.c ").ok, false);
  assert.match(treeNameValidate("").msg, /不能为空/);
});

test("treeNameValidate：超长 / . 与 .. / 非法字符全拒绝", () => {
  assert.equal(treeNameValidate("x".repeat(CODE_TREE_NAME_MAX)).ok, true);
  assert.equal(treeNameValidate("x".repeat(CODE_TREE_NAME_MAX + 1)).ok, false);
  assert.equal(treeNameValidate(".").ok, false);
  assert.equal(treeNameValidate("..").ok, false);
  for (const ch of [...CODE_TREE_NAME_ILLEGAL]) {
    const v = treeNameValidate("a" + ch + "b");
    assert.equal(v.ok, false, "应拒绝 " + JSON.stringify(ch));
  }
  assert.match(treeNameValidate("a/b").msg, /非法字符/);
});

test("treeOpAffected：文件精确相等；目录前缀（自身 + 任意子路径）", () => {
  assert.equal(treeOpAffected("main.c", "main.c", false), true);
  assert.equal(treeOpAffected("other.c", "main.c", false), false);
  assert.equal(treeOpAffected("src/app.c", "src", true), true);
  assert.equal(treeOpAffected("src", "src", true), true);
  assert.equal(treeOpAffected("src2/app.c", "src", true), false);  // 前缀必须带 /，防 srcx 误伤
  assert.equal(treeOpAffected("app.c", "src", true), false);
  assert.equal(treeOpAffected("", "main.c", false), false);
});

test("treeRenamedPath：精确替换 / 目录前缀替换 / 未命中原样", () => {
  assert.equal(treeRenamedPath("main.c", "main.c", "app.c"), "app.c");
  assert.equal(treeRenamedPath("src/app.c", "src", "drivers"), "drivers/app.c");
  assert.equal(treeRenamedPath("src", "src", "drivers"), "drivers");
  assert.equal(treeRenamedPath("src2/app.c", "src", "drivers"), "src2/app.c");
  assert.equal(treeRenamedPath("readme.md", "main.c", "app.c"), "readme.md");
});

test("treeOpIsDir：清单 is_dir 条目优先；无条目时前缀兜底", () => {
  const files = [
    { path: "main.c", size_bytes: 1 },
    { path: "src", is_dir: true },
    { path: "src/app.h", size_bytes: 1 },
  ];
  assert.equal(treeOpIsDir("src", files), true);       // 显式 is_dir
  assert.equal(treeOpIsDir("main.c", files), false);   // 显式文件
  assert.equal(treeOpIsDir("include", files), false);  // 不在清单
  const legacy = [{ path: "src/app.h", size_bytes: 1 }];
  assert.equal(treeOpIsDir("src", legacy), true);      // 前缀兜底（旧清单无 is_dir）
  assert.equal(treeOpIsDir("app.h", legacy), false);
});

test("treeOpTitle：四种动作标题", () => {
  assert.equal(treeOpTitle("create-file"), "新建文件");
  assert.equal(treeOpTitle("create-dir"), "新建文件夹");
  assert.equal(treeOpTitle("rename"), "重命名");
  assert.equal(treeOpTitle("delete"), "删除确认");
  assert.equal(treeOpTitle("nope"), "树操作");
});

test("createPromptMessage / renamePromptMessage / treeOpConfirmMessage", () => {
  assert.ok(createPromptMessage("file", "").includes("工程根目录"));
  assert.ok(createPromptMessage("dir", "src").includes("src"));
  assert.ok(renamePromptMessage("main.c").includes("main.c"));
  const del = treeOpConfirmMessage("delete", "old.c", false);
  assert.ok(del.includes("old.c"));
  assert.ok(del.includes("不可撤销"));
  const delDir = treeOpConfirmMessage("delete", "empty", true);
  assert.ok(delDir.includes("仅空目录可删"));
  assert.equal(treeOpConfirmMessage("rename", "x", false), "");
});

test("treeNamePromptHTML：data-confirm-value 文本框 + 转义默认值", () => {
  const html = treeNamePromptHTML("rename", "a<b>.c");
  assert.ok(html.includes("data-confirm-value"));
  assert.ok(html.includes("a&lt;b&gt;.c"));
  assert.ok(!html.includes("a<b>"));
});
