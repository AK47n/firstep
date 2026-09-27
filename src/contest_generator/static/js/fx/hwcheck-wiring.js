// fx/hwcheck-wiring.js — 硬件检测栏目的纯函数：**器件选择 / 接线表 / 默认脚冲突 / 建议顺序**。
//
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。
// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，
// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。

import { esc } from "./core.js";
// chip 渲染取自模块库既有纯件（器件选择复用既有载荷与卡片/chip 渲染，
// 不另造一套模块清单协议）。
import { recommendChipHTML } from "./module.js";

// ===========================================================================
// 工单 module-hwcheck/03：器件选择 + 接线表 + 默认脚冲突预警 + 建议顺序
//
// 分工不变：判据全在服务端（接线行 = 生成工程 README 同一推导；共享 / 冲突 =
// 既有同脚分类；顺序 = 既有 bring-up 前置排序），本文件只把载荷渲染成 HTML 与
// 维护选择态。**不在这里判冲突、不在这里推顺序**——两处各推一遍必然漂移。
// ===========================================================================

// hwcheckSameExclusiveGroup(groups, a, b)：a 与 b 是不是**同一个互斥组**的成员。
// 判据只吃服务端给的组（库内 manifest 的 exclusive_group 投影，判据单源在
// `collect_exclusive_groups`）——前端不自己推组、也不写 slug 名单。
function hwcheckSameExclusiveGroup(groups, a, b) {
  const x = String(a == null ? "" : a);
  const y = String(b == null ? "" : b);
  if (!x || !y || x === y) return false;
  return (Array.isArray(groups) ? groups : []).some((group) => {
    const members = (group && group.members) || [];
    return members.includes(x) && members.includes(y);
  });
}

// hwcheckDevicePick(state, slug, on, groups)：选中 / 取消一件器件 → 新状态。
//
// **同组互斥 = 单选交换**（工单 05 用户拍板，与 fx/module.js 的组卡「单选交换」
// 同规则）：点开一件属于某互斥组的器件时，把**同组已选的其它成员**一并去掉——
// 这一组只能选一件（如姿态类 imu_uart / jy61p / ml_mpu6050）。组清单由服务端
// 按平台过滤后下发（单成员组不出，与赛题侧生成链路同一函数）。
//
// 取消（on=false）不做交换：去掉一件不会让另一件变得可选。
// 返回新对象（不改原对象）；空 slug / 状态本来就是这样 = 原样返回（幂等——
// 重复点同一件不该把它挪到列表末尾，那会顺带改变"器件在建议顺序里的位置"）。
export function hwcheckDevicePick(state, slug, on, groups = []) {
  const current = Array.isArray(state && state.devices) ? state.devices : [];
  const key = String(slug == null ? "" : slug);
  if (!key) return state;
  const has = current.includes(key);
  if (has === !!on) return state;
  let next = current.filter((item) => item !== key);
  if (on) {
    next = next.filter((item) => !hwcheckSameExclusiveGroup(groups, key, item));
    next.push(key);
  }
  return { ...state, devices: next };
}

// hwcheckDeviceGroupNoticeHTML(groups, devices)：同组互斥的页面提示。
//
// 两种情形分开说（都不静默）：
//   * 选中的组内成员 **≥2** —— 点选那条路已经收了，这里只可能是回读 / 历史态
//     留下的（后端换过组定义等），如实报"只能选一件，请去掉一件再生成"；
//   * 组内**已选一件**且还有别的成员 —— 明说"再点 X 会自动换掉 Y"，把单选
//     交换这条规则摆到台面上（用户点之前就知道会发生什么，不被静默换掉）。
export function hwcheckDeviceGroupNoticeHTML(groups, devices) {
  const list = Array.isArray(groups) ? groups : [];
  const sel = (Array.isArray(devices) ? devices : []).map((slug) => String(slug));
  const rows = [];
  (list || []).forEach((group) => {
    const members = ((group && group.members) || []).map((slug) => String(slug));
    const chosen = members.filter((slug) => sel.includes(slug));
    if (!chosen.length) return;
    const label = esc(String((group && group.label) || (group && group.id) || ""));
    if (chosen.length >= 2) {
      rows.push('<div class="hwcheck-warn">⚠ 同组互斥（' + label + '）：'
        + esc(chosen.join(" × ")) + " 只能选一件——请去掉一件再生成。</div>");
      return;
    }
    const others = members.filter((slug) => !sel.includes(slug));
    if (!others.length) return;
    rows.push('<div class="hwcheck-hint">▸ 同组互斥（' + label + '）：这一组只能选一件'
      + "——再点 " + esc(others.join(" / ")) + " 会自动换掉 " + esc(chosen[0]) + "。</div>");
  });
  return rows.join("");
}

