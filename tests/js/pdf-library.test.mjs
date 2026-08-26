// PDF 资料库表格精修纯函数单测（工单 pdf-library-ui/02）：
// pdfSubdir / formatMtime / pdfFilterEntries / pdfSortEntries / pdfStats /
// pdfStatsText / pdfRowHTML。只测外部行为（过滤结果 / 排序 / 统计 / 渲染子串），
// 子串断言防脆。对偶 reference-library.test.mjs 范式。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { esc, formatSize } from "../../src/contest_generator/static/js/fx/core.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 reference-library.test.mjs 范式）；deps = 注入的兄弟函数依赖。
// 先跳过参数区（参数可能含默认值花括号，如 flags = {}），从函数体 { 开始配平。
function extract(name, deps) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  let i = html.indexOf("(", start);
  assert.ok(i !== -1, name + " 函数缺少参数表");
  let pdepth = 0;
  for (; i < html.length; i++) {
    if (html[i] === "(") pdepth++;
    else if (html[i] === ")") { pdepth--; if (pdepth === 0) break; }
  }
  const open = html.indexOf("{", i);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let j = open; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") {
      depth--;
      if (depth === 0) {
        const fnSrc = html.slice(start, j + 1);
        if (deps && Object.keys(deps).length) {
          return new Function(...Object.keys(deps), "return (" + fnSrc + ")")(
            ...Object.values(deps)
          );
        }
        return new Function("return (" + fnSrc + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

// 依赖顺序：先提取 pdfSubdir / formatMtime，再提取使用它们的函数
const pdfSubdir = extract("pdfSubdir");
const formatMtime = extract("formatMtime");
const pdfFilterEntries = extract("pdfFilterEntries", { pdfSubdir });
const pdfSortEntries = extract("pdfSortEntries", { pdfSubdir });
const pdfStats = extract("pdfStats");
const pdfStatsText = extract("pdfStatsText", { formatSize });
const pdfBadgeTags = extract("pdfBadgeTags");
const pdfRowHTML = extract("pdfRowHTML", { esc, formatSize, pdfSubdir, formatMtime, pdfBadgeTags });
const pdfChipRowHTML = extract("pdfChipRowHTML", { esc });
// 工单 03：详情弹窗（pdfPagesText 先于 pdfDetailHTML 提取）
const pdfEncodedPath = extract("pdfEncodedPath");
const pdfPagesUrl = extract("pdfPagesUrl", { pdfEncodedPath });
const pdfPagesText = extract("pdfPagesText", { esc });
const pdfDupRemainText = extract("pdfDupRemainText");
const pdfDetailHTML = extract("pdfDetailHTML", { esc, formatSize, formatMtime, pdfSubdir, pdfPagesText, pdfBadgeTags, pdfDupRemainText });
// 工单 04：数据健康（pdfBroken 先于 pdfDupGroups/pdfHealth 提取）
const pdfBroken = extract("pdfBroken");
const pdfDupGroups = extract("pdfDupGroups");
const pdfHealth = extract("pdfHealth", { pdfBroken, pdfDupGroups });
// 工单 06：回收删除（pdfTrashUrl 对偶 pdfPagesUrl；pdfDupRemainText 在 03 块已提）
const pdfTrashUrl = extract("pdfTrashUrl", { pdfEncodedPath });
const pdfTrashConfirmHTML = extract("pdfTrashConfirmHTML", { esc, formatSize, pdfBadgeTags });

// 样例：跨批次 + 批次内子目录 + 0 字节损坏（3/04 轮才警示，此处只当普通数据）
const pdfs = [
  { rel_path: "000_2017-2025_真题汇总/真题汇总.pdf", name: "真题汇总.pdf", batch: "000_2017-2025_真题汇总", size_bytes: 35000000, mtime: 1700000000 },
  { rel_path: "塔克R3两驱小车底盘资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG电机驱动芯片数据手册.pdf", name: "TB6612FNG电机驱动芯片数据手册.pdf", batch: "塔克R3两驱小车底盘资料", size_bytes: 1048576, mtime: 1700000100 },
  { rel_path: "塔克R3两驱小车底盘资料/7 AT8236电机驱动资料/3.芯片手册/TB6612FNG电机驱动芯片数据手册.pdf", name: "TB6612FNG电机驱动芯片数据手册.pdf", batch: "塔克R3两驱小车底盘资料", size_bytes: 1048576, mtime: 1700000200 },
  { rel_path: "2026_04_地猛星电赛控制题配套资料/大矩形(视觉识别训练样本).pdf", name: "大矩形(视觉识别训练样本).pdf", batch: "2026_04_地猛星电赛控制题配套资料", size_bytes: 0, mtime: 1700000300 },
  { rel_path: "2026_04_地猛星电赛控制题配套资料/原理图.pdf", name: "原理图.pdf", batch: "2026_04_地猛星电赛控制题配套资料", size_bytes: 4200, mtime: 1700000400 },
];

// ================= 子目录推导：pdfSubdir =================
test("pdfSubdir 批次根 = 空串；批次内多级子目录按段保留", () => {
  assert.equal(pdfSubdir("000_2017-2025_真题汇总/真题汇总.pdf"), "");
  assert.equal(pdfSubdir("2026_04_地猛星电赛控制题配套资料/原理图.pdf"), "");
  assert.equal(pdfSubdir("塔克R3两驱小车底盘资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG电机驱动芯片数据手册.pdf"),
    "6 TB6612电机驱动资料/3.芯片手册");
  // 无批次段的单层文件名：不炸、返回空
  assert.equal(pdfSubdir("单层.pdf"), "");
});

// ================= 时间格式化：formatMtime =================
test("formatMtime epoch 秒 → 本地 YYYY-MM-DD HH:mm；非法值 → —", () => {
  const fmtLocal = (ts) => {
    const d = new Date(ts * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  assert.match(formatMtime(1700000000), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  assert.equal(formatMtime(1700000000), fmtLocal(1700000000));
  // 0 是合法 epoch（1970-01-01），不是非法值
  assert.equal(formatMtime(0), fmtLocal(0));
  assert.equal(formatMtime(null), "—");
  assert.equal(formatMtime(undefined), "—");
});

// ================= 过滤：pdfFilterEntries =================
test("pdfFilterEntries 关键字：文件名 / 批次 / 目录 / 完整路径，大小写不敏感", () => {
  assert.equal(pdfFilterEntries(pdfs, { q: "TB6612FNG" }).length, 2);        // 文件名
  assert.equal(pdfFilterEntries(pdfs, { q: "tb6612fng" }).length, 2);        // 大小写不敏感
  assert.equal(pdfFilterEntries(pdfs, { q: "芯片手册" }).length, 2);          // 目录命中
  assert.equal(pdfFilterEntries(pdfs, { q: "真题汇总" }).length, 1);          // 批次/路径命中
  assert.equal(pdfFilterEntries(pdfs, { q: "塔克R3两驱" }).length, 2);        // 批次命中
  assert.equal(pdfFilterEntries(pdfs, { q: "不存在的文件" }).length, 0);
});

test("pdfFilterEntries 批次过滤与正交组合", () => {
  assert.equal(pdfFilterEntries(pdfs, { q: "", batch: "塔克R3两驱小车底盘资料" }).length, 2);
  assert.equal(pdfFilterEntries(pdfs, { q: "TB6612", batch: "塔克R3两驱小车底盘资料" }).length, 2);
  assert.equal(pdfFilterEntries(pdfs, { q: "真题", batch: "塔克R3两驱小车底盘资料" }).length, 0);
  assert.equal(pdfFilterEntries(pdfs, { q: "", batch: "不存在的批次" }).length, 0);
});

test("pdfFilterEntries 空条件 = 全量返回（不改原数组、不引用外部状态）", () => {
  const before = JSON.parse(JSON.stringify(pdfs));
  assert.equal(pdfFilterEntries(pdfs, { q: "", batch: "" }).length, pdfs.length);
  assert.deepEqual(pdfs, before);
  assert.deepEqual(pdfFilterEntries([], { q: "", batch: "" }), []);
  assert.deepEqual(pdfFilterEntries(pdfs, {}).map((p) => p.rel_path), pdfs.map((p) => p.rel_path));
});

test("pdfFilterEntries 健康维度：无谓词 = 不过滤（与注释语义一致），有谓词 = 正交过滤", () => {
  // health 置位但未注入谓词：该维度不参与（不静默清空——工单 04 漏传预期）
  assert.equal(pdfFilterEntries(pdfs, { q: "", batch: "", health: "broken" }).length, pdfs.length);
  assert.equal(pdfFilterEntries(pdfs, { q: "", batch: "", health: "dup" }).length, pdfs.length);
  // 注入谓词后正交过滤（工单 04 接线形态：isBroken = 0 字节 / isDup = 同名同大小）
  assert.deepEqual(
    pdfFilterEntries(pdfs, { health: "broken", isBroken: (p) => p.size_bytes === 0 })
      .map((p) => p.name), ["大矩形(视觉识别训练样本).pdf"]);
  assert.deepEqual(
    pdfFilterEntries(pdfs, { health: "dup", isDup: (p) => p.name === "TB6612FNG电机驱动芯片数据手册.pdf" })
      .map((p) => p.name), ["TB6612FNG电机驱动芯片数据手册.pdf", "TB6612FNG电机驱动芯片数据手册.pdf"]);
  // 与关键字/批次正交
  assert.equal(pdfFilterEntries(pdfs, { q: "真题", health: "dup", isDup: () => false }).length, 0);
});

// ================= 批次 chips 渲染：pdfChipRowHTML =================
test("pdfChipRowHTML 全量 chip 带 .lib-chip，选中加 on，count 括号", () => {
  const html = pdfChipRowHTML([
    { value: "", label: "全部", count: 5 },
    { value: "A批", label: "A批", count: 3 },
  ], "A批");
  assert.ok(html.startsWith('<button type="button" class="lib-chip" data-pdf-chip="">全部（5）</button>'));
  assert.ok(html.includes('<button type="button" class="lib-chip on" data-pdf-chip="A批">A批（3）</button>'));
  assert.ok(html.includes("data-pdf-chip"));
});

// ================= 排序：pdfSortEntries =================
const sortPdfs = [
  { id: "z", rel_path: "B批/zeta.pdf", name: "zeta.pdf", batch: "B批", size_bytes: 10, mtime: 3 },
  { id: "a", rel_path: "A批/alpha.pdf", name: "alpha.pdf", batch: "A批", size_bytes: 30, mtime: 1 },
  { id: "m1", rel_path: "A批/子/mid.pdf", name: "mid.pdf", batch: "A批", size_bytes: 20, mtime: 2 },
  { id: "m2", rel_path: "A批/子/mid2.pdf", name: "mid.pdf", batch: "A批", size_bytes: 20, mtime: 2 },
];

test("pdfSortEntries 文件名升/降序；同键保持原相对序（稳定排序）", () => {
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "name", dir: "asc" }).map((p) => p.id), ["a", "m1", "m2", "z"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "name", dir: "desc" }).map((p) => p.id), ["z", "m1", "m2", "a"]);
});

test("pdfSortEntries 大小 / 修改时间数值排序", () => {
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "size", dir: "asc" }).map((p) => p.id), ["z", "m1", "m2", "a"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "size", dir: "desc" }).map((p) => p.id), ["a", "m1", "m2", "z"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "mtime", dir: "asc" }).map((p) => p.id), ["a", "m1", "m2", "z"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "mtime", dir: "desc" }).map((p) => p.id), ["z", "m1", "m2", "a"]);
});

