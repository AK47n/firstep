// 参考文件库表格精修纯函数单测（工单 reference-library-ui/02）：
// refFilterEntries / refSortEntries / refStats / refStatsText / refMatchFiles /
// refAnchorBadge / refChipRowHTML / refRowHTML / refDetailHTML。
// 只测外部行为（过滤结果 / 统计数值 / 渲染子串），子串断言防脆。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 module-library.test.mjs 范式）；deps = 注入的兄弟函数依赖
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
const referencePlatformChip = extract("referencePlatformChip", { esc });
const refFilterEntries = extract("refFilterEntries");
const refSortEntries = extract("refSortEntries");
const refStats = extract("refStats");
const refStatsText = extract("refStatsText", { formatSize });
const refMatchFiles = extract("refMatchFiles");
const refAnchorBadge = extract("refAnchorBadge", { esc });
const refChipRowHTML = extract("refChipRowHTML", { esc });
const refRowHTML = extract("refRowHTML", { esc, formatSize, refMatchFiles, refAnchorBadge, referencePlatformChip });
const refDetailHTML = extract("refDetailHTML", { esc, formatSize, refAnchorBadge, referencePlatformChip });

const refs = [
  { id: "adc12", title: "ADC12 例程", type: "例程代码", description: "MSPM0 ADC12 采样例程", anchor_kind: "topic", anchor_value: "2026C", platform: "mspm0", files: ["main.c", "adc.c"], file_count: 2, size_bytes: 4096 },
  { id: "car-1", title: "巡线模板 21F", type: "例程代码", description: "21F 巡线送药决策", anchor_kind: "topic", anchor_value: "21F", platform: "any", files: ["car.py"], file_count: 1, size_bytes: 8192 },
  { id: "alx-uart", title: "ALX 套件 USART", type: "例程代码", description: "STM32F1 串口", anchor_kind: "kit", anchor_value: "ALX-AOA-FIT-套件", platform: "stm32", files: ["usart.c"], file_count: 1, size_bytes: 2048 },
  { id: "manual", title: "K230 资料", type: "说明书", description: "k230 官方源码", anchor_kind: "none", anchor_value: "", platform: "any", files: ["docs/manual.md"], file_count: 1, size_bytes: 1024 },
];

// ================= 过滤：refFilterEntries =================
test("refFilterEntries 关键字：大小写不敏感匹配标题 / 类型 / 锚定值 / 简介 / 文件名", () => {
  assert.deepEqual(refFilterEntries(refs, { q: "adc", platform: "", anchorKind: "" }).map((e) => e.id), ["adc12"]);
  assert.deepEqual(refFilterEntries(refs, { q: "例程", platform: "", anchorKind: "" }).map((e) => e.id), ["adc12", "car-1", "alx-uart"]);
  // 锚定值大小写不敏感（2026C → 2026c）
  assert.deepEqual(refFilterEntries(refs, { q: "2026c", platform: "", anchorKind: "" }).map((e) => e.id), ["adc12"]);
  // 简介命中
  assert.deepEqual(refFilterEntries(refs, { q: "官方", platform: "", anchorKind: "" }).map((e) => e.id), ["manual"]);
  // 文件名命中（含子目录路径）
  assert.deepEqual(refFilterEntries(refs, { q: "usart.c", platform: "", anchorKind: "" }).map((e) => e.id), ["alx-uart"]);
  assert.deepEqual(refFilterEntries(refs, { q: "MANUAL.MD", platform: "", anchorKind: "" }).map((e) => e.id), ["manual"]);
});

test("refFilterEntries 空条件：全量返回（不改原数组）", () => {
  const before = refs.map((e) => e.id);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "", anchorKind: "" }).map((e) => e.id), before);
  assert.deepEqual(refFilterEntries([], { q: "", platform: "", anchorKind: "" }), []);
});

