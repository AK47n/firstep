// 参考文件库表格精修纯函数单测（工单 reference-library-ui/02）：
// refFilterEntries / refSortEntries / refStats / refStatsText / refMatchFiles /
// refAnchorBadge / refChipRowHTML / refRowHTML / refDetailHTML + 编辑弹窗 /
// 悬空锚定 / referencePlatformChip。
// 只测外部行为（过滤结果 / 统计数值 / 渲染子串），子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  referencePlatformChip, referenceTopicTypeChip, refFilterEntries, refDanglingAnchors, refSortEntries,
  refStats, refStatsText, refMatchFiles, refAnchorBadge, refChipRowHTML,
  refRowHTML, refDetailHTML, refEditState, refEditValidate, refEditFilePlan,
  refEditPayload,
} from "../../src/contest_generator/static/js/fx/reference.js";

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

test("refSortEntries mtime（最近更新）：数值排序、缺失垫底、降序最新在前", () => {
  const refs = [
    { id: "x", title: "x", mtime: 10 },
    { id: "y", title: "y", mtime: 30 },
    { id: "z", title: "z" },
  ];
  assert.deepEqual(refSortEntries(refs, { by: "mtime", dir: "asc" }).map((e) => e.id), ["z", "x", "y"]);
  assert.deepEqual(refSortEntries(refs, { by: "mtime", dir: "desc" }).map((e) => e.id), ["y", "x", "z"]);
});

