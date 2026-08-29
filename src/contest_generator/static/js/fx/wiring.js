// fx/wiring.js — 任务卡接线图渲染纯件（task-wiring-diagram/03）。
// 图 = 开发板俯视图 + 右侧模块端子列 + 引脚焊盘→端子盒连线（本步高亮彩色 /
// 「显示全部接线」其余行淡显 / 电源·地独立配色）+ 图例 + 空态文案。
// 数据纪律：形状 / 坐标 / 端子名全部由确定性数据渲染（board + rows + wiring
// 引用），无任何 AI 生成几何——wiring 引用只是「选哪些行」的名字。
// 几何与 fx/resource-board.js 的 resourceBoardSVG **同常量**（rowH=22、
// topPad=46、W=460、焊盘 r=7、芯片 x=100 w=260、标签 font-size=11）——
// 两处改动必须同步（三处同常量抽取单源为范围外，见 spec）。
import { esc } from "./core.js";

// —— 几何常量：与 fx/resource-board.js / ui/generate-pins.js 交叉同步 ——
const ROW_H = 22, TOP_PAD = 46, BOARD_W = 460, PAD_R = 7;
const CHIP_X = 100, CHIP_W = 260, LABEL_FS = 11;
const TERM_X = BOARD_W + 24;   // 端子列左缘（接线图右侧扩展列）
const TERM_W = 208, TERM_BOX_H = 20;

/** 电源 / 地 / 复位类引脚（board pin kind ∈ power|gnd|reset）→ 独立配色。
 * 电源线一眼可辨（供电部分与信号线区分开，spec 用户故事 5）。 */
export function isPowerKind(kind) {
  return kind === "power" || kind === "gnd" || kind === "reset";
}

/** 行 → 线描述：{pin, target, label, remark, note, power, hl}。
 * target = 端子名（role_id）；label = 端子盒主文字（模块 · 角色）；remark =
 * 行说明（类型 / 必接）；power = 引脚是否电源类（行 pin 查板 kind）。 */
function rowLine(row, board) {
  const pin = (row && row.pin) || "";
  return {
    pin,
    target: (row && row.role_id) || (row && row.role) || "",
    label: [row && row.slug, row && row.role].filter(Boolean).join(" · "),
    remark: (row && row.remark) || "",
    note: "",
    power: isPowerKind(pinKind(pin, board)),
    hl: false,
  };
}

/** 引脚在板定义中的 kind（行只带名字，kind 查板）；板外引脚 → null。 */
function pinKind(pinName, board) {
  const pins = (board && board.pins) || [];
  for (const p of pins) {
    if (p && p.name === pinName) return p.kind;
  }
  return null;
}

/** 引脚在板上的焊盘中心坐标（与 resourceBoardSVG 同换算：
 * x=0 左列 150 / x=1 右列 310，y = topPad + pin.y * rowH + rowH/2）。 */
function padCenter(board, pinName) {
  const pins = (board && board.pins) || [];
  for (const p of pins) {
    if (p && p.name === pinName) {
      const cx = p.x === 0 ? 150 : 310;
      const cy = TOP_PAD + ((p.y || 0) * ROW_H) + ROW_H / 2;
      return { cx, cy };
    }
  }
  return null;
}

/** 端子名匹配：target ∈ {role_id, role_label, role（渲染合成串——后端白名单
 * 同收，评审整改：展示值照抄也能命中行）} 且 pin 同名的行才算被 wiring 条目
 * 命中（图上不出现与数据矛盾的线）。 */
function matchRow(row, entry) {
  if (!row || !entry) return false;
  if (row.pin !== entry.pin) return false;
  const target = String(entry.target || "");
  if (!target) return false;
  return row.role_id === target || row.role_label === target || row.role === target;
}

/** 本步高亮线：wiring 条目逐条解析（非法条目——pin 不在板上 / target 空——
 * 丢弃；命中行 = 行数据 + 高亮；未命中行 = 按引用画（板内直连 / 板载资源 /
 * 供电线，端子名 = target 自身）。保序去重（同 pin+target 只画一条）。 */