test("pdfSortEntries 批次 / 目录文本排序；缺省 = 文件名升序；不改原数组", () => {
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "batch", dir: "asc" }).map((p) => p.id), ["a", "m1", "m2", "z"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "batch", dir: "desc" }).map((p) => p.id), ["z", "a", "m1", "m2"]);
  // 目录：批次根（""）排最前；"子" 排后；同级稳定
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "subdir", dir: "asc" }).map((p) => p.id), ["z", "a", "m1", "m2"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, { by: "subdir", dir: "desc" }).map((p) => p.id), ["m1", "m2", "z", "a"]);
  assert.deepEqual(pdfSortEntries(sortPdfs, {}).map((p) => p.id), ["a", "m1", "m2", "z"]);
  const before = sortPdfs.map((p) => p.id);
  assert.deepEqual(sortPdfs.map((p) => p.id), before);
});

// ================= 统计：pdfStats / pdfStatsText =================
test("pdfStats 总数 / 总体积 / 批次数与批次份数表", () => {
  assert.deepEqual(pdfStats(pdfs), {
    total: 5,
    totalBytes: 37101352,
    batchCount: 3,
    batchCounts: {
      "000_2017-2025_真题汇总": 1,
      "塔克R3两驱小车底盘资料": 2,
      "2026_04_地猛星电赛控制题配套资料": 2,
    },
  });
  assert.deepEqual(pdfStats([]), { total: 0, totalBytes: 0, batchCount: 0, batchCounts: {} });
});