test("refFilterEntries 平台过滤：any / stm32 / mspm0 各自命中", () => {
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "any", anchorKind: "" }).map((e) => e.id), ["car-1", "manual"]);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "stm32", anchorKind: "" }).map((e) => e.id), ["alx-uart"]);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "mspm0", anchorKind: "" }).map((e) => e.id), ["adc12"]);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "megaboard", anchorKind: "" }).map((e) => e.id), []);
});

test("refFilterEntries 锚定类型过滤：topic / kit / none", () => {
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "", anchorKind: "topic" }).map((e) => e.id), ["adc12", "car-1"]);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "", anchorKind: "kit" }).map((e) => e.id), ["alx-uart"]);
  assert.deepEqual(refFilterEntries(refs, { q: "", platform: "", anchorKind: "none" }).map((e) => e.id), ["manual"]);
});

test("refFilterEntries 条件叠加：关键字 + 平台 + 锚定类型同时生效", () => {
  assert.deepEqual(refFilterEntries(refs, { q: "例程", platform: "stm32", anchorKind: "" }).map((e) => e.id), ["alx-uart"]);
  assert.deepEqual(refFilterEntries(refs, { q: "例程", platform: "any", anchorKind: "topic" }).map((e) => e.id), ["car-1"]);
  assert.deepEqual(refFilterEntries(refs, { q: "不存在的词", platform: "", anchorKind: "none" }).map((e) => e.id), []);
});

// ================= 排序：refSortEntries =================
const sortRefs = [
  { id: "b", title: "bravo", type: "t1", platform: "mspm0", size_bytes: 10, file_count: 3, files: [] },
  { id: "a", title: "alpha", type: "t2", platform: "any", size_bytes: 30, file_count: 1, files: [] },
  { id: "c", title: "charlie", type: "t1", platform: "stm32", size_bytes: 20, file_count: 2, files: [] },
  { id: "d", title: "delta", type: "t1", platform: "stm32", size_bytes: 20, file_count: 4, files: [] },
];

test("refSortEntries 标题升/降序；类型同键保持原相对序（稳定排序）", () => {
  assert.deepEqual(refSortEntries(sortRefs, { by: "title", dir: "asc" }).map((e) => e.id), ["a", "b", "c", "d"]);
  assert.deepEqual(refSortEntries(sortRefs, { by: "title", dir: "desc" }).map((e) => e.id), ["d", "c", "b", "a"]);
  // t1 三项 b、c、d：升序保持原相对序；降序同键保持相对序（stable reverse 后仍 b 在 c 前）
  assert.deepEqual(refSortEntries(sortRefs, { by: "type", dir: "asc" }).map((e) => e.id), ["b", "c", "d", "a"]);
  assert.deepEqual(refSortEntries(sortRefs, { by: "type", dir: "desc" }).map((e) => e.id), ["a", "b", "c", "d"]);
});

test("refSortEntries 体量 / 文件数数值排序；平台按词表序", () => {
  assert.deepEqual(refSortEntries(sortRefs, { by: "size", dir: "asc" }).map((e) => e.id), ["b", "c", "d", "a"]);
  assert.deepEqual(refSortEntries(sortRefs, { by: "size", dir: "desc" }).map((e) => e.id), ["a", "c", "d", "b"]);
  assert.deepEqual(refSortEntries(sortRefs, { by: "files", dir: "asc" }).map((e) => e.id), ["a", "c", "b", "d"]);
  // 平台：any < mspm0 < stm32（字母序）；同 stm32 的 c、d 保持原序
  assert.deepEqual(refSortEntries(sortRefs, { by: "platform", dir: "asc" }).map((e) => e.id), ["a", "b", "c", "d"]);
  assert.deepEqual(refSortEntries(sortRefs, { by: "platform", dir: "desc" }).map((e) => e.id), ["c", "d", "b", "a"]);
});

test("refSortEntries 缺省按标题升序；空数组返回空", () => {
  assert.deepEqual(refSortEntries(sortRefs, {}).map((e) => e.id), ["a", "b", "c", "d"]);
  assert.deepEqual(refSortEntries([], { by: "title", dir: "asc" }), []);
});