export function highlightWiringLines(board, rows, wiringEntries) {
  const allRows = Array.isArray(rows) ? rows : [];
  const entries = Array.isArray(wiringEntries) ? wiringEntries : [];
  const lines = [];
  const seen = new Set();
  for (const entry of entries) {
    if (!entry || typeof entry !== "object") continue;
    const pin = String(entry.pin || "");
    const target = String(entry.target || "");
    if (!pin || !target) continue;
    if (!padCenter(board, pin)) continue;   // 幻觉引脚（校验层本应已拒，渲染侧兜底）
    const key = pin + "→" + target;
    if (seen.has(key)) continue;
    seen.add(key);
    const row = allRows.find((r) => matchRow(r, { pin, target }));
    lines.push(row
      ? { ...rowLine(row, board), note: String(entry.note || ""), hl: true }
      : {
          pin, target, label: target, remark: "",
          note: String(entry.note || ""),
          power: isPowerKind(pinKind(pin, board)),
          hl: true,
        });
  }
  return lines;
}

/** 全部接线行（「显示全部接线」用）：rows 逐行一条，hl 由命中集合标记；
 * 命中本步的仍高亮，其余淡显。未命中的条目专用线（供电 / 板载资源）附后。 */
export function wiringAllLines(board, rows, highlight) {
  const allRows = Array.isArray(rows) ? rows : [];
  const hlSet = new Set((highlight || []).map((l) => l.pin + "→" + l.target));
  const lines = allRows.map((row) => {
    const line = rowLine(row, board);
    if (hlSet.has(line.pin + "→" + line.target)) line.hl = true;
    return line;
  });
  for (const l of highlight || []) {
    if (!lines.some((x) => x.pin === l.pin && x.target === l.target)) {
      lines.push(l);
    }
  }
  return lines;
}

/** 板壳 + 芯片 + 地标 + 全部焊盘（丝印名）——与 resourceBoardSVG 同画法
 * （0° 视角、无点击/旋转；此处不画任务着色，接线图只求板形可认）。 */
