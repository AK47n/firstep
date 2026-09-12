// 模块说明入口单测（工单 module-intro-detail/03）：推荐区/组卡/已选清单点「说明」
// 弹出的内容 = 讲人话的四问分段 + 「为什么推荐它」+ 既有内部字段；三处入口的
// 渲染与接线都钉住（防回退到「只有 slug + 一句短线代号」）。
// 直接 import fx/module.js（不字符串提取）；接线断言按归属读 ui/generate-recommend.js。
// 运行：node --test "tests/js/*.test.mjs"
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import {
  moduleInfoHTML,
  moduleIntroHTML,
  moduleReasonHTML,
  moduleInfoBtnHTML,
  recommendChipHTML,
  renderGroupCards,
  groupRequirementNote,
  MODULE_INFO_BTN_TEXT,
  MODULE_INFO_BTN_TITLE,
} from "../../src/contest_generator/static/js/fx/module.js";

const src = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
  "utf8"
);

// 载荷形状与 /api/modules 投影一致（intro 由后端 module_intro 拆段下发）
const irBeam = {
  slug: "ir_beam",
  kind: "device",
  requires_identity: false,
  description: "红外对射传感器：……",
  intro: [
    { label: "这是干什么的", text: "红外对射传感器：一对红外发射管和接收管相对安装" },
    { label: "怎么接线", text: "三线制接线（VCC 电源 / GND 地 / OUT 信号），只占 1 个 GPIO" },
    { label: "怎么用（接口）", text: "ir_beam_init() 初始化、ir_beam_read() 读一次状态" },
    { label: "什么时候用", text: "适用于物体经过检测、防夹等赛题功能" },
  ],
  platforms: {
    stm32: { files: ["code/ir_beam.c"], verified: true, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] },
  },
};

test("moduleIntroHTML：四问分段各自成块（标题 + 正文）", () => {
  const out = moduleIntroHTML(irBeam.intro);
  for (const s of irBeam.intro) {
    assert.ok(out.includes(s.label), "缺标题 " + s.label);
    assert.ok(out.includes(s.text), "缺正文 " + s.text);
  }
  // 顺序按载荷（后端定序，前端不重排）
  assert.ok(out.indexOf("这是干什么的") < out.indexOf("怎么接线"));
  assert.ok(out.indexOf("怎么接线") < out.indexOf("怎么用（接口）"));
  assert.ok(out.indexOf("怎么用（接口）") < out.indexOf("什么时候用"));
  assert.equal((out.match(/mi-intro-sec/g) || []).length, 4);
});

test("moduleIntroHTML：旧载荷无 intro / 空数组 / 脏条目 → 空串（回落原样简介）", () => {
  assert.equal(moduleIntroHTML(undefined), "");
  assert.equal(moduleIntroHTML(null), "");
  assert.equal(moduleIntroHTML([]), "");
  // 缺 label 或 text 的脏条目不渲染（不产出空标题）
  assert.equal(moduleIntroHTML([{ label: "", text: "x" }, { label: "怎么接线", text: "" }]), "");
});

test("moduleIntroHTML：转义（简介与标签里的 HTML 字符不成为可交互标签）", () => {
  const out = moduleIntroHTML([
    { label: "这是干什么的", text: '<script>alert(1)</script> & "引号"' },
  ]);
  assert.ok(out.includes("&lt;script&gt;"));
  assert.ok(!out.includes("<script>"));
  assert.ok(out.includes("&amp;"));
  assert.ok(out.includes("&quot;"));
});

test("moduleReasonHTML：有理由 = 「为什么推荐它」段；无理由 = 空串（不编造）", () => {
  const out = moduleReasonHTML("可选点/起始做辅助");
  assert.ok(out.includes("为什么推荐它"));
  assert.ok(out.includes("可选点/起始做辅助"));
  // 模块库页打开时没有推荐理由 → 不渲染该段
  assert.equal(moduleReasonHTML(""), "");
  assert.equal(moduleReasonHTML("   "), "");
  assert.equal(moduleReasonHTML(undefined), "");
  // 理由里的 HTML 字符被转义
  assert.ok(moduleReasonHTML("<b>x</b>").includes("&lt;b&gt;"));
});