test("pdfStatsText 文案：共 N 份 · 总体积 X · M 个批次", () => {
  assert.equal(pdfStatsText(pdfStats(pdfs)),
    "共 5 份 · 总体积 " + formatSize(37101352) + " · 3 个批次");
  // 0 字节总体积不显示「总体积」段（对偶 refStatsText）
  assert.equal(pdfStatsText({ total: 0, totalBytes: 0, batchCount: 0 }), "共 0 份 · 0 个批次");
});

// ================= 行渲染：pdfRowHTML =================
test("pdfRowHTML 六列：文件名链接（全文 tooltip）/ 批次 chip / 目录 / 大小 / 修改时间 / 操作", () => {
  const row = pdfRowHTML(pdfs[1], {});
  const rel = pdfs[1].rel_path;
  assert.ok(row.includes('data-open-pdf="' + rel + '"'), "打开数据属性应为完整相对路径");
  assert.ok(row.includes('title="' + rel + '"'), "tooltip 应为完整相对路径");
  assert.ok(row.includes(">TB6612FNG电机驱动芯片数据手册.pdf</a>"), "文件名链接文本");
  assert.ok(row.includes("class=\"lib-chip\""), "批次 chip 应为 .lib-chip 令牌");
  assert.ok(row.includes("塔克R3两驱小车底盘资料"), "批次 chip 文案");
  assert.ok(row.includes("6 TB6612电机驱动资料/3.芯片手册"), "目录列");
  assert.ok(row.includes(formatSize(1048576)), "大小列 = formatSize 口径");
  assert.ok(row.includes(formatMtime(1700000100)), "修改时间列 = formatMtime 口径");
  assert.ok(row.includes(">打开</button>"), "打开按钮");
  assert.ok(row.includes(">详情</button>"), "详情按钮（弹窗接线为工单 03）");
});

