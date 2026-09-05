// md-library.test.mjs — Markdown 资料库纯函数（工单 wiki-materials/02，对偶
// pdf-library.test.mjs）。只测外部行为：过滤结果 / 排序 / 统计文案 / 行渲染 /
// 弹窗壳 / 编码路径。域内无健康/重复/回收/页数语义。
import test from "node:test";
import assert from "node:assert/strict";
import { esc, formatSize } from "../../src/contest_generator/static/js/fx/core.js";
import {
  mdEncodedPath, mdSubdir, formatMtime, mdFilterEntries, mdSortEntries,
  mdStats, mdStatsText, mdChipRowHTML, mdRowHTML, mdPreviewShellHTML, mdFileUrl,
  mdAssetUrl, mdAssetImageUrl,
} from "../../src/contest_generator/static/js/fx/md.js";

const mds = [
  {
    rel_path: "lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md",
    name: "sensor--mpu6050-six-axis-sensor.md",
    batch: "lckfb-地猛星移植手册",
    size_bytes: 51468,
    mtime: 1725000000,
  },
  {
    rel_path: "lckfb-地猛星移植手册/screen--0-96-color-screen.md",
    name: "screen--0-96-color-screen.md",
    batch: "lckfb-地猛星移植手册",
    size_bytes: 50111,
    mtime: 1725000001,
  },
  {
    rel_path: "2026_06_电赛视觉资料/12_xbhdcc_spi_lcd.py.md",
    name: "12_xbhdcc_spi_lcd.py.md",
    batch: "2026_06_电赛视觉资料",
    size_bytes: 1024,
    mtime: 1725000002,
  },
  {
    rel_path: "lckfb-地猛星移植手册/模块索引.md",
    name: "模块索引.md",
    batch: "lckfb-地猛星移植手册",
    size_bytes: 3273,
    mtime: 1725000003,
  },
];

// ================= 编码 / 子目录 / 时间 =================

test("mdEncodedPath：逐段编码保留段间 /", () => {
  assert.equal(
    mdEncodedPath("lckfb-地猛星移植手册/sensor--x.md"),
    "lckfb-%E5%9C%B0%E7%8C%9B%E6%98%9F%E7%A7%BB%E6%A4%8D%E6%89%8B%E5%86%8C/sensor--x.md"
  );
});

test("mdFileUrl：/api/materials-md/ + 段编码路径", () => {
  assert.equal(
    mdFileUrl("lckfb-地猛星移植手册/模块索引.md"),
    "/api/materials-md/lckfb-%E5%9C%B0%E7%8C%9B%E6%98%9F%E7%A7%BB%E6%A4%8D%E6%89%8B%E5%86%8C/%E6%A8%A1%E5%9D%97%E7%B4%A2%E5%BC%95.md"
  );
});

test("mdAssetUrl：/api/materials-md-assets/ + 段编码路径", () => {
  assert.equal(
    mdAssetUrl("lckfb-地猛星移植手册/images/0-96-color-screen/img1.gif"),
    "/api/materials-md-assets/lckfb-%E5%9C%B0%E7%8C%9B%E6%98%9F%E7%A7%BB%E6%A4%8D%E6%89%8B%E5%86%8C/images/0-96-color-screen/img1.gif"
  );
});

test("mdAssetImageUrl：相对路径按 .md 所在目录归一为资产端点", () => {
  assert.equal(
    mdAssetImageUrl("lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md", "images/0-96-color-screen/img1.gif"),
    "/api/materials-md-assets/lckfb-%E5%9C%B0%E7%8C%9B%E6%98%9F%E7%A7%BB%E6%A4%8D%E6%89%8B%E5%86%8C/images/0-96-color-screen/img1.gif"
  );
});

test("mdAssetImageUrl：./ 前缀归一（不产出 /./ 段）", () => {
  assert.equal(
    mdAssetImageUrl("lckfb-地猛星移植手册/sensor--x.md", "./images/x/img1.png"),
    "/api/materials-md-assets/lckfb-%E5%9C%B0%E7%8C%9B%E6%98%9F%E7%A7%BB%E6%A4%8D%E6%89%8B%E5%86%8C/images/x/img1.png"
  );
});

test("mdAssetImageUrl：批次根 md（rel_path 无 /）直接相对资产根", () => {
  assert.equal(
    mdAssetImageUrl("sensor--x.md", "images/x/img1.png"),
    "/api/materials-md-assets/images/x/img1.png"
  );
});