// ================= 统计：refStats / refStatsText =================
test("refStats 全量统计：总数 / 三平台恒显 / 三锚定类型恒显 / 未锚定数 / 总体积", () => {
  assert.deepEqual(refStats(refs), {
    total: 4,
    platforms: { any: 2, stm32: 1, mspm0: 1 },
    anchorKinds: { topic: 2, kit: 1, none: 1 },
    unanchored: 1,
    totalBytes: 15360,
    dangling: 0,
  });
  assert.deepEqual(refStats([]), {
    total: 0,
    platforms: { any: 0, stm32: 0, mspm0: 0 },
    anchorKinds: { topic: 0, kit: 0, none: 0 },
    unanchored: 0,
    totalBytes: 0,
    dangling: 0,
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
    dangling: 0,
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
  assert.ok(out.includes('<button data-ref-edit="adc12"'));
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

// ================= 编辑弹窗纯函数（工单 03） =================

test("refEditState 状态机：idle→saving→ok/rejected；reset 回 idle；非法事件保持原态", () => {
  assert.equal(refEditState("idle", "save"), "saving");
  assert.equal(refEditState("saving", "saved"), "ok");
  assert.equal(refEditState("saving", "error"), "rejected");
  assert.equal(refEditState("ok", "reset"), "idle");
  assert.equal(refEditState("rejected", "reset"), "idle");
  // 非 saving 态收 saved / error 不动
  assert.equal(refEditState("idle", "saved"), "idle");
  assert.equal(refEditState("ok", "error"), "ok");
  assert.equal(refEditState("idle", "error"), "idle");
  // 非法事件保持原态
  assert.equal(refEditState("idle", "boom"), "idle");
  assert.equal(refEditState("saving", "boom"), "saving");
  // save 事件不校验来源态（对偶 editDescStatus：重入由保存按钮禁用承担）
  assert.equal(refEditState("saving", "save"), "saving");
});

test("refEditValidate 校验：标题 / 类型 / 简介非空（strip 后）；topic/kit 锚定须给值", () => {
  const base = { title: "t", type: "例程代码", description: "d", anchor_kind: "none", anchor_value: "" };
  assert.deepEqual(refEditValidate(base), { ok: true, message: "" });
  assert.equal(refEditValidate({ ...base, title: "  " }).ok, false);
  assert.ok(refEditValidate({ ...base, title: "  " }).message.includes("标题"));
  assert.equal(refEditValidate({ ...base, type: "" }).ok, false);
  assert.equal(refEditValidate({ ...base, description: "   " }).ok, false);
  assert.equal(refEditValidate({ ...base, anchor_kind: "topic", anchor_value: "" }).ok, false);
  assert.equal(refEditValidate({ ...base, anchor_kind: "kit", anchor_value: " " }).ok, false);
  assert.equal(refEditValidate({ ...base, anchor_kind: "topic", anchor_value: "2026C" }).ok, true);
  assert.equal(refEditValidate({ ...base, anchor_kind: "kit", anchor_value: "ALX 套件" }).ok, true);
});

test("refEditFilePlan 文件计划：增删透传；同名新增 = 覆盖（一次保存）；同名且勾删 = 覆盖优先剔除删除", () => {
  const plan = refEditFilePlan(["a.c", "b.c"], ["a.c"], { "c.c": "int x;", "d.c": "int y;" });
  assert.deepEqual(plan, { ok: true, add_files: { "c.c": "int x;", "d.c": "int y;" }, remove_files: ["a.c"] });
  assert.deepEqual(refEditFilePlan(["a.c"], [], {}), { ok: true, add_files: {}, remove_files: [] });
  assert.deepEqual(refEditFilePlan([], [], {}), { ok: true, add_files: {}, remove_files: [] });
  // 同名新增（未勾删）→ ok，add_files 含同名（后端 upsert 覆盖内容，工单 ux-walkthrough-02/08）
  const overwrite = refEditFilePlan(["a.c"], [], { "a.c": "new" });
  assert.deepEqual(overwrite, { ok: true, add_files: { "a.c": "new" }, remove_files: [] });
  // 同名既勾删又新增 → 覆盖优先：删除清单剔除同名，add 保留
  const both = refEditFilePlan(["a.c"], ["a.c"], { "a.c": "new" });
  assert.deepEqual(both, { ok: true, add_files: { "a.c": "new" }, remove_files: [] });
  // 勾删的路径不在既有清单（外部删除）：透传，存在性由后端裁决
  const stale = refEditFilePlan(["a.c"], ["gone.c"], {});
  assert.deepEqual(stale, { ok: true, add_files: {}, remove_files: ["gone.c"] });
});

test("refEditPayload 组装：元数据全量（trim）；topic 取 topic 值、kit 取 kit 值、none 强制空；题型透传；文件计划透传", () => {
  const plan = { ok: true, add_files: { "a.c": "x" }, remove_files: ["b.c"] };
  const fields = { title: " t ", type: "例程代码", description: " d ", anchor_kind: "topic", anchor_value: " 2026C ", platform: "mspm0", topic_type: " line_follow " };
  assert.deepEqual(refEditPayload(fields, plan), {
    title: "t", type: "例程代码", description: "d",
    anchor_kind: "topic", anchor_value: "2026C", platform: "mspm0", topic_type: "line_follow",
    add_files: { "a.c": "x" }, remove_files: ["b.c"],
  });
  const kit = refEditPayload({ ...fields, anchor_kind: "kit", anchor_value: " ALX 套件 " }, plan);
  assert.equal(kit.anchor_value, "ALX 套件");
  const none = refEditPayload({ ...fields, anchor_kind: "none", anchor_value: "ignored" }, plan);
  assert.equal(none.anchor_value, "");
  assert.equal(none.anchor_kind, "none");
});

// ================= 悬空锚定警示（工单 04） =================
const drefs = [
  { id: "ok-topic", title: "赛题命中", anchor_kind: "topic", anchor_value: "2026C" },
  { id: "dang-topic", title: "悬空赛题", anchor_kind: "topic", anchor_value: "1999Z" },
  { id: "ok-kit", title: "套件命中", anchor_kind: "kit", anchor_value: "ALX-AOA-FIT-套件" },
  { id: "dang-kit", title: "悬空套件", anchor_kind: "kit", anchor_value: "不存在的套件" },
  { id: "none", title: "未锚定", anchor_kind: "none", anchor_value: "" },
];

test("refDanglingAnchors topic 方向：库内存在赛题 key 是锚定值子串 = 不悬空；否则悬空", () => {
  const tk = ["2026C", "2026H", "21F"];
  // 命中（key in anchor_value）；锚定值带前后缀也能命中
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "topic", anchor_value: "2026C" }], tk, []).map((e) => e.id), []);
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "topic", anchor_value: "2026C-巡线模板" }], tk, []), []);
  assert.deepEqual(refDanglingAnchors([{ id: "x", anchor_kind: "topic", anchor_value: "1999Z" }], tk, []).map((e) => e.id), ["x"]);
});

test("refDanglingAnchors kit 方向：与生成侧同构子串判定（词表值 in 锚定值 = 会关联不悬空）；空词表降级不报", () => {
  const kv = ["ALX-AOA-FIT-套件", "塔克R3-DB20"];
  // 精确值 = 词表值是锚定值子串 → 命中不悬空
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "kit", anchor_value: "ALX-AOA-FIT-套件" }], [], kv), []);
  // 锚定值带前后缀（如 ALX-套件-v2）：生成侧 search_references 走子串仍会关联 → 不算悬空
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "kit", anchor_value: "ALX-AOA-FIT-套件-核心子集" }], [], kv), []);
  // 词表内无任何值是锚定值子串 = 悬空
  assert.equal(refDanglingAnchors([{ anchor_kind: "kit", anchor_value: "没有这个套件" }], [], kv).length, 1);
  // 降级：词表空 = 跳过 kit 方向检查（零误报）
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "kit", anchor_value: "任意值" }], [], []), []);
});