test("pdfRowHTML 批次根文件：目录列显示 —；HTML 转义生效", () => {
  const rootRow = pdfRowHTML(pdfs[0], {});
  assert.ok(rootRow.includes(">—</td>"), "批次根目录列应为 —");
  const amp = pdfRowHTML({ rel_path: "批/A&B.pdf", name: "A&B.pdf", batch: "批", size_bytes: 3, mtime: 1 }, {});
  assert.ok(amp.includes("A&amp;B.pdf"), "文件名 & 应转义");
});

// ================= 详情弹窗（工单 03）：pdfPagesText / pdfDetailHTML =================
test("pdfEncodedPath 逐段编码（分隔符保留，段内特殊字符转义）", () => {
  assert.equal(pdfEncodedPath("批 A/文件(1).pdf"),
    encodeURIComponent("批 A") + "/" + encodeURIComponent("文件(1).pdf"));
  assert.equal(pdfEncodedPath("单层.pdf"), encodeURIComponent("单层.pdf"));
});

test("pdfPagesUrl 页数端点：逐段编码 + /pages 尾缀", () => {
  assert.equal(pdfPagesUrl("批 A/文件(1).pdf"),
    "/api/pdfs/" + encodeURIComponent("批 A") + "/" + encodeURIComponent("文件(1).pdf") + "/pages");
});

test("pdfPagesText 三态：读取中 / N 页 / 无法读取", () => {
  assert.ok(pdfPagesText(null).includes("页数读取中"), "加载中占位");
  assert.ok(pdfPagesText(12).includes("12 页"), "页数成功");
  assert.ok(pdfPagesText("error").includes("无法读取"), "损坏 400 → 无法读取");
});