test("mdAssetImageUrl：http(s) 外链透传", () => {
  assert.equal(
    mdAssetImageUrl("lckfb-地猛星移植手册/sensor--x.md", "https://wiki.lckfb.com/storage/x/y.png"),
    "https://wiki.lckfb.com/storage/x/y.png"
  );
});

test("mdAssetImageUrl：空 src → 空串", () => {
  assert.equal(mdAssetImageUrl("lckfb-地猛星移植手册/sensor--x.md", ""), "");
});

test("mdSubdir：批次内子目录；批次根为空串", () => {
  assert.equal(mdSubdir("a/b/c/x.md"), "b/c");
  assert.equal(mdSubdir("a/x.md"), "");
  assert.equal(mdSubdir(""), "");
});

test("formatMtime：缺失/非法 → —；合法 → YYYY-MM-DD HH:mm", () => {
  assert.equal(formatMtime(null), "—");
  assert.equal(formatMtime(undefined), "—");
  assert.equal(formatMtime("not-a-number"), "—");
  assert.equal(formatMtime(0), "1970-01-01 08:00"); // 本地时区（东八）
  assert.match(formatMtime(1725000000), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
});

// ================= 过滤 =================

test("mdFilterEntries 关键字：文件名 / 批次 / 目录 / 完整路径，大小写不敏感", () => {
  assert.equal(mdFilterEntries(mds, { q: "MPU6050" }).length, 1);         // 大小写不敏感
  assert.equal(mdFilterEntries(mds, { q: "mpu6050" }).length, 1);
  assert.equal(mdFilterEntries(mds, { q: "电赛视觉" }).length, 1);        // 批次命中
  assert.equal(mdFilterEntries(mds, { q: "模块索引" }).length, 1);        // 文件名命中
  assert.equal(mdFilterEntries(mds, { q: "不存在的文件" }).length, 0);
});

test("mdFilterEntries 批次过滤与正交组合", () => {
  assert.equal(mdFilterEntries(mds, { q: "", batch: "lckfb-地猛星移植手册" }).length, 3);
  assert.equal(mdFilterEntries(mds, { q: "screen", batch: "lckfb-地猛星移植手册" }).length, 1);
  assert.equal(mdFilterEntries(mds, { q: "screen", batch: "2026_06_电赛视觉资料" }).length, 0);
  assert.equal(mdFilterEntries(mds, { q: "", batch: "不存在的批次" }).length, 0);
});

test("mdFilterEntries 空条件 = 全量返回（不改原数组）", () => {
  assert.equal(mdFilterEntries(mds, { q: "", batch: "" }).length, mds.length);
  assert.deepEqual(mdFilterEntries([], {}), []);
  assert.deepEqual(
    mdFilterEntries(mds, {}).map((m) => m.rel_path),
    mds.map((m) => m.rel_path)
  );
});

// ================= 排序 =================

test("mdSortEntries 文件名升/降序；稳定排序（ASCII 名）", () => {
  const asciiMds = [
    { ...mds[0], rel_path: "a/m.md", name: "m.md" },
    { ...mds[1], rel_path: "a/s1.md", name: "s1.md" },
    { ...mds[2], rel_path: "a/s2.md", name: "s2.md" },
    { ...mds[3], rel_path: "a/z.md", name: "z.md" },
  ];
  const byNameAsc = mdSortEntries(asciiMds, { by: "name", dir: "asc" });
  assert.deepEqual(byNameAsc.map((m) => m.name), ["m.md", "s1.md", "s2.md", "z.md"]);
  assert.deepEqual(
    mdSortEntries(asciiMds, { by: "name", dir: "desc" }).map((m) => m.name),
    ["z.md", "s2.md", "s1.md", "m.md"]
  );
});

test("mdSortEntries 大小 / 修改时间数值排序", () => {
  assert.deepEqual(
    mdSortEntries(mds, { by: "size", dir: "asc" }).map((m) => m.name),
    ["12_xbhdcc_spi_lcd.py.md", "模块索引.md", "screen--0-96-color-screen.md", "sensor--mpu6050-six-axis-sensor.md"]
  );
  assert.deepEqual(
    mdSortEntries(mds, { by: "mtime", dir: "desc" }).map((m) => m.name),
    ["模块索引.md", "12_xbhdcc_spi_lcd.py.md", "screen--0-96-color-screen.md", "sensor--mpu6050-six-axis-sensor.md"]
  );
});

test("mdSortEntries 批次 / 目录文本排序；缺省 = 文件名升序；不改原数组", () => {
  const byBatch = mdSortEntries(mds, { by: "batch", dir: "asc" });
  assert.deepEqual(byBatch.map((m) => m.batch), [
    "2026_06_电赛视觉资料", "lckfb-地猛星移植手册", "lckfb-地猛星移植手册", "lckfb-地猛星移植手册",
  ]);
  assert.deepEqual(mdSortEntries(mds, {}).length, mds.length);
  assert.equal(mds[0].name, "sensor--mpu6050-six-axis-sensor.md"); // 原数组未动
});

// ================= 统计 =================

test("mdStats 总数 / 总体积 / 批次数与批次份数表", () => {
  assert.deepEqual(mdStats(mds), {
    total: 4,
    totalBytes: 51468 + 50111 + 1024 + 3273,
    batchCount: 2,
    batchCounts: { "lckfb-地猛星移植手册": 3, "2026_06_电赛视觉资料": 1 },
  });
  assert.deepEqual(mdStats([]), { total: 0, totalBytes: 0, batchCount: 0, batchCounts: {} });
});

test("mdStatsText 文案：共 N 篇 · 总体积 X · M 个批次", () => {
  assert.equal(
    mdStatsText(mdStats(mds)),
    "共 4 篇 · 总体积 " + formatSize(51468 + 50111 + 1024 + 3273) + " · 2 个批次"
  );
  assert.equal(mdStatsText({ total: 0, totalBytes: 0, batchCount: 0 }), "共 0 篇 · 0 个批次");
});

// ================= 行渲染 / chips / 弹窗壳 =================

test("mdChipRowHTML：选中项 on 类、计数括号、转义", () => {
  const html = mdChipRowHTML([
    { value: "", label: "全部", count: 4 },
    { value: 'a"b', label: '标签"x', count: 1 },
  ], 'a"b');
  assert.match(html, /data-md-chip=""[^>]*>全部（4）<\/button>/);
  assert.match(html, /class="lib-chip on" data-md-chip="a&quot;b"/);
  assert.ok(!html.includes('标签"x'));
});

test("mdRowHTML：文件名链接 + tooltip + 批次 chip + 大小/时间 + 操作钮；超限徽章", () => {
  const html = mdRowHTML(mds[0]);
  assert.match(html, /data-open-md="lckfb-地猛星移植手册\/sensor--mpu6050-six-axis-sensor.md"/);
  assert.match(html, /data-md-preview="lckfb-地猛星移植手册\/sensor--mpu6050-six-axis-sensor.md"/);
  assert.match(html, /data-md-copy="lckfb-地猛星移植手册\/sensor--mpu6050-six-axis-sensor.md"/);
  assert.match(html, /lib-chip">lckfb-地猛星移植手册<\/span>/);
  assert.ok(!html.includes("超预览上限"));
  const big = mdRowHTML({ ...mds[0], size_bytes: 2 * 1024 * 1024 });
  assert.match(big, /超预览上限/);
});

test("mdRowHTML：有 title 时主行显示中文标题 + 文件名小字；无 title 回退文件名", () => {
  const withTitle = mdRowHTML({ ...mds[0], title: "MPU6050 六轴传感器" });
  assert.match(withTitle, />MPU6050 六轴传感器</);
  assert.match(withTitle, /md-row-file">sensor--mpu6050-six-axis-sensor\.md</);
  const noTitle = mdRowHTML(mds[0]);
  assert.match(noTitle, />sensor--mpu6050-six-axis-sensor\.md</);
  assert.ok(!noTitle.includes("md-row-file"));
});

test("mdPreviewShellHTML：元数据行 + 转义（标题/路径/大小/时间）", () => {
  const html = mdPreviewShellHTML(mds[3]);
  assert.match(html, /ref-detail-title">模块索引\.md</);
  assert.match(html, /lckfb-地猛星移植手册\/模块索引\.md/);
  assert.match(html, /批次<\/span><span><span class="lib-chip">lckfb-地猛星移植手册<\/span>/);
  assert.ok(html.includes("ref-detail-k\">大小"));
  assert.ok(html.includes(formatSize(3273)));
  assert.ok(!html.includes("<script>")); // 标题转义（无原始 HTML 透传）
});

// ================= 域内导出护栏（fx-guard DOMAINS 登记对齐） =================

test("mdEncodedPath 不编码段间分隔符（URL 安全）", () => {
  const p = mdEncodedPath("a b/c#d.md");
  assert.equal(p, "a%20b/c%23d.md");
});
