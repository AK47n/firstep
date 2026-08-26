// 母版库增强轮纯函数（工单 master-library-ui-2/01）：健康徽章 + 体积统计行。
// 直接 import fx/master.js；只测外部行为，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  masterHealthBadgeHTML,
  masterStatsHTML,
  masterTableRowHTML,
  masterDetailHTML,
  buildMasterTree,
  masterTreeNodeHTML,
  masterTreeFileURL,
  masterContentHTML,
} from "../../src/contest_generator/static/js/fx/master.js";

const HEALTH_OK = {
  ok: true,
  missing_key_files: [],
  config_file_ok: true,
  artifact_dirs: [],
};
const HEALTH_WARN = {
  ok: false,
  missing_key_files: ["pin_config.h", "user/Project.uvprojx"],
  config_file_ok: false,
  artifact_dirs: ["Debug"],
};

test("masterHealthBadgeHTML：健康 = ✓ 徽章 + title 说明", () => {
  const out = masterHealthBadgeHTML(HEALTH_OK);
  assert.ok(out.includes("✓ 健康"));
  assert.ok(out.includes('class="master-health-pill master-health-ok"'));
  assert.ok(out.includes(
    'title="健康：关键文件齐全、工程配置文件在、无构建产物残留"',
  ));
});

test("masterHealthBadgeHTML：异常 = ⚠ 徽章 + title 明细（缺失/配置/残留）", () => {
  const out = masterHealthBadgeHTML(HEALTH_WARN);
  assert.ok(out.includes("⚠ 有缺失或残留"));
  assert.ok(out.includes(
    'title="关键文件缺失：pin_config.h、user/Project.uvprojx；缺少工程配置文件；构建产物残留：Debug"',
  ));
});

test("masterHealthBadgeHTML：缺失/残留明细转义 title", () => {
  const out = masterHealthBadgeHTML({
    ...HEALTH_WARN,
    missing_key_files: ['<img src=x>'],
  });
  assert.ok(out.includes("&lt;img src=x&gt;"));
  assert.ok(!out.includes('<img src=x>'));
});

test("masterStatsHTML：总体积/文件数/大文件清单（formatSize 可读单位）", () => {
  const out = masterStatsHTML({
    total_size_bytes: 6291456,
    file_count: 42,
    big_files: [
      { path: "ml_libs/oled.c", size_bytes: 1572864 },
      { path: "user/Project.uvprojx", size_bytes: 17606 },
    ],
  });
  assert.ok(out.includes("总体积"));
  assert.ok(out.includes("6.0 MB"));
  assert.ok(out.includes("文件数"));
  assert.ok(out.includes("42 个"));
  assert.ok(out.includes("大文件"));
  assert.ok(out.includes("ml_libs/oled.c（1.5 MB）"));
  assert.ok(out.includes("user/Project.uvprojx（17.2 KB）"));
});

test("masterStatsHTML：无大文件 = — 占位；0 字节 0 文件", () => {
  const out = masterStatsHTML({
    total_size_bytes: 0,
    file_count: 0,
    big_files: [],
  });
  assert.ok(out.includes("0 B"));
  assert.ok(out.includes("0 个"));
  assert.ok(out.includes("—"));

  const empty = masterStatsHTML({ total_size_bytes: 0, file_count: 0, big_files: undefined });
  assert.ok(empty.includes("大文件"));
  assert.ok(empty.includes("—"));
});

test("masterTableRowHTML：带 health = 健康徽章列；不带 = 既有行列不变", () => {
  const base = {
    platform: "stm32",
    platform_label: "STM32 · Keil5",
    sources: ["2026C"],
    warnings: [],
    key_files: [],
  };
  const out = masterTableRowHTML({ ...base, health: HEALTH_OK });
  assert.ok(out.includes('class="master-health-pill master-health-ok"'));
  assert.ok(out.includes("✓ 健康"));
  // 既有列仍渲染
  assert.ok(out.includes("STM32 · Keil5"));
  assert.ok(out.includes('data-master-detail="stm32"'));

  const legacy = masterTableRowHTML(base);
  assert.ok(!legacy.includes("master-health-pill"));
  assert.ok(legacy.includes('data-master-detail="stm32"'));
});

test("masterDetailHTML：带 stats = 元数据段增统计行；不带 = 既有结构不变", () => {
  const base = {
    platform: "stm32",
    sources: ["2026C"],
    warnings: [],
    key_files: [],
  };
  const out = masterDetailHTML({
    ...base,
    stats: { total_size_bytes: 6291456, file_count: 42, big_files: [] },
  });
  assert.ok(out.includes("总体积"));
  assert.ok(out.includes("6.0 MB"));
  assert.ok(out.includes("42 个"));
  assert.ok(out.includes("关键文件清单")); // 清单段仍渲染

  const legacy = masterDetailHTML(base);
  assert.ok(!legacy.includes("总体积"));
  assert.ok(legacy.includes("关键文件清单"));
});