// ================= 统计：refStats / refStatsText =================
test("refStats 全量统计：总数 / 三平台恒显 / 三锚定类型恒显 / 未锚定数 / 总体积", () => {
  assert.deepEqual(refStats(refs), {
    total: 4,
    platforms: { any: 2, stm32: 1, mspm0: 1 },
    anchorKinds: { topic: 2, kit: 1, none: 1 },
    unanchored: 1,
    totalBytes: 15360,
  });
  assert.deepEqual(refStats([]), {
    total: 0,
    platforms: { any: 0, stm32: 0, mspm0: 0 },
    anchorKinds: { topic: 0, kit: 0, none: 0 },
    unanchored: 0,
    totalBytes: 0,
  });
});

test("refStats 对过滤后子集统计（统计条随过滤联动）", () => {
  const filtered = refFilterEntries(refs, { q: "", platform: "any", anchorKind: "" });
  assert.deepEqual(refStats(filtered), {
    total: 2,
    platforms: { any: 2, stm32: 0, mspm0: 0 },
    anchorKinds: { topic: 1, kit: 0, none: 1 },
    unanchored: 1,
    totalBytes: 8192 + 1024,
  });
});

test("refStatsText 统计条文案：总数 / 平台分布 / 锚定分布 / 总体积", () => {
  const text = refStatsText(refStats(refs));
  assert.ok(text.includes("共 4 条"));
  assert.ok(text.includes("ANY 2"));
  assert.ok(text.includes("STM32 1"));
  assert.ok(text.includes("MSPM0 1"));
  assert.ok(text.includes("赛题 2"));
  assert.ok(text.includes("套件 1"));
  assert.ok(text.includes("未锚定 1"));
  assert.ok(text.includes("15.0 KB"));
  assert.ok(refStatsText(refStats([])).includes("共 0 条"));
});

// ================= 文件名命中：refMatchFiles =================
test("refMatchFiles 文件名命中清单：子串大小写不敏感；空关键字不命中", () => {
  assert.deepEqual(refMatchFiles(refs[0], "adc"), ["adc.c"]);
  assert.deepEqual(refMatchFiles(refs[0], "MAIN"), ["main.c"]);
  assert.deepEqual(refMatchFiles(refs[3], "manual"), ["docs/manual.md"]);
  assert.deepEqual(refMatchFiles(refs[0], ""), []);
  assert.deepEqual(refMatchFiles(refs[0], "z"), []);
  assert.deepEqual(refMatchFiles({ files: [] }, "x"), []);
});

// ================= 锚定徽章：refAnchorBadge =================
test("refAnchorBadge 三态徽章：赛题 / 套件 / 未锚定（值转义）", () => {
  const topic = refAnchorBadge({ anchor_kind: "topic", anchor_value: "2026C" });
  assert.ok(topic.includes("badge ref-topic"));
  assert.ok(topic.includes("赛题"));
  assert.ok(topic.includes("2026C"));
  const kit = refAnchorBadge({ anchor_kind: "kit", anchor_value: "ALX-AOA-FIT-套件" });
  assert.ok(kit.includes("套件"));
  assert.ok(kit.includes("ALX-AOA-FIT-套件"));
  const none = refAnchorBadge({ anchor_kind: "none", anchor_value: "" });
  assert.ok(none.includes("未锚定"));
  // 值转义
  const evil = refAnchorBadge({ anchor_kind: "topic", anchor_value: 'a"b' });
  assert.ok(evil.includes("a&quot;b"));
});