test("pdfDetailHTML 元数据段（路径/批次 chip/目录/大小/mtime/页数占位）+ 操作段（打开/复制）", () => {
  const d = pdfDetailHTML(pdfs[1], null);
  const rel = pdfs[1].rel_path;
  assert.ok(d.includes("TB6612FNG电机驱动芯片数据手册.pdf"), "标题 = 文件名");
  assert.ok(d.includes(rel), "完整相对路径");
  assert.ok(d.includes("class=\"lib-chip\"") && d.includes("塔克R3两驱小车底盘资料"), "批次 chip");
  assert.ok(d.includes("6 TB6612电机驱动资料/3.芯片手册"), "目录");
  assert.ok(d.includes(formatSize(1048576)) && d.includes(formatMtime(1700000100)), "大小 + mtime");
  assert.ok(d.includes("页数读取中"), "页数加载占位（懒取）");
  assert.ok(d.includes('data-pdf-open="' + rel + '"'), "打开按钮数据属性 = rel_path");
  assert.ok(d.includes(">打开 PDF</button>") && d.includes(">复制相对路径</button>"), "操作按钮文案");
  assert.ok(d.includes('data-pdf-copy="' + rel + '"'), "复制按钮数据属性 = rel_path（原始路径，非编码）");
});

test("pdfDetailHTML 页数成功 / 无法读取两态渲染；HTML 转义生效", () => {
  assert.ok(pdfDetailHTML(pdfs[1], 12).includes(">12 页<"), "成功态");
  assert.ok(pdfDetailHTML(pdfs[1], "error").includes("无法读取"), "400 态");
  const amp = pdfDetailHTML({ rel_path: "批/A&B.pdf", name: "A&B.pdf", batch: "批", size_bytes: 3, mtime: 1 }, 4);
  assert.ok(amp.includes("A&amp;B.pdf"), "文件名 & 应转义");
});

// ================= 数据健康（工单 04）：pdfBroken / pdfDupGroups / pdfHealth =================
test("pdfBroken 判据：size_bytes === 0 为损坏，>0 非损坏", () => {
  assert.equal(pdfBroken({ size_bytes: 0 }), true);
  assert.equal(pdfBroken({ size_bytes: 1 }), false);
  assert.equal(pdfBroken({ size_bytes: "0" }), true, "字符串 0 也判损坏（防御宽松，配套 Number 防护）");
  assert.equal(pdfBroken({}), false);
  assert.equal(pdfBroken({ size_bytes: null }), false, "null 不判损坏（缺失字段≠空文件）");
});

test("pdfBadgeTags 徽章拼接：损坏/重复独立开关，双 false = 空串", () => {
  assert.ok(pdfBadgeTags(true, false).includes("⚠ 损坏") && !pdfBadgeTags(true, false).includes("疑似重复"));
  assert.ok(pdfBadgeTags(false, true).includes("⚠ 疑似重复") && !pdfBadgeTags(false, true).includes("损坏"));
  assert.ok(pdfBadgeTags(true, true).includes("⚠ 损坏") && pdfBadgeTags(true, true).includes("⚠ 疑似重复"));
  assert.equal(pdfBadgeTags(false, false), "", "无标注 = 空串（行/详情共用）");
});

test("pdfDupGroups 判据：同名（大小写不敏感）+ 同大小 + 大小>0，组内 ≥2 成员", () => {
  const list = [
    { name: "A.pdf", size_bytes: 10, rel_path: "批1/A.pdf" },
    { name: "a.pdf", size_bytes: 10, rel_path: "批2/A.pdf" },   // 大小写不敏感 + 同大小 → 同组
    { name: "A.pdf", size_bytes: 20, rel_path: "批3/A.pdf" },   // 同名不同大小 = 版本差异，不判
    { name: "B.pdf", size_bytes: 0, rel_path: "批1/B.pdf" },
    { name: "b.pdf", size_bytes: 0, rel_path: "批2/B.pdf" },    // 0 字节归损坏，不参与重复
    { name: "C.pdf", size_bytes: 5, rel_path: "批1/C.pdf" },    // 单成员不判
  ];
  const groups = pdfDupGroups(list);
  assert.equal(groups.length, 1, "唯一重复组");
  assert.equal(groups[0].name, "A.pdf");
  assert.equal(groups[0].size, 10);
  assert.equal(groups[0].count, 2);
  assert.deepEqual(groups[0].paths, ["批1/A.pdf", "批2/A.pdf"], "组内成员 = 原输入序（稳定）");
});

