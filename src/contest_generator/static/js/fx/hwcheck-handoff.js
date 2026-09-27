// fx/hwcheck-handoff.js — 硬件检测栏目的纯函数：**检测页 → 生成页衔接（只带器件，不带引脚）**。
//
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。
// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，
// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。

import { esc } from "./core.js";
// 器件 slug 归一与平台展示名归 state（衔接的两条判据都要它们）。
import { hwcheckDeviceSlugs, hwcheckPlatformLabel } from "./hwcheck-state.js";

// ===========================================================================
// 工单 hwcheck-acceptance/04：检测页 → 生成页的衔接（只带器件，不带引脚）
//
// 页面上的一个动作：把**当前选中的库内器件**并进生成页的已选清单——学生在检测页
// 验通一件之后不用回生成页再找一遍同名模块。三条判据都在本文件（纯函数，数组 /
// 字符串进出，零 DOM 零请求），因为它们是"该不该进生成载荷"的判据：
//   ① **只带库内件**：「我的器件」（库外自建件）**不走生成链**——它没有 manifest、
//      不进 slugs，生成链上游（`resolve_dependencies`）会直接拒；带过去等于把
//      一个必然 400 的 slug 塞进载荷。
//   ② **逐个过库内词表**：不在词表里的 slug 一件都不许带（"点了没反应"与"生成时
//      才 400"两种分家都从这一处杜绝），并逐件给出中文理由。
//   ③ **引脚不带**：检测页没有引脚配置入口，而生成前自动移开的那几根线是**这一页
//      的本地裁决**（不是用户做出的选择）——带过去就是把没做过的决定塞进生成页。
//      页面上必须自己把这条说清楚（学生照着检测页的接线表接好线，却以为生成页
//      会用同一组脚，是最难查的一类不一致）。
//
// **"库外件"的判据不写成 id 前缀**（`mine_`）：前缀是 `my_devices.DEVICE_ID_PATTERN`
// 的事，页面再判一遍就是第二份实现（改了文法两处必然分叉）。这里判的是"它在不在
// 自建件清单里"——清单来自服务端载荷。
// ===========================================================================

// hwcheckHandoffPlan(devices, librarySlugs, myDevices)：把选中的器件分成三类。
//   devices      = 当前选中的 slug（去重保序，与请求载荷同一个取法）
//   librarySlugs = 库内 slug 词表（模块库真源）
//   myDevices    = 「我的器件」清单（[{id, name}]，服务端载荷）
// → { carry: [slug…], custom: [{id, name}…], unknown: [slug…] }
// 分类**先判词表**：slug 同时在两处时按"库内"算（生成链认的是词表；自建件撞库内
// slug 在保存那一步就被服务端拒了，这条只是把顺序钉死，不留两种答案）。
export function hwcheckHandoffPlan(devices, librarySlugs, myDevices) {
  const known = new Set(
    (Array.isArray(librarySlugs) ? librarySlugs : [])
      .map((slug) => String(slug == null ? "" : slug)).filter(Boolean));
  const mine = new Map();
  (Array.isArray(myDevices) ? myDevices : []).forEach((item) => {
    const id = String((item && item.id) || "");
    if (id) mine.set(id, String((item && item.name) || ""));
  });
  const carry = []; const custom = []; const unknown = [];
  hwcheckDeviceSlugs({ devices }).forEach((slug) => {
    if (known.has(slug)) carry.push(slug);
    else if (mine.has(slug)) custom.push({ id: slug, name: mine.get(slug) });
    else unknown.push(slug);
  });
  return { carry, custom, unknown };
}

// hwcheckHandoffMerge(selected, carry)：把要带的几件**并进**生成页的已选清单。
// → { selected: […], added: […], already: […] }
//
// 生成页那侧的 selectedSlugs 由推荐簇 A 持有（唯一写者），本函数只算"并进去之后
// 长什么样"——于是"不重复加、保持原顺序、已选过的如实报 already"这三条规则可直测，
// ui 侧只剩写状态 + 重绘（双轴评审整改：原来那条 ui 断言在数 runExpand() 出现几次，
// 那是实现细节，不是行为）。
export function hwcheckHandoffMerge(selected, carry) {
  const out = (Array.isArray(selected) ? selected : [])
    .map((slug) => String(slug == null ? "" : slug)).filter(Boolean);
  // `already` 的判据 = **本来就在生成页里**，所以拿入参那份快照比——不能拿边算边长的
  // out 比：入参里重复出现的同一件会被算成"本来就在"，那是句假话。
  const base = new Set(out);
  const added = []; const already = [];
  (Array.isArray(carry) ? carry : []).forEach((slug) => {
    const key = String(slug == null ? "" : slug);
    if (!key) return;
    if (base.has(key)) {
      if (!already.includes(key)) already.push(key);
      return;
    }
    if (out.includes(key)) return;   // 入参里重复的一件：只加一次，也不假报 already
    out.push(key);
    added.push(key);
  });
  return { selected: out, added, already };
}

// hwcheckHandoffPinNote()：**引脚那一句的唯一出处**——带入块里那句与带过去之后
// 回报那句同源（两处各写一句必然分叉；先例见 fx/my-devices.js 文件头的「文案单源」）。
export function hwcheckHandoffPinNote() {
  return "只带器件、不带引脚（引脚到生成页第 7 步再配）";
}