function boardSVGParts(board, rowsCount) {
  const parts = [];
  const pins = (board && board.pins) || [];
  const hasTop = (board.landmarks || []).some((l) => l.edge === "top");
  const hasBottom = (board.landmarks || []).some((l) => l.edge === "bottom");
  const extraBottom = hasBottom ? 40 : 14;
  const H = TOP_PAD + rowsCount * ROW_H + extraBottom;
  const pcbBottom = TOP_PAD - 10 + rowsCount * ROW_H + 18;
  const chip = (board.platform === "stm32") ? "STM32F103C8T6" : "MSPM0G3507";
  parts.push(`<rect x="${CHIP_X}" y="${TOP_PAD - 10}" width="${CHIP_W}" height="${rowsCount * ROW_H + 18}" rx="8" fill="${esc(board.pcb_color || "var(--pin-pcb)")}" stroke="var(--border)" stroke-width="1.5"/>`);
  parts.push(`<rect x="186" y="${H / 2 - 34}" width="88" height="68" rx="4" fill="var(--panel-2)" stroke="var(--border-strong)" stroke-width="1"/>`);
  parts.push(`<text x="230" y="${H / 2 - 10}" text-anchor="middle" font-family="var(--mono)" font-size="8.5" fill="var(--muted)">${esc(chip)}</text>`);
  parts.push(`<text x="230" y="${H / 2 + 14}" text-anchor="middle" font-size="9" fill="var(--muted)">2×20 排针</text>`);
  for (const lm of board.landmarks || []) {
    if (lm.kind === "header_4p" && lm.edge === "top") {
      parts.push(`<rect x="192" y="${TOP_PAD - 14}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16}" y="2" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="230" y="${TOP_PAD - 1}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
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
      parts.push(`<rect x="205" y="${TOP_PAD - 6}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="213" y="${TOP_PAD - 6}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="230" y="${TOP_PAD - 18}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    }
  }
  for (const pin of pins) {
    const cx = pin.x === 0 ? 150 : 310;
    const cy = TOP_PAD + ((pin.y || 0) * ROW_H) + ROW_H / 2;
    const io = pin.kind === "io";
    const labelX = pin.x === 0 ? cx - PAD_R - 7 : cx + PAD_R + 7;
    const anchor = pin.x === 0 ? "end" : "start";
    parts.push(`<circle cx="${cx}" cy="${cy}" r="${PAD_R}" fill="${io ? "var(--pin-pad)" : "var(--pin-fixed-pad)"}" stroke="var(--border-strong)" stroke-width="1.5"><title>${esc(String(pin.name || "") + (io ? "（空闲 IO）" : "（固定/电源）"))}</title></circle>`
      + `<text x="${labelX}" y="${cy + 4}" text-anchor="${anchor}" font-family="var(--mono)" font-size="${LABEL_FS}" fill="var(--muted)">${esc(String(pin.name || ""))}</text>`);
  }
  return parts;
}

/** 接线图整块 HTML（纯函数，全部输出转义）：
 * 输入 {board, rows, wiring, showAll}——
 * board = 板定义 dict（快照内嵌 / /api/boards 同形；null = 空态）；
 * rows = 接线行（快照 rows：slug/role/role_id/pin/remark…）；
 * wiring = 本步接线引用（迭代记录 wiring：[{pin, target, note}]）；
 * showAll = 是否展开「显示全部接线」（默认 false = 只画本步高亮线）。
 * 空 rows / 板定义缺失 / 全非法输入 → 中文空态文案（不崩溃、不空白）。 */
export function wiringDiagramHTML({ board, rows, wiring, showAll }) {
  if (!board || !(board.pins || []).length) {
    return '<div class="wiring-empty muted">板定义缺失——无法绘制接线图（下方文字指引仍可用）。</div>';
  }
  const highlight = highlightWiringLines(board, rows, wiring);
  const all = wiringAllLines(board, rows, highlight);
  const lines = showAll ? all : highlight;
  if (!lines.length) {
    // 空 rows / 全非法输入 → 中文空态文案（不崩溃、不空白——spec 退化路径）
    return '<div class="wiring-empty muted">本步无接线引用或接线数据为空——请按下方文字指引操作。</div>';
  }
  const boardRows = Math.max(
    ...(board.pins || []).map((p) => (p.y || 0) + 1)
  );
  const termRows = lines.length;
  const H = Math.max(TOP_PAD + boardRows * ROW_H + 40, TOP_PAD + termRows * ROW_H + 24);
  const W = TERM_X + TERM_W + 12;
  const parts = [];
  parts.push(`<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:720px" role="img" aria-label="${esc(board.name || "开发板")}接线图">`);
  parts.push(...boardSVGParts(board, boardRows));
  lines.forEach((line, index) => {
    const pad = padCenter(board, line.pin);
    if (!pad) return;
    const boxY = TOP_PAD + index * ROW_H;
    const boxCy = boxY + ROW_H / 2;
    const cls = "wiring-line" + (line.hl ? " wiring-hl" : " wiring-dim")
      + (line.power ? " wiring-power" : "");
    parts.push(`<path d="M ${pad.cx} ${pad.cy} L ${TERM_X} ${boxCy}" class="${cls}"/>`);
    parts.push(`<g class="wiring-term" transform="translate(${TERM_X} ${boxY})">`
      + `<rect x="0" y="0" width="${TERM_W}" height="${TERM_BOX_H}" rx="4" fill="var(--panel-2)" stroke="${line.hl ? "var(--accent)" : "var(--border)"}" stroke-width="${line.hl ? "1.5" : "1"}"/>`
      + `<text x="8" y="${13}" font-size="10" fill="${line.hl ? "var(--text)" : "var(--muted)"}">${esc(line.label)}</text>`
      + (line.remark || line.note
        ? `<text x="8" y="${TERM_BOX_H + 10}" font-size="8" fill="var(--muted)">`
          + esc([line.remark, line.note].filter(Boolean).join(" · ")) + "</text>"
        : "")
      + "</g>");
  });
  parts.push("</svg>");
  const legend = '<div class="wiring-legend">'
    + '<span class="lg"><span class="dot wiring-dot-hl"></span>本步接线</span>'
    + '<span class="lg"><span class="dot wiring-dot-power"></span>电源 / 地</span>'
    + (showAll ? '<span class="lg"><span class="dot wiring-dot-dim"></span>其它接线</span>' : '')
    + "</div>";
  const toggle = (all.length > 1)
    ? '<label class="wiring-toggle"><input type="checkbox" data-wiring-toggle'
      + (showAll ? " checked" : "") + "> 显示全部接线</label>"
    : "";
  return '<div class="wiring-diagram">'
    + '<div class="wiring-caption muted">' + esc(board.name || "开发板") + " · 本步接线</div>"
    + legend + parts.join("") + toggle + "</div>";
}