test("pdfDupGroups 空数组 / 单成员 / 输入序稳定", () => {
  assert.deepEqual(pdfDupGroups([]), []);
  const one = [{ name: "X.pdf", size_bytes: 3, rel_path: "p/X.pdf" }];
  assert.deepEqual(pdfDupGroups(one), []);
  const three = [
    { name: "z.pdf", size_bytes: 9, rel_path: "a/z.pdf" },
    { name: "z.pdf", size_bytes: 9, rel_path: "b/z.pdf" },
    { name: "z.pdf", size_bytes: 9, rel_path: "c/z.pdf" },
  ];
  const groups = pdfDupGroups(three);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].count, 3);
  assert.deepEqual(groups[0].paths, ["a/z.pdf", "b/z.pdf", "c/z.pdf"], "组成员保持输入序");
});

test("pdfHealth 全量派生：dupPaths 集合 + broken 集合（对偶 refDanglingAnchors）", () => {
  const mockPdfs = [
    { name: "B.pdf", size_bytes: 0, rel_path: "批1/B.pdf" },
    { name: "b.pdf", size_bytes: 0, rel_path: "批2/b.pdf" },       // 损坏两份（非重复）
    { name: "A.pdf", size_bytes: 7, rel_path: "批1/A.pdf" },
    { name: "A.pdf", size_bytes: 7, rel_path: "批2/A.pdf" },       // 重复组
    { name: "C.pdf", size_bytes: 7, rel_path: "批1/C.pdf" },       // 健康
  ];
  const h = pdfHealth(mockPdfs);
  assert.equal(h.dupGroups.length, 1);
  assert.ok(h.dupPaths.has("批1/A.pdf") && h.dupPaths.has("批2/A.pdf"), "重复组成员进 dupPaths");
  assert.ok(h.broken.has("批1/B.pdf") && h.broken.has("批2/b.pdf"), "0 字节进 broken");
  assert.equal(h.broken.size, 2);
  assert.ok(!h.dupPaths.has("批1/B.pdf"), "损坏文件不属重复组");
  assert.ok(!h.dupPaths.has("批1/C.pdf"), "健康文件不属于任何组");
});

test("pdfRowHTML 健康徽章：f.isBroken / f.isDup 谓词 → ⚠ 徽章；无谓词不标注", () => {
  // 判据谓词命中场景：size 0（损坏）+ rel_path 命中（重复）
  const p = { name: "A.pdf", rel_path: "批/A.pdf", batch: "批", size_bytes: 0, mtime: 1 };
  const fAll = { isBroken: pdfBroken, isDup: (x) => x.rel_path === "批/A.pdf" };
  const row = pdfRowHTML(p, fAll);
  assert.ok(row.includes("⚠ 损坏"), "损坏徽章（谓词命中）");
  assert.ok(row.includes("⚠ 疑似重复"), "重复徽章（谓词命中）");
  const none = pdfRowHTML(p, {});
  assert.ok(!none.includes("⚠"), "无谓词 = 无徽章（不标注）");
  const fBrokenOnly = { isBroken: pdfBroken, isDup: null };
  const row2 = pdfRowHTML(p, fBrokenOnly);
  assert.ok(row2.includes("⚠ 损坏") && !row2.includes("疑似重复"), "两徽章正交（isDup null 不标）");
});

test("pdfDetailHTML 健康徽章：flags={broken,dup} 标注；缺省不标注", () => {
  const p = { name: "A.pdf", rel_path: "批/A.pdf", batch: "批", size_bytes: 0, mtime: 1 };
  assert.ok(pdfDetailHTML(p, null, { broken: true, dup: false }).includes("⚠ 损坏"), "损坏标注");
  assert.ok(pdfDetailHTML(p, null, { broken: false, dup: true }).includes("⚠ 疑似重复"), "重复标注");
  assert.ok(!pdfDetailHTML(p, null).includes("⚠"), "缺省 flags = 不标注（03 兼容）");
  assert.ok(!pdfDetailHTML(p, null, {}).includes("⚠"), "空 flags = 不标注");
});

// ================= 回收删除（工单 06）：pdfTrashUrl / pdfDupRemainText / pdfTrashConfirmHTML =================
test("pdfTrashUrl 回收端点：逐段编码 + /trash 尾缀", () => {
  assert.equal(pdfTrashUrl("批 A/文件(1).pdf"),
    "/api/pdfs/" + encodeURIComponent("批 A") + "/" + encodeURIComponent("文件(1).pdf") + "/trash");
});