// ================= 工单 02：文件树（构建 / 树 HTML / URL 拼装） =================

const TREE_FILES = [
  { path: "main.c", size_bytes: 909 },
  { path: "inc/stm32f10x_conf.h", size_bytes: 500 },
  { path: "user/Project.uvprojx", size_bytes: 17606 },
  { path: "user/oled.c", size_bytes: 2048 },
  { path: "user/keil/startup.s", size_bytes: 8192 },
];

test("buildMasterTree：扁平清单 → 嵌套树（目录在前，目录/文件内按码点序）", () => {
  const nodes = buildMasterTree(TREE_FILES);
  assert.deepEqual(nodes.map((n) => n.name), ["inc", "user", "main.c"]);
  assert.equal(nodes[0].isDir, true);
  assert.equal(nodes[0].path, "inc");
  assert.deepEqual(nodes[0].children.map((n) => n.name), ["stm32f10x_conf.h"]);
  assert.equal(nodes[0].children[0].path, "inc/stm32f10x_conf.h");
  assert.equal(nodes[0].children[0].size_bytes, 500);
  assert.equal(nodes[0].children[0].isDir, false);
  const user = nodes[1];
  assert.deepEqual(user.children.map((n) => n.name), ["keil", "Project.uvprojx", "oled.c"]);
  assert.equal(user.children[0].path, "user/keil");
  assert.equal(user.children[0].children[0].path, "user/keil/startup.s");
  assert.equal(nodes[2].path, "main.c");
  assert.equal(nodes[2].isDir, false);
});

test("buildMasterTree：空清单 → []；根级单文件", () => {
  assert.deepEqual(buildMasterTree([]), []);
  const one = buildMasterTree([{ path: "main.c", size_bytes: 1 }]);
  assert.equal(one.length, 1);
  assert.equal(one[0].isDir, false);
  assert.equal(one[0].size_bytes, 1);
});

test("masterTreeNodeHTML：递归 details/summary + 行按钮 data 属性 + 大小 + 转义", () => {
  const html = masterTreeNodeHTML(buildMasterTree(TREE_FILES));
  assert.ok(html.includes("<details open><summary>user</summary>"));
  assert.ok(html.includes("<details open><summary>keil</summary>"));
  assert.ok(html.includes('data-master-tree-file="main.c"'));
  assert.ok(html.includes('data-master-tree-file="user/oled.c"'));
  assert.ok(html.includes('data-master-tree-file="user/keil/startup.s"'));
  assert.ok(html.includes("909 B"));
  assert.ok(html.includes("17.2 KB"));
  const evil = masterTreeNodeHTML(buildMasterTree([{ path: "<i>.c", size_bytes: 1 }]));
  assert.ok(evil.includes("&lt;i&gt;.c"));
  assert.ok(!evil.includes("<i>.c"));
});

test("masterTreeFileURL：/api/masters/{platform}/tree/{path}，逐段编码", () => {
  assert.ok(masterTreeFileURL("stm32", "main.c") === "/api/masters/stm32/tree/main.c");
  assert.ok(masterTreeFileURL("stm32", "user/keil/startup.s")
    === "/api/masters/stm32/tree/user/keil/startup.s");
  assert.ok(masterTreeFileURL("stm32", "a b/c") === "/api/masters/stm32/tree/a%20b/c");
  assert.ok(masterTreeFileURL("a/b", "x") === "/api/masters/a%2Fb/tree/x");
});

// ================= 工单 03：内容箱渲染（复制钮 + 高亮） =================

test("masterContentHTML：成功 = 复制按钮 + 语言高亮 pre", () => {
  const out = masterContentHTML({ ok: true, content: "int x = 1;\n" }, "main.c");
  assert.ok(out.includes('data-master-copy'));
  assert.ok(out.includes("复制"));
  assert.ok(out.includes('class="master-file-pre"'));
  assert.match(out, /<span class="tok-kw">int<\/span>/);
});

test("masterContentHTML：plain / 未知语言无高亮 span，内容仍转义", () => {
  const out = masterContentHTML({ ok: true, content: "a < b && c\n" }, "readme.txt");
  assert.ok(out.includes("&lt;"));
  assert.ok(!out.includes("tok-"));
  assert.ok(!out.includes("a < b"));
});

test("masterContentHTML：失败 = 中文原因 + 可重试提示，无复制钮", () => {
  const out = masterContentHTML({ ok: false, message: "非法路径：../x" }, "a.c");
  assert.ok(out.includes("加载失败"));
  assert.ok(out.includes("非法路径"));
  assert.ok(out.includes("可重试"));
  assert.ok(!out.includes("data-master-copy"));
});

test("masterContentHTML：null = 加载中占位（三态），无复制钮", () => {
  const out = masterContentHTML(null, "main.c");
  assert.ok(out.includes("加载中"));
  assert.ok(!out.includes("data-master-copy"));
});
