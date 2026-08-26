// PDF 资料库表格精修纯函数单测（工单 pdf-library-ui/02）：
// pdfSubdir / formatMtime / pdfFilterEntries / pdfSortEntries / pdfStats /
// pdfStatsText / pdfRowHTML。只测外部行为（过滤结果 / 排序 / 统计 / 渲染子串），
// 子串断言防脆。对偶 reference-library.test.mjs 范式。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 reference-library.test.mjs 范式）；deps = 注入的兄弟函数依赖
function extract(name, deps) {
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
        const fnSrc = html.slice(start, i + 1);
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

const esc = extract("esc");
const formatSize = extract("formatSize");
// 依赖顺序：先提取 pdfSubdir / formatMtime，再提取使用它们的函数
const pdfSubdir = extract("pdfSubdir");
const formatMtime = extract("formatMtime");
const pdfFilterEntries = extract("pdfFilterEntries", { pdfSubdir });
const pdfSortEntries = extract("pdfSortEntries", { pdfSubdir });
const pdfStats = extract("pdfStats");
const pdfStatsText = extract("pdfStatsText", { formatSize });
const pdfRowHTML = extract("pdfRowHTML", { esc, formatSize, pdfSubdir, formatMtime });
const pdfChipRowHTML = extract("pdfChipRowHTML", { esc });
// 工单 03：详情弹窗（pdfPagesText 先于 pdfDetailHTML 提取）
const pdfEncodedPath = extract("pdfEncodedPath");
const pdfPagesUrl = extract("pdfPagesUrl", { pdfEncodedPath });
const pdfPagesText = extract("pdfPagesText", { esc });
const pdfDetailHTML = extract("pdfDetailHTML", { esc, formatSize, formatMtime, pdfSubdir, pdfPagesText });

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