test("pdfDupRemainText 组级文案：组内 N 份 → 删除其余 N-1 份", () => {
  assert.equal(pdfDupRemainText({ count: 2 }), "保留此文件，删除其余 1 份");
  assert.equal(pdfDupRemainText({ count: 3 }), "保留此文件，删除其余 2 份");
  assert.equal(pdfDupRemainText({}), "保留此文件，删除其余 0 份", "缺省 count 防御 = 0 份（不炸）");
});

test("pdfTrashConfirmHTML 单文件：完整路径 / 大小 / 回收去向 / 提示 / 确认取消按钮", () => {
  const p = { name: "A&B.pdf", rel_path: "批一/子/A&B.pdf", batch: "批一", size_bytes: 999, mtime: 1 };
  const d = pdfTrashConfirmHTML(p, "one", null, "sources/.trash-pdf/2026-08-26/批一/子/A&B.pdf");
  assert.ok(d.includes("A&amp;B.pdf"), "文件名 & 应转义");
  assert.ok(d.includes("批一/子/A&amp;B.pdf"), "完整路径（转义）");
  assert.ok(d.includes(formatSize(999)), "大小 = formatSize 口径");
  assert.ok(d.includes("sources/.trash-pdf/2026-08-26/批一/子/A&amp;B.pdf"), "回收去向文案");
  assert.ok(d.includes("git 已忽略"), "回收语义提示（不真删）");
  assert.ok(d.includes("参考库条目引用"), "参考镜像提示");
  assert.ok(d.includes('data-pdf-trash-confirm="批一/子/A&amp;B.pdf"'), "确认按钮数据属性 = rel_path");
  assert.ok(d.includes(">确认删除</button>") && d.includes(">取消</button>"), "按钮文案");
  assert.ok(!d.includes("组内成员"), "单文件模式不列组成员");
});

test("pdfTrashConfirmHTML 组级：组内成员清单 + 确认删除其余按钮", () => {
  const p = { name: "同一.pdf", rel_path: "批一/子/同一.pdf", batch: "批一", size_bytes: 5, mtime: 1 };
  const group = { name: "同一.pdf", size: 5, count: 2, paths: ["批一/子/同一.pdf", "批二/子/同一.pdf"] };
  const d = pdfTrashConfirmHTML(p, "group", group, "sources/.trash-pdf/2026-08-26/批一/子/同一.pdf");
  assert.ok(d.includes("组内成员"), "组成员清单标题");
  assert.ok(d.includes("批一/子/同一.pdf") && d.includes("批二/子/同一.pdf"), "列出全部成员");
  assert.ok(d.includes(">确认删除其余</button>"), "组级确认按钮文案");
  assert.ok(!d.includes("保留此文件，删除其余 1 份"), "组级文案在弹窗头（openPdfTrashConfirm 生成），纯函数体不含");
});

test("pdfDetailHTML flags.group / flags.dup：删除按钮渲染；缺省不渲染", () => {
  const p = { name: "同一.pdf", rel_path: "批一/子/同一.pdf", batch: "批一", size_bytes: 5, mtime: 1 };
  const group = { name: "同一.pdf", size: 5, count: 3, paths: ["批一/子/同一.pdf", "批二/子/同一.pdf", "批三/子/同一.pdf"] };
  const d = pdfDetailHTML(p, null, { broken: false, dup: true, group });
  assert.ok(d.includes('data-pdf-delete="批一/子/同一.pdf"'), "dup → 单删按钮");
  assert.ok(d.includes('data-pdf-delete-group="批一/子/同一.pdf"'), "group → 组级按钮");
  assert.ok(d.includes("保留此文件，删除其余 2 份"), "组级文案 = count-1");
  assert.ok(!pdfDetailHTML(p, null).includes("data-pdf-delete"), "缺省 flags 无删除按钮（03 兼容）");
});

test("pdfRowHTML 重复行渲染删除按钮（data-pdf-trash），非重复行不渲染", () => {
  const dupP = { name: "du.pdf", rel_path: "批/du.pdf", batch: "批", size_bytes: 9, mtime: 1 };
  const dupRow = pdfRowHTML(dupP, { isDup: (x) => x.rel_path === "批/du.pdf" });
  assert.ok(dupRow.includes('data-pdf-trash="批/du.pdf"'), "dup 行删除按钮");
  assert.ok(dupRow.includes(">删除</button>"), "删除按钮文案");
  const plain = pdfRowHTML(dupP, {});
  assert.ok(!plain.includes("data-pdf-trash"), "非重复行无删除按钮");
});