// hwcheckHandoffResultText(added, already)：带过去之后那一句回报（ui 只把它塞进
// toast，不自己拼文案）。两段都可能为空（第二次点同一批 = added 空、already 满），
// 但引脚那一句**恒在**——"带过去的东西里没有引脚"这件事每次都要说。
export function hwcheckHandoffResultText(added, already) {
  const add = (Array.isArray(added) ? added : []).filter(Boolean);
  const had = (Array.isArray(already) ? already : []).filter(Boolean);
  const parts = [];
  if (add.length) parts.push("已带进生成页 " + add.length + " 件：" + add.join("、"));
  if (had.length) parts.push("另有 " + had.length + " 件本来就在工程里：" + had.join("、"));
  parts.push(hwcheckHandoffPinNote());
  return parts.join("；");
}

// hwcheckHandoffHTML(plan, opts)：带入块（说明 + 一个按钮）。
//
// opts = {
//   pinFixes:  这一趟生成前自动移开的默认脚冲突处数（wiring.pin_fixes 的长度；
//              0 = 还没取到接线表 / 一根都没动——两种都不许说成"没出过事"）
//   platforms: 平台清单（GET /api/state 那份；只用来取展示名）
//   from / to：检测页选的平台 / 生成页当前的平台（不一致时提前讲明）
// }
//
// 按钮**没有可带的东西时置灰**（而不是点下去没反应）：理由就写在同一块里。
// 逐条理由的形状（三种都不静默）：带过去几件 / 自建件为什么不带 / 词表外为什么拒收。
export function hwcheckHandoffHTML(plan, opts = {}) {
  const one = plan || {};
  const carry = Array.isArray(one.carry) ? one.carry : [];
  const custom = Array.isArray(one.custom) ? one.custom : [];
  const unknown = Array.isArray(one.unknown) ? one.unknown : [];
  const pinFixes = Number(opts.pinFixes) > 0 ? Number(opts.pinFixes) : 0;
  const platforms = Array.isArray(opts.platforms) ? opts.platforms : [];
  const rows = [];

  // ① 引脚那一句：**永远在**（这是这一栏与生成页之间唯一说不清的地方）。
  //    开头就是 `hwcheckHandoffPinNote()` 那一句（单源，块里与回报那句共用）；
  //    "自动消解的那几根也不带过去、那不是你的选择"这一条同样**恒在**——接线表
  //    还没取到时我们并不知道移开过几根，但"移开过的也不带"这句话永远为真。
  rows.push('<div class="hwcheck-hint">' + hwcheckHandoffPinNote()
    + "：检测页没有引脚配置，不动就按默认布线。"
    + (pinFixes
      ? `这一趟生成前自动移开了 ${pinFixes} 处默认脚冲突，那几根也不带过去：`
        + "那是检测页的自动消解，不是你的选择。"
      : "检测页为避开冲突自动移开的线（如果有）同样不带过去："
        + "那是这一页的自动消解，不是你的选择。")
    + "</div>");

  // ② 要带过去的（空 = 说清"还没有可带的"，不让人对着灰按钮猜）
  if (carry.length) {
    rows.push('<div class="hwcheck-hint">要带过去 '
      + `<strong>${carry.length}</strong> 件：`
      + carry.map((slug) => `<span class="slug">${esc(slug)}</span>`).join("、")
      + "（生成页里已选过的不会重复加）</div>");
  } else if (!custom.length && !unknown.length) {
    rows.push('<div class="muted">还没选器件——先在上面选一件库内器件，'
      + "这里就能把它带进生成页（省得回去再找一遍同名模块）。</div>");
  } else {
    rows.push('<div class="muted">选中的这几件都带不过去——原因见下。</div>');
  }

  // ③ 库外自建件：为什么不带（点名是哪一件，学生才知道说的是他那件）
  custom.forEach((item) => {
    rows.push('<div class="hwcheck-hint">不带「' + esc(item.name || item.id)
      + '」（<span class="slug">' + esc(item.id) + '</span>）：库外自建件不在模块库里'
      + "——没有 manifest、不进 slugs，生成链不认它。要进工程，先在「模块库」把它"
      + "补录成模块。</div>");
  });

  // ④ 两类清单都没有这一件：**两个成因都说**（清单没读到 / 确实删了），不武断地
  //    只说后者——两份清单各自读失败时都是空集，那时"它已经被删了"是句假话。
  unknown.forEach((slug) => {
    rows.push('<div class="hwcheck-warn">⚠ <span class="slug">' + esc(slug)
      + "</span> 没有带过去：它现在既不在模块库清单里、也不在「我的器件」里"
      + "（可能是这两份清单有一份没读出来——刷新一次再看；也可能这件确实已经删了）。"
      + "生成链只认库内模块，硬塞进去只会在生成时被拒。</div>");
  });

  // ⑤ 平台不一致（两个栏目各选各的平台）：带过去之后按**生成页**的平台校验，
  //    这一句只是把"那边为什么会说它不支持"提前讲明（不替用户切平台）。
  const from = String(opts.from || "");
  const to = String(opts.to || "");
  if (from && to && from !== to) {
    rows.push('<div class="hwcheck-warn">⚠ 检测页选的是「'
      + esc(hwcheckPlatformLabel(platforms, from)) + "」，生成页当前是「"
      + esc(hwcheckPlatformLabel(platforms, to))
      + "」——带过去后按生成页的平台校验（那边不支持的模块会在第 6 步列出来）。</div>");
  }

  const label = carry.length
    ? `把这 ${carry.length} 件带进生成页`
    : "带进生成页";
  return '<div class="hwcheck-handoff">'
    + `<button data-hwcheck-handoff${carry.length ? "" : " disabled"}>${label}</button>`
    + rows.join("") + "</div>";
}

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckHandoffPlan, hwcheckHandoffHTML, hwcheckHandoffMerge,
    hwcheckHandoffPinNote, hwcheckHandoffResultText,
  });
}