// hwcheckDevicePool(modules)：可挑选的器件池 = **模块库全量**（/api/modules 既有
// 载荷，与模块库页 / 生成页同一份，卡片渲染也同一套）。
//
// 为什么**不按 kind 过滤**（工单 03 评审整改）：`library.MODULE_KIND` 分的是
// 「要不要购买链接」，不是「能不能上板测」。按它过滤会把 spec 的 v1 专精清单里的
// `adc`（internal，却有 ADC 引脚声明）关在门外——检测页会永远选不到它。挑选面
// 的收敛留给配方与专精标注（后续工单），这里一个字都不判。
export function hwcheckDevicePool(modules) {
  return (Array.isArray(modules) ? modules : []).filter((m) => m && m.slug);
}

// hwcheckDeviceKit(modules, slug, platform)：已选器件的套件型号（chip 上那句
// 小字）——取 /api/modules 载荷里该平台条目的 kit（人补的硬件身份字段）；
// 没有 = 空串（不编造）。
export function hwcheckDeviceKit(modules, slug, platform) {
  const hit = (Array.isArray(modules) ? modules : []).find((m) => m && m.slug === slug);
  const entry = hit && hit.platforms ? hit.platforms[platform] : null;
  return String((entry && entry.kit) || "");
}

// hwcheckDeviceChipsHTML(devices, modules, platform)：已选器件 chips。
// **复用推荐区的 chip 渲染**（fx/module.js recommendChipHTML：绿底 + ✕「点击
// 从工程里移除」+ 内嵌「说明」按钮）——不另造一套卡片协议；点 chip = 把这一件
// 从这次检测的工程里去掉（说明按钮由 ui 用既有 bindModuleInfoEntry 委托拦住）。
export function hwcheckDeviceChipsHTML(devices, modules, platform) {
  const list = (Array.isArray(devices) ? devices : []).filter(Boolean);
  if (!list.length) return "";
  return list.map((slug) => recommendChipHTML(
    slug, hwcheckDeviceKit(modules, slug, platform), true)).join("");
}

// hwcheckDeviceEmptyHTML()：一件器件都没选时的说明（这不是错误状态——
// 「先确认板子活着」本来就是检测页的第一条路）。
export function hwcheckDeviceEmptyHTML() {
  return '<div class="muted">还没选器件——也可以就这样生成：那是先确认板子和'
    + '烧录链路是好的（灯在闪 = 程序在跑）。选上器件后，下面会出现它们的接线表、'
    + '默认脚冲突与建议检测顺序。</div>';
}

// hwcheckMissingDevicesHTML(missing)：选了**本平台没有条目**的器件 → 逐条点名
// （票面硬要求：不静默省略——悄悄从接线表里消失会让学生以为"选上了、能测"）。
export function hwcheckMissingDevicesHTML(missing) {
  const list = Array.isArray(missing) ? missing : [];
  if (!list.length) return "";
  return list.map((item) => {
    const text = (item && (item.message || item.slug)) || "";
    return `<div class="hwcheck-warn">⚠ ${esc(text)}</div>`;
  }).join("");
}

// hwcheckPinFixHTML(pinFixes)：生成前**自动移开的默认脚撞脚**（工单
// hwcheck-pin-conflict-exit/01）。为什么必须明说：检测页没有引脚配置入口，学生
// 照"原厂默认脚"接好线却生成了另一组脚，是最难查的一类不一致——所以页面把动过的
// 每一根线原样打出来（说明行由服务端给，前端只渲染），并点明接线表已是新脚。
// 空数组 = 这一趟一根都没动，不渲染任何东西（不制造"好像出过事"的错觉）。
export function hwcheckPinFixHTML(pinFixes) {
  const list = (Array.isArray(pinFixes) ? pinFixes : []).map((item) => String(item || ""))
    .filter((item) => item);
  if (!list.length) return "";
  return '<div class="hwcheck-warn">⚠ 生成前自动移开了 '
    + `${list.length} 处默认脚冲突（这几根线<strong>不按原厂默认脚</strong>，按下面接线表接）：`
    + list.map((item) => `<div class="hwcheck-pin-fix">· ${esc(item)}</div>`).join("")
    + "</div>";
}

