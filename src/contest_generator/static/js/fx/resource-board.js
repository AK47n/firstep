// fx/resource-board.js — 资源总览「板图视角」纯件（resource-overview-polish/02）。
// 板定义 = GET /api/boards?platform= 的 boards[0]（JSON：pins[{name,kind,x,y,side,…}],
// landmarks, fixed）；几何与 ui/generate-pins.js 的 renderPinBoard/svgPin **同常量**
// （rowH=22、topPad=46、W=460、焊盘 r=7、标签 font-size=11、焊芯 x=100 w=260）——
// 两处改动必须同步（后续抽取共享渲染器为范围外）。本视图 0° 视角、无点击/旋转/饼图，
// 职责 = 引脚按任务着色 + 冲突黄描边 + 悬停(title) 显示占用任务。
import { esc } from "./core.js";
import { aggregateResourceGroups, taskUserLabel } from "./task.js";

/** 任务配色（与 ui/generate-pins.js MODULE_COLORS 同值保持全站一致；两处常量，
 * 后续可抽 fx/color.js 单源——范围外）。按任务在资源聚合中的出现顺序循环分配。 */
export const RESOURCE_TASK_COLORS = [
  "#60a5fa", "#f87171", "#34d399", "#fbbf24", "#a78bfa", "#f472b6",
  "#22d3ee", "#a3e635", "#fb923c", "#e879f9", "#38bdf8", "#facc15",
];

/** 任务 id → 颜色（Map 保首次出现顺序）：入参可直接是 aggregateResourceGroups
 * 的返回值（含 .pins/.other/.soft），否则当作 plan 先聚合。空 → 空 Map。 */
export function resourceTaskColorMap(groupsOrPlan) {
  const groups = groupsOrPlan && groupsOrPlan.pins
    ? groupsOrPlan
    : aggregateResourceGroups(groupsOrPlan);
  const map = new Map();
  if (!groups) return map;
  let i = 0;
  const put = (users) => users.forEach((u) => {
    if (u && typeof u.id === "string" && !map.has(u.id)) {
      map.set(u.id, RESOURCE_TASK_COLORS[i++ % RESOURCE_TASK_COLORS.length]);
    }
  });
  groups.pins.forEach((e) => put(e.users));
  groups.other.forEach((e) => put(e.users));
  groups.soft.forEach((e) => put(e.users));
  return map;
}

/** 板图 SVG（纯字符串；pinAttr: Map<pinName, {color, conflict, users:[{id,title}]}>）。
 * 未占用的引脚按焊盘的 空闲 IO / 固定电源 样式灰显；占用的按任务色填充 +
 * 同色描边；冲突额外 r=9.5 黄虚线环 + .res-pin-conflict（CSS 呼吸）。 */