// ================= 过滤 chips：refChipRowHTML =================
test("refChipRowHTML：每项一个按钮、选中项 on 类、计数可带可不带、值转义", () => {
  const out = refChipRowHTML([{ value: "", label: "全部" }, { value: "stm32", label: "STM32", count: 3 }], "stm32");
  const opts = out.split("<button").slice(1);
  assert.equal(opts.length, 2);
  assert.ok(out.includes('data-ref-chip=""'));
  assert.ok(out.includes('data-ref-chip="stm32"'));
  assert.ok(out.includes("STM32（3）"));
  assert.ok(opts[1].split(">")[0].includes('class="lib-chip on"'));
  assert.ok(!opts[0].split(">")[0].includes(" on"));
  const evil = refChipRowHTML([{ value: 'a"b', label: "x" }], "");
  assert.ok(evil.includes('data-ref-chip="a&quot;b"'));
});

// ================= 行渲染：refRowHTML =================
test("refRowHTML 骨干结构：标题截断类 + 全文 tooltip、简介截断类、锚定徽章、体量口径、操作按钮", () => {
  const out = refRowHTML(refs[0], {});
  assert.ok(out.includes('class="ref-title-cell" title="ADC12 例程"'), out);
  assert.ok(out.includes('class="desc-cell" title="MSPM0 ADC12 采样例程"'));
  assert.ok(out.includes("badge ref-topic"));
  assert.ok(out.includes("2 个文件 · 4.0 KB"));
  assert.ok(out.includes('<button data-ref-view="adc12"'));
  assert.ok(out.includes('class="danger" data-ref-del="adc12"'));
});

test("refRowHTML 标题 / 简介特殊字符双转义", () => {
  const out = refRowHTML({ ...refs[0], title: 'a"b', description: 'a<b>&"c\'' }, {});
  assert.ok(out.includes('title="a&quot;b"'));
  assert.ok(out.includes('title="a&lt;b&gt;&amp;&quot;c&#39;"'));
});

test("refRowHTML 文件名命中直出链接（ref-matched + data-mf/data-path）；无命中不渲染", () => {
  const hit = refRowHTML(refs[0], { q: "adc" });
  assert.ok(hit.includes('class="ref-matched"'));
  assert.ok(hit.includes('data-mf="adc12"'));
  assert.ok(hit.includes('data-path="adc.c"'));
  const miss = refRowHTML(refs[0], { q: "zzz" });
  assert.ok(!miss.includes("ref-matched"));
  const noQ = refRowHTML(refs[0], {});
  assert.ok(!noQ.includes("ref-matched"));
});

test("refRowHTML 平台 chip：非 any 显示 <chip out>，any 不显示", () => {
  const mspm0 = refRowHTML(refs[0], {});
  assert.ok(mspm0.includes("mspm0 平台"));
  const any = refRowHTML(refs[1], {});
  assert.ok(!any.includes("chip out"));
});

test("refRowHTML 未锚定条目：徽章为未锚定、锚定值为空不显示", () => {
  const out = refRowHTML(refs[3], {});
  assert.ok(out.includes("未锚定"));
  assert.ok(!out.includes("套件："));
});

// ================= 详情弹窗内容：refDetailHTML =================
test("refDetailHTML 元数据段：标题 / 类型 / 锚定徽章 / 平台 / 简介全文 / 体量 / id", () => {
  const out = refDetailHTML(refs[0], [{ path: "main.c", size_bytes: 100 }, { path: "adc.c", size_bytes: 200 }]);
  assert.ok(out.includes("ADC12 例程"));
  assert.ok(out.includes("例程代码"));
  assert.ok(out.includes("赛题"));
  assert.ok(out.includes("2026C"));
  assert.ok(out.includes("mspm0 平台"));
  assert.ok(out.includes("MSPM0 ADC12 采样例程"));
  assert.ok(out.includes("2 个文件 · 4.0 KB"));
  assert.ok(out.includes("adc12"));
});

test("refDetailHTML 文件清单段：逐文件路径 + 大小 + 打开链接；空清单提示", () => {
  const out = refDetailHTML(refs[0], [{ path: "main.c", size_bytes: 100 }]);
  assert.ok(out.includes('data-path="main.c"'));
  assert.ok(out.includes("main.c"));
  assert.ok(out.includes("100 B"));
  const empty = refDetailHTML(refs[0], []);
  assert.ok(empty.includes("无文件"));
});