// hwcheckPinCapacityNoteHTML(note)：**这一趟没判**「装不装得下」的原因（工单
// hwcheck-hygiene/04）。为什么必须显示：母版没导入时容量判定整段跳过，页面若一声不吭
// 就像"检查过了、没问题"，而学生点到「生成」才吃 400。空 = 判过了（或这一步不适用），
// 不渲染任何东西。文案由服务端给（`PIN_CAPACITY_SKIPPED_NOTE` 单源），前端只渲染。
export function hwcheckPinCapacityNoteHTML(note) {
  const text = String(note || "").trim();
  if (!text) return "";
  return `<div class="hwcheck-warn">⚠ ${esc(text)}</div>`;
}

// hwcheckWiringTableHTML(rows, footnote)：接线表（列与工程 README「引脚接线表」
// 同序：模块 / 角色 / 引脚 / 说明）。pin_note = 板上共享注记（如地猛星 PA0/PA1 的
// 「板载 LED 共用」）——挂在同一行上：学生照着表和板子对线时才看得见这条暗雷。
// footnote = 与工程 README 同一句尾注（服务端随载荷下发；空 = 不渲染）。
export function hwcheckWiringTableHTML(rows, footnote) {
  const list = Array.isArray(rows) ? rows : [];
  const tail = footnote
    ? `<div class="hwcheck-hint">${esc(footnote)}</div>` : "";
  if (!list.length) {
    return '<div class="muted">这次没有已声明引脚角色的接线行——所选模块的实现'
      + "内嵌母版（如 stm32 的 led / delay），不产生独立接线。</div>" + tail;
  }
  const body = list.map((row) => {
    const note = String((row && row.pin_note) || "").trim();
    return "<tr>"
      + `<td><span class="slug">${esc((row && row.slug) || "")}</span></td>`
      + `<td>${esc((row && (row.role || row.role_id)) || "")}</td>`
      + `<td><span class="hwcheck-pin">${esc((row && row.pin) || "")}</span></td>`
      + `<td>${esc((row && row.remark) || "")}`
      + (note ? `<span class="hwcheck-share">⚠ 板载共享：${esc(note)}</span>` : "")
      + "</td></tr>";
  }).join("");
  return '<table class="hwcheck-table"><thead><tr>'
    + "<th>模块</th><th>角色</th><th>引脚</th><th>说明</th>"
    + `</tr></thead><tbody>${body}</tbody></table>`
    + '<div class="hwcheck-hint">这张表与生成出来的工程 README「引脚接线表」'
    + "是同一份推导（同一函数、同一字段）——照着它插线就行。</div>"
    + tail;
}

// hwcheckRoleLabeler(rows)：同脚组里的角色键（`<slug>.<role_id>`，服务端既有
// 角色键文法）→ 显示文本（`slug·角色`，角色取接线表里那一行的渲染文本）。
// 找不到对应行 = 原样显示角色键（不猜、不丢——它仍是真实存在的角色）。
function hwcheckRoleLabeler(rows) {
  const by = new Map();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    if (row && row.slug && row.role_id) {
      by.set(row.slug + "." + row.role_id, String(row.role || row.role_id));
    }
  });
  return (key) => {
    const text = String(key == null ? "" : key);
    const role = by.get(text);
    if (!role) return esc(text);
    return esc(text.split(".")[0] + "·" + role);
  };
}

// hwcheckBoardSharesHTML(board_shares, rows)：**板上自带**的共享脚（板定义里写了
// 注记的脚，如地猛星 PA0/PA1「板载 LED 共用」）。与模块之间的同脚组分开列：
// 这类重叠不是"你选错了"，是板子本来就这么接的——但学生必须知道（灯会跟着串口
// 通信微闪、I2C 上拉靠模块板自带），所以不能只藏在接线表的说明列里。
export function hwcheckBoardSharesHTML(boardShares, rows) {
  const list = Array.isArray(boardShares) ? boardShares : [];
  if (!list.length) return "";
  const label = hwcheckRoleLabeler(rows);
  return '<div class="hwcheck-hint">板上自带的共享（原厂就这么接的，不是接线错误）：</div>'
    + list.map((item) => {
      const roles = ((item && item.roles) || []).map(label).join(" × ");
      return '<div class="hwcheck-group board-share">'
        + '<span class="hwcheck-group-mark">⚠ 板上共享</span>'
        + `<span class="hwcheck-pin">${esc((item && item.pin) || "")}</span>`
        + `<span class="hwcheck-group-roles">${roles}</span>`
        + `<span class="hwcheck-group-reason">${esc((item && item.note) || "")}</span>`
        + "</div>";
    }).join("");
}