export function resourceBoardSVG(board, pinAttr) {
  const pins = (board && board.pins) || [];
  if (!pins.length) return "";
  // —— 几何常量：与 generate-pins.js renderPinBoard/svgPin 交叉同步 ——
  const rowH = 22, topPad = 46, W = 460;
  const rows = Math.max(...pins.map((p) => p.y)) + 1;
  const hasTop = (board.landmarks || []).some((l) => l.edge === "top");
  const hasBottom = (board.landmarks || []).some((l) => l.edge === "bottom");
  const extraBottom = hasBottom ? 40 : 14;
  const H = topPad + rows * rowH + extraBottom;
  const pcbBottom = topPad - 10 + rows * rowH + 18;
  const chip = (board.platform === "stm32") ? "STM32F103C8T6" : "MSPM0G3507";
  const parts = [];
  parts.push(`<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:440px" role="img" aria-label="${esc(board.name || "开发板")}资源占用板图">`);
  parts.push(`<rect x="100" y="${topPad - 10}" width="260" height="${rows * rowH + 18}" rx="8" fill="${esc(board.pcb_color || "var(--pin-pcb)")}" stroke="var(--border)" stroke-width="1.5"/>`);
  parts.push(`<rect x="186" y="${H / 2 - 34}" width="88" height="68" rx="4" fill="var(--panel-2)" stroke="var(--border-strong)" stroke-width="1"/>`);
  parts.push(`<text x="230" y="${H / 2 - 10}" text-anchor="middle" font-family="var(--mono)" font-size="8.5" fill="var(--muted)">${esc(chip)}</text>`);
  parts.push(`<text x="230" y="${H / 2 + 14}" text-anchor="middle" font-size="9" fill="var(--muted)">2×20 排针</text>`);
  // 板缘地标（与 generate-pins.js 同画法：header_4p / usb_typec，0° 不换边）
  for (const lm of board.landmarks || []) {
    if (lm.kind === "header_4p" && lm.edge === "top") {
      parts.push(`<rect x="192" y="${topPad - 14}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16}" y="2" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="230" y="${topPad - 1}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "header_4p" && lm.edge === "bottom") {
      parts.push(`<rect x="192" y="${pcbBottom - 4}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16}" y="${pcbBottom - 2}" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="230" y="${pcbBottom - 12}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "usb_typec" && lm.edge === "bottom") {
      parts.push(`<rect x="205" y="${pcbBottom - 30}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="213" y="${pcbBottom - 7}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="230" y="${pcbBottom + 8}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    } else if (lm.kind === "usb_typec" && lm.edge === "top") {
      parts.push(`<rect x="205" y="${topPad - 6}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="213" y="${topPad - 6}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="230" y="${topPad - 18}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    }
  }
  for (const pin of pins) {
    const cx = pin.x === 0 ? 150 : 310;
    const cy = topPad + pin.y * rowH + rowH / 2;
    const attr = pinAttr && pinAttr.get(pin.name);
    const io = pin.kind === "io";
    const fill = attr ? attr.color : io ? "var(--pin-pad)" : "var(--pin-fixed-pad)";
    const stroke = attr ? (attr.conflict ? "var(--warn)" : attr.color) : io ? "var(--border-strong)" : "var(--border)";
    const strokeWidth = attr ? (attr.conflict ? "2.5" : "2") : "1.5";
    const labelFill = attr ? attr.color : "var(--muted)";
    const users = (attr && attr.users) || [];
    const ttl = attr
      ? pin.name + " · " + users.map((u) => taskUserLabel(u)).join("、") + (attr.conflict ? " · ⚠ 多任务共享" : "")
      : pin.name + (io ? "（空闲 IO）" : "（固定/电源）");
    const labelX = pin.x === 0 ? cx - 14 : cx + 14;
    const anchor = pin.x === 0 ? "end" : "start";
    parts.push(`<circle cx="${cx}" cy="${cy}" r="7" fill="${fill}" fill-opacity="${attr ? "0.9" : "1"}" stroke="${stroke}" stroke-width="${strokeWidth}"${attr ? ' class="res-pin-used"' : ' class="res-pin-idle"'}>`
      + `<title>${esc(ttl)}</title></circle>`
      + (attr && attr.conflict
        ? `<circle cx="${cx}" cy="${cy}" r="9.5" fill="none" stroke="var(--warn)" stroke-width="1" stroke-dasharray="2.5 2" class="res-pin-conflict"/>`
        : "")
      + `<text x="${labelX}" y="${cy + 4}" text-anchor="${anchor}" font-family="var(--mono)" font-size="11" fill="${labelFill}"${attr ? ' font-weight="700"' : ""}>${esc(pin.name)}</text>`);
  }
  parts.push("</svg>");
  return parts.join("");
}

/** 资源总览工具栏（resource-overview-polish/02）：标题 + 「列表/板图」切换按钮
 * （view=当前激活视图，active 高亮 + aria-pressed）。list = 分组列表（01），
 * board = 板图视角（本模块）。 */
export function resourcesToolbarHTML(view) {
  const btn = (key, label) => '<button type="button" class="res-view-btn'
    + (view === key ? " active" : "") + '" data-res-view="' + key
    + '" aria-pressed="' + (view === key) + '">' + label + "</button>";
  return '<div class="res-toolbar"><span class="res-toolbar-title muted">资源总览</span>'
    + '<div class="res-view-switch" role="group" aria-label="资源总览视图切换">'
    + btn("list", "列表") + btn("board", "板图") + "</div></div>";
}

/** 板图整块 HTML：板名 + 图例（任务色点/冲突说明/空闲说明）+ SVG +
 * 「不在板上的资源」chips 行（外设/中断/软资源/未引出引脚不回丢）。
 * groups = aggregateResourceGroups(plan) 返回值；taskColors 可显式传入（缺省按 groups 分配）。
 * opts.conflictLegend = false 时隐藏「⚠ 多任务共享」图例项（单任务视角——
 * 如任务接线图退化图，groups 已过滤到单任务且无冲突，该图例会误导）。 */
export function resourceBoardHTML(board, groups, taskColors, opts) {
  if (!board) {
    return '<div class="res-board-msg muted">板定义缺失——无法绘制资源占用板图。</div>';
  }
  if (!groups) {
    return '<div class="res-board-msg muted">尚无资源标注——先识别（拆解包）后查看板图。</div>';
  }
  const colors = taskColors || resourceTaskColorMap(groups);
  const pinAttr = new Map();
  const onboard = new Set((board.pins || []).map((p) => p.name));
  const missing = [];   // {name, users, soft}
  const collect = (rows, soft) => rows.forEach((e) => e.names.forEach((name) => {
    if (onboard.has(name) && !soft) {
      pinAttr.set(name, {
        color: colors.get((e.users[0] || {}).id) || "var(--accent)",
        conflict: !!e.conflict,
        users: e.users,
      });
    } else if (!pinAttr.has(name)) {
      missing.push({ name, users: e.users, soft });
    }
  }));
  collect(groups.pins, false);
  collect(groups.other, false);
  collect(groups.soft, true);
  const svg = resourceBoardSVG(board, pinAttr);
  // 序号人话化（工单 beginner-gap-closure/03）：图例色点标签用「第 N 步」，
  // 原始任务 id 不上界面（seqById 由 groups users 的 order 反查）
  const seqById = {};
  [...(groups.pins || []), ...(groups.other || []), ...(groups.soft || [])]
    .forEach((e) => (e.users || []).forEach((u) => {
      if (u && u.id && u.order != null) seqById[u.id] = u.order;
    }));
  const legend = [...colors.entries()].map(([id, color]) =>
    '<span class="lg"><span class="dot" style="background:' + esc(color) + '"></span>'
    + esc(seqById[id] != null ? "第 " + seqById[id] + " 步" : id) + "</span>"
  ).join("")
    + (!(opts && opts.conflictLegend === false)
      ? '<span class="lg"><span class="dot res-legend-conflict"></span>⚠ 多任务共享（联调冲突）</span>'
      : "")
    + '<span class="lg"><span class="dot"></span>空闲 IO</span>';
  const missingHTML = missing.length
    ? '<div class="res-board-missing"><span class="muted">不在板上的资源（外设/中断/软资源）：</span>'
      + missing.map((m) => {
        const ttl = m.users.map((u) => esc(taskUserLabel(u))).join("、");
        return '<span class="res-chip' + (m.soft ? " res-soft" : "") + '" title="' + ttl + '">' + esc(m.name) + "</span>";
      }).join(" ") + "</div>"
    : "";
  return '<div class="res-board-wrap">'
    + '<div class="res-board-caption">' + esc(board.name || "开发板") + " · 引脚资源占用</div>"
    + '<div class="res-board-legend">' + legend + "</div>"
    + svg
    + missingHTML
    + "</div>";
}
