// fx/code-tree-ops.js 纯函数单测（工单 code-tree-ops/02）：名称校验 /
// 受影响判定 / 重命名映射 / 目录判定 / 标题与文案 / 输入框 HTML。
// 直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
  treeCtxItems,
  setCodeTreeNameRules,
  CODE_TREE_NAME_ILLEGAL,
  CODE_TREE_NAME_MAX,
  CODE_TREE_NAME_RULES_DEFAULT,
} from "../../src/contest_generator/static/js/fx/code-tree-ops.js";

// ---- 规则由后端下发（工单 cross-lang-mirror-c5a/01）----
//
// 判据单源 = 后端 codeview.name_rules_payload，经 POST /api/code/open 的
// name_rules 下发；本模块的常量退化为「后端尚未下发时的启动兜底」。下面按
// **后端下发值**驱动校验，确认校验真吃下发的那份（而不是恒读兜底）。

test("setCodeTreeNameRules：按后端下发的规则驱动校验（兜底不是唯一出处）", () => {
  try {
    setCodeTreeNameRules({ illegal: "@", max_len: 5 });
    assert.equal(treeNameValidate("a@b").ok, false);
    assert.equal(treeNameValidate("a-b").ok, true);   // 兜底集合里的字符，下发后放行
    assert.equal(treeNameValidate("abcde").ok, true);
    assert.equal(treeNameValidate("abcdef").ok, false);
  } finally {
    setCodeTreeNameRules(CODE_TREE_NAME_RULES_DEFAULT);  // 复原本模块兜底，防串场景
  }
  assert.equal(treeNameValidate("a@b").ok, true);        // 复原后再按兜底判
  assert.equal(treeNameValidate("x".repeat(CODE_TREE_NAME_MAX)).ok, true);
});

test("setCodeTreeNameRules：下发值含反斜杠 / 上限边界逐字生效", () => {
  // 反斜杠是这条规则里最容易漏的一个：JS 源码里写作 "\\"，下发值是单个
  // "\"——校验必须按**下发的那一个字符**判，不能被转义写法带偏。
  try {
    setCodeTreeNameRules({ illegal: "\\", max_len: 8 });
    assert.equal(treeNameValidate("a\\b").ok, false);
    assert.equal(treeNameValidate("a/b").ok, true);    // 未下发的分隔符不拦
    assert.equal(treeNameValidate("a".repeat(8)).ok, true);
    assert.equal(treeNameValidate("a".repeat(9)).ok, false);
  } finally {
    setCodeTreeNameRules(CODE_TREE_NAME_RULES_DEFAULT);
  }
});

test("setCodeTreeNameRules：畸形下发一律忽略（空集合/空串/负数不许放行一切）", () => {
  try {
    for (const bad of [
      { illegal: "", max_len: 120 },
      { illegal: "/\\:*", max_len: 0 },
      { illegal: "/\\:*", max_len: -1 },
      { illegal: "/\\:*", max_len: 1.5 },
      { illegal: null, max_len: 120 },
      { illegal: "/\\:*" },
      {},
      null,
    ]) {
      setCodeTreeNameRules(bad);
      // 规则没被改坏：兜底仍在生效（含兜底非法字符、上限仍是 120）
      assert.equal(treeNameValidate("a/b").ok, false, "畸形下发不该把非法集清空");
      assert.equal(treeNameValidate("x".repeat(CODE_TREE_NAME_MAX + 1)).ok, false,
        "畸形下发不该把上限放开");
    }
  } finally {
    setCodeTreeNameRules(CODE_TREE_NAME_RULES_DEFAULT);
  }
});

// ---- 装载接线：打开目录的每个响应都要把规则装进本模块（工单 01 评审整改）----
//
// 这条是**源码守卫**而非行为测试：`ui/codeview.js` 依赖 DOM 与 fetch，进不了
// node:test（仓库里 ui 层只有 2 个测试文件 import 它）。守卫只回答一件事——
// 「每个 /api/code/open 调用点附近都调了装载函数」；漏装时前端会静默退回兜底
// 常量，规则漂移就又成了没人发现的那类问题，所以这层守卫不能省。
// 形态无关：`setCodeTreeNameRules(data.name_rules)` 与
// `const r = data.name_rules; setCodeTreeNameRules(r)` 都算通过（先例：
// tests/js/overlay-confirm.test.mjs:82 对 ui/code-tree-ops.js 的同款守卫）。
test("ui/codeview.js：每个 /api/code/open 响应都装载名称规则", () => {
  const src = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/codeview.js", import.meta.url), "utf8");
  const lines = src.split("\n");
  const calls = lines
    .map((line, i) => [line, i])
    .filter(([line]) => line.includes('apiPost("/api/code/open"'));
  assert.ok(calls.length >= 1, "ui/codeview.js 应有 /api/code/open 调用点");

  for (const [line, i] of calls) {
    const window = lines.slice(i, i + 6).join("\n");
    assert.ok(window.includes("setCodeTreeNameRules("),
      `第 ${i + 1} 行的 /api/code/open 响应未装载名称规则：\n${line.trim()}`);
  }
});

test("CODE_TREE_NAME_RULES_DEFAULT：可把校验复装回兜底口径", () => {
  // 断言的是「复装后校验结论回到兜底」这一**能力**（不是常量对象等于自己）
  try {
    setCodeTreeNameRules({ illegal: "@", max_len: 3 });
    assert.equal(treeNameValidate("a@b").ok, false);
    assert.equal(treeNameValidate("abcd").ok, false);

    setCodeTreeNameRules(CODE_TREE_NAME_RULES_DEFAULT);

    assert.equal(treeNameValidate("a@b").ok, true);                       // "@" 只在下发里
    assert.equal(treeNameValidate("a/b").ok, false);                      // 兜底非法字符回来了
    assert.equal(treeNameValidate("abcd").ok, true);                      // 上限回到 120
    assert.equal(treeNameValidate("a".repeat(CODE_TREE_NAME_MAX)).ok, true);
    assert.equal(treeNameValidate("a".repeat(CODE_TREE_NAME_MAX + 1)).ok, false);
  } finally {
    setCodeTreeNameRules(CODE_TREE_NAME_RULES_DEFAULT);
  }
});

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

// ---- 右键菜单（工单 code-editor-refine/06）----

test("treeCtxItems：四项（打开/复制相对路径/重命名/删除），目录打开 = 展开/收起", () => {
  const file = treeCtxItems(false);
  assert.deepEqual(file.map((i) => i.action), ["open", "copy", "rename", "delete"]);
  assert.equal(file[0].label, "打开");
  assert.equal(file[1].label, "复制相对路径");
  assert.equal(file[3].danger, true);
  assert.equal(treeCtxItems(true)[0].label, "展开 / 收起");
});