test("refDanglingAnchors 集合判定：none 不参与；空 key 忽略；topic 侧赛题库空降级", () => {
  const out = refDanglingAnchors(drefs, ["2026C", "21F"], ["ALX-AOA-FIT-套件"]);
  assert.deepEqual(out.map((e) => e.id), ["dang-topic", "dang-kit"]);
  // none 条目（含空锚定值）永不悬空
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "none", anchor_value: "" }], [], []), []);
  // 空 key 不参与子串匹配（"".indexOf 恒 0 会误命中）
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "topic", anchor_value: "2026C" }], [""], []), []);
  // 赛题库空 = topic 方向降级不报
  assert.deepEqual(refDanglingAnchors([{ anchor_kind: "topic", anchor_value: "2026C" }], [], []), []);
});

test("refFilterEntries 悬空过滤（dangling 维度）：与平台/关键字正交组合", () => {
  const base = { q: "", platform: "", anchorKind: "", dangling: true, topicKeys: ["2026C", "21F"], kitVocab: ["ALX-AOA-FIT-套件"] };
  const out = refFilterEntries(drefs, base).map((e) => e.id);
  assert.deepEqual(out, ["dang-topic", "dang-kit"]);
  // 平台正交
  const mspm0 = refFilterEntries(drefs, { ...base, platform: "mspm0" });
  assert.deepEqual(mspm0, []);
  // 关键字正交（dangling + q 命中「悬空」）
  const q = refFilterEntries(drefs, { ...base, q: "悬空" });
  assert.deepEqual(q.map((e) => e.id), ["dang-topic", "dang-kit"]);
  // dangling=false = 不限制（与既有行为一致）
  const off = refFilterEntries(drefs, { q: "", platform: "", anchorKind: "", dangling: false, topicKeys: ["2026C"], kitVocab: [] });
  assert.deepEqual(off.map((e) => e.id), drefs.map((e) => e.id));
});

test("refRowHTML 悬空标注：锚定列 ⚠（title 解释「不会自动关联」）；非悬空 / 无词表上下文不渲染", () => {
  const f = { topicKeys: ["2026C", "21F"], kitVocab: ["ALX-AOA-FIT-套件"] };
  const dang = refRowHTML({ id: "d1", title: "t", type: "例程", description: "d", anchor_kind: "kit", anchor_value: "没有这个套件", platform: "any", files: [], file_count: 0, size_bytes: 0 }, f);
  assert.ok(dang.includes("ref-dangling-tag"));
  assert.ok(dang.includes("不会自动关联"));
  const ok = refRowHTML({ ...refs[0], anchor_kind: "topic", anchor_value: "2026C" }, f);
  assert.ok(!ok.includes("ref-dangling-tag"));
  // 无词表上下文（数据未就绪）时降级不渲染 ⚠
  const noctx = refRowHTML({ id: "d2", title: "t", type: "例程", description: "d", anchor_kind: "topic", anchor_value: "2026C", platform: "any", files: [], file_count: 0, size_bytes: 0 }, {});
  assert.ok(!noctx.includes("ref-dangling-tag"));
});

test("refStats 悬空计数（ctx 契约）：含 ctx 算 dangling / 缺 ctx 零误报", () => {
  const ctx = { topicKeys: ["2026C", "21F"], kitVocab: ["ALX-AOA-FIT-套件"] };
  const s = refStats(drefs, ctx);
  assert.equal(s.dangling, 2);
  assert.equal(s.total, drefs.length);
  // 无 ctx（or 词表空）→ dangling 0（降级不误报）
  assert.equal(refStats(drefs).dangling, 0);
  assert.equal(refStats(drefs, { topicKeys: [], kitVocab: [] }).dangling, 0);
});

// ================= 题型标记（工单 topic-framework/04） =================

test("referenceTopicTypeChip：topic_type 非空 → <题型> 框架 chip；空 → 不渲染", () => {
  assert.ok(referenceTopicTypeChip({ topic_type: "line_follow" }).includes("line_follow 框架"));
  assert.ok(referenceTopicTypeChip({ topic_type: "generic" }).includes("generic 框架"));
  assert.equal(referenceTopicTypeChip({ topic_type: "" }), "");
  assert.equal(referenceTopicTypeChip({}), "");
});

test("refRowHTML 题型列：非空题型渲染题型单元格；空 → — 占位", () => {
  const typed = refRowHTML({ ...refs[0], topic_type: "line_follow" }, {});
  assert.ok(typed.includes(">line_follow<"));
  const untyped = refRowHTML({ ...refs[0], topic_type: "" }, {});
  assert.ok(untyped.includes("—"));
  assert.ok(!untyped.includes("line_follow"));
});

test("refDetailHTML 锚定行带题型 chip（类型标注可见）", () => {
  const detail = refDetailHTML({ ...refs[1], topic_type: "line_follow" }, []);
  assert.ok(detail.includes("line_follow 框架"));
});