test("moduleInfoHTML：说明弹窗 = 四问分段 + 推荐理由 + 既有内部字段（引脚/源码/链接）", () => {
  const out = moduleInfoHTML({ ...irBeam, kit: "" }, "stm32", "可选点/起始做辅助");
  // 讲人话部分（第一眼要看的）
  assert.ok(out.includes("这是干什么的"));
  assert.ok(out.includes("怎么接线"));
  assert.ok(out.includes("为什么推荐它"));
  // 内部字段仍在（老信息零丢失）
  assert.ok(out.includes("ir_beam.c"));
  assert.ok(out.includes("mi-plat"));
  // 分段块在平台字段之前（用户先看到「是什么」）
  assert.ok(out.indexOf("mi-intro") < out.indexOf("mi-plat"));
});

test("moduleInfoHTML：旧载荷（无 intro）+ 无理由 → 零分段零报错，原样简介兜底", () => {
  const legacy = {
    slug: "oled", description: "OLED 显示驱动",
    platforms: { stm32: { files: [], verified: true, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } },
  };
  const out = moduleInfoHTML(legacy, "stm32");
  assert.ok(out.includes("OLED 显示驱动"));
  assert.ok(!out.includes("mi-intro"));
  assert.ok(!out.includes("为什么推荐它"));
});

test("moduleInfoHTML：有分段就不重复印整段简介（同一段话不连读两遍）", () => {
  const out = moduleInfoHTML(irBeam, "stm32", "可选点/起始做辅助");
  // 有 intro → 标题下不再重复整段 description（分段就是它拆出来的）
  assert.ok(!out.includes("红外对射传感器：……"), "整段简介不该与分段并列重复");
  assert.equal((out.match(/红外对射传感器：一对红外发射管/g) || []).length, 1);
  // 无 intro 的旧载荷 → 整段简介仍在（弹窗不会变成「只有 slug 的空壳」）
  const legacy = moduleInfoHTML({ slug: "oled", description: "OLED 显示驱动", platforms: {} }, "stm32");
  assert.ok(legacy.includes("OLED 显示驱动"));
});

test("moduleInfoBtnHTML：说明按钮独立于 chip 本体（data-mod-info + 文案单源 + 转义）", () => {
  const out = moduleInfoBtnHTML("ir_beam");
  assert.ok(out.includes('data-mod-info="ir_beam"'));
  assert.ok(out.includes('type="button"'));
  assert.ok(out.includes(MODULE_INFO_BTN_TEXT));
  assert.ok(out.includes(MODULE_INFO_BTN_TITLE));
  assert.ok(!out.includes("data-remove"), "说明按钮不能带移除语义");
  assert.ok(moduleInfoBtnHTML("<x>").includes("&lt;x&gt;"));
});

test("recommendChipHTML：chip 带说明按钮，选择态按 selected 渲染（工单 06）", () => {
  // 已选（默认）：绿底 + ✕ 移除语义
  const on = recommendChipHTML("ir_beam", "可选点/起始做辅助");
  assert.ok(on.includes('class="chip rec"'), "缺省 = 已选，类名不带 unsel");
  assert.ok(on.includes('data-remove="ir_beam"'), "chip 本体仍是选择开关");
  assert.ok(on.includes('data-mod-info="ir_beam"'), "chip 内有说明入口");
  assert.ok(on.includes("可选点/起始做辅助"));
  assert.ok(on.includes("✕"));
  assert.match(on, /点击从工程里移除/);
  // 未选（用户点掉了它）：灰显虚线 + ＋ 加回语义
  const off = recommendChipHTML("ir_beam", "可选点/起始做辅助", false);
  assert.ok(off.includes("chip rec unsel"), "未选态要带 unsel 类（灰显虚线）");
  assert.ok(off.includes("＋"), "未选态显示加回符号");
  assert.ok(!off.includes("✕"), "未选态不该再显示移除符号");
  assert.match(off, /已从工程移除，点击加回/);
  // 两侧都保留说明入口与理由
  assert.ok(off.includes('data-mod-info="ir_beam"'));
  assert.ok(off.includes("可选点/起始做辅助"));
  assert.ok(recommendChipHTML("led", "").includes('data-mod-info="led"'));
});