// hwcheckPinGroupsHTML(groups, rows)：模块之间的同脚组 → **物理冲突（⚠）/
// 合法共享（✓）**。kind / reason 全部来自服务端既有同脚分类（同一 I2C 总线 =
// 可共享；同脚分属不同外设 = 物理不通）；前端只上色，不改判。
// 空集那句话必须**说准**：`_shared_groups` 只看模块角色，看不见板上自带的共享
// （板载 LED / 板载上拉），所以不能写成"没有共用同一个引脚"——那是假安心
// （工单 03 评审整改）。板载共享由 hwcheckBoardSharesHTML 单独列。
export function hwcheckPinGroupsHTML(groups, rows) {
  const list = Array.isArray(groups) ? groups : [];
  if (!list.length) {
    return '<div class="hwcheck-ok">✓ 没有两件模块抢同一个引脚'
      + "（板上自带的共享另见下一条）。</div>";
  }
  const label = hwcheckRoleLabeler(rows);
  return list.map((group) => {
    const conflict = (group && group.kind) === "conflict";
    const roles = ((group && group.roles) || []).map(label).join(" × ");
    return `<div class="hwcheck-group ${conflict ? "conflict" : "share"}">`
      + `<span class="hwcheck-group-mark">${conflict ? "⚠ 引脚冲突" : "✓ 可共享"}</span>`
      + `<span class="hwcheck-pin">${esc((group && group.pin) || "")}</span>`
      + `<span class="hwcheck-group-roles">${roles}</span>`
      + `<span class="hwcheck-group-reason">${esc((group && group.reason) || "")}</span>`
      + "</div>";
  }).join("");
}

// hwcheckOrderDesc(text)：顺序行里的简介截断——顺序表是给人**扫一眼**的清单，
// 不是读简介的地方（库内简介常有整段）。切点与推荐区「瘦身行」同一取舍：先找
// 「。」再找「；」取更早的那个，再按字符上限兜底加省略号。
const HWCHECK_ORDER_DESC_CHARS = 60;

export function hwcheckOrderDesc(text) {
  const raw = String(text == null ? "" : text).trim();
  if (!raw) return "";
  const stops = ["。", "；"].map((mark) => raw.indexOf(mark)).filter((i) => i >= 0);
  let out = stops.length ? raw.slice(0, Math.min(...stops) + 1) : raw;
  if (out.length > HWCHECK_ORDER_DESC_CHARS) {
    out = out.slice(0, HWCHECK_ORDER_DESC_CHARS) + "…";
  }
  return out;
}

// hwcheckOrderHTML(order, guide, reason)：建议检测顺序（bring-up 前置，判据 =
// 服务端既有排序；`bring_up` 标记同源）。空集 = 空串（调用方放占位）。
//
// 自建件那几行（工单 hwcheck-unknown-device/05）**排在库内之后**（服务端拼好，
// 这里不重排）：多两个服务端字段——`tag_text`（标注词「自建件：按你确认的事实
// 探测」，与库内 `[专精]` 严格区分）与 `name`（slug 之外给人认的那个名字）。
export function hwcheckOrderHTML(order, guide, reason) {
  const list = Array.isArray(order) ? order : [];
  if (!list.length) return "";
  const items = list.map((item, index) => {
    const one = item || {};
    const tag = one.bring_up ? '<span class="badge ok">先做·板子活着</span>' : "";
    const custom = one.custom
      ? (one.tag_text ? `<span class="badge custom">${esc(one.tag_text)}</span>` : "")
        + (one.name ? `<span class="hwcheck-order-name">${esc(one.name)}</span>` : "")
      : "";
    return '<li class="hwcheck-order-row">'
      + `<span class="hwcheck-order-index">${index + 1}</span>`
      + `<span class="slug">${esc(one.slug || "")}</span>${tag}${custom}`
      + `<span class="hwcheck-order-desc">${esc(hwcheckOrderDesc(one.description))}</span>`
      + "</li>";
  }).join("");
  return `<div class="hwcheck-hint">${esc(guide || "")}</div>`
    + `<ol class="hwcheck-order">${items}</ol>`
    + `<div class="hwcheck-hint">为什么是这个次序：${esc(reason || "")}</div>`;
}

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckDevicePick, hwcheckDevicePool, hwcheckDeviceKit,
    hwcheckDeviceChipsHTML, hwcheckDeviceEmptyHTML, hwcheckMissingDevicesHTML,
    hwcheckDeviceGroupNoticeHTML, hwcheckWiringTableHTML, hwcheckPinGroupsHTML,
    hwcheckBoardSharesHTML, hwcheckOrderHTML, hwcheckOrderDesc,
  });
}