test("generate-recommend.js：展开并发收口——排队 + 令牌作废旧响应（工单 07 / 09）", () => {
  // 原实现是 `if (expandBusy) return;` 静默丢弃：展开途中再改选择集 → 那次展开永不发生，
  // 旧响应落地还会覆盖成旧集合（真机实测：点回 chip 后 120ms 已选清单只剩 motor）。
  assert.match(src, /let expandSeq = 0/);
  assert.match(src, /let expandPending = false/);
  assert.match(src, /if \(expandBusy\) \{ expandPending = true; return; \}/);
  // 结果落地前判令牌 + 请求体快照（双保险）
  assert.match(src, /token > expandApplied && snapshot === JSON\.stringify/);
  // 收尾判据（工单 09 起）单一来源在 fx 层：三结局（applied / discarded / failed）
  // 的后续动作由 expandOutcomeDecision 决定——**不许**在 ui 层再合并成一个 `!ok`
  assert.match(src, /expandOutcomeDecision\(outcome, \{/);
  assert.match(src, /if \(decision\.retry\) void runExpand\(\)/);
  assert.ok(!/\(\s*expandPending\s*\|\|\s*!ok\s*\)/.test(src),
    "ui 层又出现「pending || !ok」合并重跑 = 失败也被重跑（自激根因，工单 09）");
  // 选择集变化后必须重跑展开（否则停在「已选（未展开依赖）」）
  assert.match(src, /renderRecommendResult\(lastRecommend, false\);\n  runExpand\(\);/);
});

test("generate-recommend.js：chip 渲染带选择态 + 点击是双向开关（工单 06）", () => {
  // 渲染必须按 selectedSlugs 判选择态——照 done 载荷的 modules 渲染 = 点掉后仍显示已选
  assert.match(src, /recommendChipHTML\(slug, reason, on\)/);
  assert.match(src, /const on = selectedSlugs\.includes\(slug\)/);
  // 点击双向：已选 → 移除；未选 → 加回（否则点掉了再也加不回来）
  assert.match(src, /if \(selectedSlugs\.includes\(slug\)\)/);
  assert.match(src, /addModule\(slug, false\)/);
  assert.match(src, /classList\.contains\("unsel"\)/);
});

// ===== 已选清单的「点掉之后」时序（工单 module-intro-detail/08 调查结论）=====
// 曾疑为 bug：点掉 chip 后、新 expand 回来之前，已选清单会显示**过期**的展开结果
// （真机时间线里 t+139ms 那帧看起来像「已移除的 ir_beam 还在清单里」）。
// **结论：不成立——那是我自己的判据误报**。复现实验：
//   ① 把 renderSelected 临时改回原实现的两行分支形状（`if (!expanded.length) …`），
//      真机时间线仍然**只在占位里列出当前选择**（`已选（未展开依赖）：pid、motor`），
//      从未渲染出 ir_beam 的行；
//   ② 把「点掉后无条件按 expanded 渲染」作为反例注入 → 清单变成**空**（不是过期行），
//      因为 `reRenderAfterSelectionChange` 已经先清了 expanded；
//   ③ 读码确认：点击路径（chip 移除 / 组卡换选）清 `expanded` **早于**任何 renderSelected，
//      renderSelected 拿到的 expanded 只可能是「空」或「本次/上次请求落地的新结果」。
// 故此处**只留判据**：清单里的占位文案必须逐字等于当前选择，且不得出现被点掉的模块——
// 用一个纯函数把它钉住（它描述的是既有行为，不是新增代码）。
const pendingText = (selected) => (selected.length
  ? "已选（未展开依赖）：" + selected.join("、")
  : "尚未选择模块。");

test("已选清单占位文案：逐字等于当前选择，且不含被点掉的模块（工单 08 判据）", () => {
  assert.equal(pendingText(["pid", "motor"]), "已选（未展开依赖）：pid、motor");
  assert.ok(!pendingText(["pid", "motor"]).includes("ir_beam"),
    "占位文案带上了已移除的模块 = 界面与工程不一致（本判据就是当初误报的那条）");
  assert.equal(pendingText([]), "尚未选择模块。");
});

test("generate-recommend.js：点击路径清 expanded 必须**早于**渲染（工单 08 的根因判据）", () => {
  // 这是「点掉后清单不会显示过期结果」的**真正保障**：先把 expanded 清掉再重绘。
  // 一旦有人把顺序调换（先渲染再清），上面那条占位判据就会被打破。
  assert.match(src, /expanded = \[\]; warnings = \[\];\s*\n\s*renderSelected\(\); renderWarnings\(\); renderRecommendResult\(lastRecommend, false\);/,
    "reRenderAfterSelectionChange 的「先清后渲染」顺序被改了 —— 点掉模块后清单可能显示过期展开结果");
});

test("三处入口都出说明按钮：推荐 chip / 功能组卡成员行 / 需求清单灰注", () => {
  const groups = [{
    id: "gray-track", label: "8 路灰度传感器驱动", hint: false, choice_required: true,
    members: [{ slug: "huidu", role: "仅 8 路灰度读取" }, { slug: "pid", role: "灰度 + PID 巡线" }],
    recommended: ["pid"],
  }];
  const cards = renderGroupCards(groups, [{ slug: "pid", reason: "PID 循迹" }], []);
  assert.ok(cards.includes('data-mod-info="huidu"'), "组卡成员行缺说明入口");
  assert.ok(cards.includes('data-mod-info="pid"'));
  // 需求清单里进了功能组的模块走灰注，灰注同样带说明入口
  const note = groupRequirementNote(groups, "pid", "PID 循迹", {});
  assert.ok(note.includes('data-mod-info="pid"'));
  assert.ok(note.includes("请选择"));
});

test("generate-recommend.js 接线：委托绑定 + stopPropagation + 已选清单行入口", () => {
  // 三处入口统一走 data-mod-info 委托（innerHTML 全量重绘后仍有效）
  assert.match(src, /bindModuleInfoEntry\(box\)/);
  assert.match(src, /closest\("\[data-mod-info\]"\)/);
  // 说明按钮嵌在 .chip.rec（data-remove）里，且 chip 的移除监听挂在 chip 本体上
  // ——同一元素的监听属 target 阶段，先于容器冒泡监听 → **必须捕获阶段**才拦得住
  // （真机验收抓到过：冒泡阶段 stopPropagation 时模块已被移除）
  assert.match(src, /ev\.stopPropagation\(\)/);
  assert.match(src, /\}, true\);/);
  assert.match(src, /ev\.preventDefault\(\)/);
  // 已选清单行带说明按钮
  assert.match(src, /moduleInfoBtnHTML\(m\.slug\)/);
  // 弹窗标题与推荐理由（chip 上那句短线代号在弹窗里有上下文）
  assert.match(src, /moduleInfoHTML\(module, platform, reason\)/);
  assert.match(src, /moduleInfoReason\(btn\.dataset\.modInfo\)/);
  assert.match(src, /function moduleInfoReason\(slug\)/);
});
