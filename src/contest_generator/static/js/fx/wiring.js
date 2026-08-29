// fx/wiring.js — 任务卡接线图渲染纯件（task-wiring-diagram/03）。
// 图 = 开发板俯视图 + 左右两侧模块端子列 + 引脚焊盘→端子盒连线（本步高亮彩色 /
// 「显示全部接线」其余行淡显 / 电源·地独立配色）+ 图例 + 空态文案。
// 布局（工单 06，两列布线）：板居中，左列焊盘线接左端子列、右列接右端子列——
// 跨侧线被板隔离；端子盒纵向优先**对齐焊盘**（线水平、零交叉），同侧同 y 多线
// （一焊盘多线，罕见）该侧改等距兜底（按焊盘 y 单调排布，同侧不交叉、盒不重叠）。
// 数据纪律：形状 / 坐标 / 端子名全部由确定性数据渲染（board + rows + wiring
// 引用），无任何 AI 生成几何——wiring 引用只是「选哪些行」的名字。
// 几何与 fx/resource-board.js 的 resourceBoardSVG **同常量**（rowH=22、
// topPad=46、W=460、焊盘 r=7、芯片 x=100 w=260、标签 font-size=11）——
// 两处改动必须同步（三处同常量抽取单源为范围外，见 spec）。
import { esc } from "./core.js";

// —— 几何常量：与 fx/resource-board.js / ui/generate-pins.js 交叉同步 ——
const ROW_H = 22, TOP_PAD = 46, BOARD_W = 460, PAD_R = 7;
const CHIP_X = 100, CHIP_W = 260, LABEL_FS = 11;
const TERM_W = 208, TERM_BOX_H = 20, TERM_GAP = 24;
const BOARD_X = TERM_W + TERM_GAP;               // 板图左缘（=232，两列端子区对称、板居中）
const TERM_L_X = 0;                              // 左端子盒左缘
const TERM_R_X = BOARD_X + BOARD_W + TERM_GAP;   // 右端子盒左缘（=716）

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

/** 引脚在板上的焊盘几何（与 resourceBoardSVG 同换算：x=0 左列 150 / x=1
 * 右列 310，y = topPad + pin.y * rowH + rowH/2；板整体平移 BOARD_X——工单 06
 * 两列布线）：side = 焊盘所在板侧（L/R）→ 端子分列。单一出处——padCenter
 * 与 boardPinParts 共用（评审整改：坐标表达式抽共享，防两处漂移）。 */
function pinXY(pin) {
  const left = pin.x === 0;
  return {
    cx: BOARD_X + (left ? 150 : 310),
    cy: TOP_PAD + ((pin.y || 0) * ROW_H) + ROW_H / 2,
    side: left ? "L" : "R",
  };
}

function padCenter(board, pinName) {
  const pins = (board && board.pins) || [];
  for (const p of pins) {
    if (p && p.name === pinName) return pinXY(p);
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

/** 按任务 resources 反推「本步涉及的线」（tier-2 增强，工单 05）：
 * resources = 任务拆解时 AI 标定的真实引脚名 / 模块 slug；接线行（与 README
 * 同源——快照或 README 兜底）决定每根线接哪个端子。data 纪律：resources 只
 * 作「选哪些行」的名字，线/端子名由确定数据决定——引脚名 → 同 pin 的接线行
 * （多行同 pin 全收，如 LED 与 LED_RED 双行）；模块 slug → 该模块全部行；
 * 无匹配（供电 / 板载资源 / 外设名等不在接线行内）→ 跳过（不幻觉线）。
 * 保序去重（同 pin→target 只画一条），返回 wiring 引用形 [{pin, target, note}]。 */
export function wiringFromResources(resources, rows) {
  const allRows = Array.isArray(rows) ? rows : [];
  const out = [];
  const seen = new Set();
  for (const r of resources || []) {
    const name = String(r || "");
    if (!name) continue;
    for (const row of allRows) {
      if (!row || (row.pin !== name && row.slug !== name)) continue;
      const target = row.role_id || row.role || "";
      if (!target) continue;
      const key = row.pin + "→" + target;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ pin: row.pin, target, note: "" });
    }
  }
  return out;
}

/** 板壳 + 芯片 + 地标（丝印，**不含焊盘**——焊盘与标签画在连线之上，见
 * boardPinParts）——与 resourceBoardSVG 同画法（0° 视角、无点击/旋转；此处
 * 不画任务着色，接线图只求板形可认）。工单 06：板整体平移 BOARD_X（两列
 * 端子区对称、板居中），板内全部 x 坐标随动。 */
function boardBaseParts(board, rowsCount) {
  const parts = [];
  const hasTop = (board.landmarks || []).some((l) => l.edge === "top");
  const hasBottom = (board.landmarks || []).some((l) => l.edge === "bottom");
  const extraBottom = hasBottom ? 40 : 14;
  const H = TOP_PAD + rowsCount * ROW_H + extraBottom;
  const pcbBottom = TOP_PAD - 10 + rowsCount * ROW_H + 18;
  const cx0 = BOARD_X + 230;   // 板内原中心 230 平移
  const chip = (board.platform === "stm32") ? "STM32F103C8T6" : "MSPM0G3507";
  parts.push(`<rect x="${CHIP_X + BOARD_X}" y="${TOP_PAD - 10}" width="${CHIP_W}" height="${rowsCount * ROW_H + 18}" rx="8" fill="${esc(board.pcb_color || "var(--pin-pcb)")}" stroke="var(--border)" stroke-width="1.5"/>`);
  parts.push(`<rect x="${186 + BOARD_X}" y="${H / 2 - 34}" width="88" height="68" rx="4" fill="var(--panel-2)" stroke="var(--border-strong)" stroke-width="1"/>`);
  parts.push(`<text x="${cx0}" y="${H / 2 - 10}" text-anchor="middle" font-family="var(--mono)" font-size="8.5" fill="var(--muted)">${esc(chip)}</text>`);
  parts.push(`<text x="${cx0}" y="${H / 2 + 14}" text-anchor="middle" font-size="9" fill="var(--muted)">2×20 排针</text>`);
  for (const lm of board.landmarks || []) {
    if (lm.kind === "header_4p" && lm.edge === "top") {
      parts.push(`<rect x="${192 + BOARD_X}" y="${TOP_PAD - 14}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16 + BOARD_X}" y="2" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="${cx0}" y="${TOP_PAD - 1}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "header_4p" && lm.edge === "bottom") {
      parts.push(`<rect x="${192 + BOARD_X}" y="${pcbBottom - 4}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16 + BOARD_X}" y="${pcbBottom - 2}" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="${cx0}" y="${pcbBottom - 12}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "usb_typec" && lm.edge === "bottom") {
      parts.push(`<rect x="${205 + BOARD_X}" y="${pcbBottom - 30}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="${213 + BOARD_X}" y="${pcbBottom - 7}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="${cx0}" y="${pcbBottom + 8}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    } else if (lm.kind === "usb_typec" && lm.edge === "top") {
      parts.push(`<rect x="${205 + BOARD_X}" y="${TOP_PAD - 6}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="${213 + BOARD_X}" y="${TOP_PAD - 6}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="${cx0}" y="${TOP_PAD - 18}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    }
  }
  return parts;
}

/** 全部焊盘 + 丝印名（画在连线之上——工单 06 分层：线从焊盘中心起笔，焊盘
 * 圆点盖线头使线视觉从圆盘边缘起；水平线穿过标签文字时有衬底描边，文字仍
 * 可读（paint-order:stroke 先描边后填充，stroke 用面板底色）。
 * 引脚名可读性（用户反馈）：基线提亮 var(--text)（原 muted 太灰难看清）；
 * 被本步接线引用的引脚名强调 var(--accent) + 700 粗体——线与引脚名同色，
 * 一眼定位「线从哪根引脚出」。hlPins = 本步高亮线的引脚名集合。 */
function boardPinParts(board, hlPins) {
  const parts = [];
  for (const pin of (board && board.pins) || []) {
    const p = pinXY(pin);
    const io = pin.kind === "io";
    const hl = hlPins.has(pin.name);
    const labelX = p.side === "L" ? p.cx - PAD_R - 7 : p.cx + PAD_R + 7;
    const anchor = p.side === "L" ? "end" : "start";
    parts.push(`<circle cx="${p.cx}" cy="${p.cy}" r="${PAD_R}" fill="${io ? "var(--pin-pad)" : "var(--pin-fixed-pad)"}" stroke="var(--border-strong)" stroke-width="1.5"><title>${esc(String(pin.name || "") + (io ? "（空闲 IO）" : "（固定/电源）"))}</title></circle>`
      + `<text x="${labelX}" y="${p.cy + 4}" text-anchor="${anchor}" font-family="var(--mono)" font-size="${LABEL_FS}" fill="${hl ? "var(--accent)" : "var(--text)"}" font-weight="${hl ? "700" : "500"}" stroke="var(--panel-2)" stroke-width="${hl ? "3" : "2.5"}" paint-order="stroke">${esc(String(pin.name || ""))}</text>`);
  }
  return parts;
}

/** 接线图布局（工单 06 两列布线，纯函数）：lines → 每线的焊盘坐标 / 端子盒
 * 坐标 / 连线 path。规则：
 * 1. 分侧：焊盘 x=0（板左列）→ 左端子列（盒 [TERM_L_X, TERM_L_X+TERM_W]，
 *    线终点 = 盒右缘）；x=1（右列）→ 右端子列（盒左缘 TERM_R_X，线终点 =
 *    盒左缘）——跨侧线被板隔离；
 * 2. y 对齐优先：端子盒 cy = 焊盘 cy → 线为水平线（同侧同行各占一行 →
 *    零交叉）；
 * 3. 冲突兜底：同侧 ≥2 根线的焊盘 y 相同（触发条件 = 同侧同 cy；真实场景 =
 *    同一引脚在接线行出现多行，如 LED/LED_RED 双行同 pin；测试亦用等位焊盘
 *    构造）→ 该侧改等距布局：按焊盘 cy 稳定排序，端子盒依次铺
 *    TOP_PAD+ROW_H/2+k*ROW_H（侧内单调 → 不交叉、盒不重叠）。
 * 输出 [{line, pad:{cx,cy,side}, boxX, boxY, boxCy, path}]。 */
export function layoutWiring(board, lines) {
  const groupBySide = { L: [], R: [] };
  for (const line of lines) {
    const pad = padCenter(board, line.pin);
    if (!pad) continue;
    groupBySide[pad.side].push({ line, pad });
  }
  // 侧配置：线终点 x（端子盒外缘中点）与盒子起点 x
  const sideCfg = {
    L: { edgeX: TERM_L_X + TERM_W, boxX: TERM_L_X },
    R: { edgeX: TERM_R_X, boxX: TERM_R_X },
  };
  const out = [];
  for (const side of ["L", "R"]) {
    const group = groupBySide[side];
    if (!group.length) continue;
    const counts = new Map();
    for (const g of group) counts.set(g.pad.cy, (counts.get(g.pad.cy) || 0) + 1);
    const clash = [...counts.values()].some((n) => n > 1);
    const ordered = clash ? group.slice().sort((a, b) => a.pad.cy - b.pad.cy) : group;
    const cfg = sideCfg[side];
    let k = 0;
    for (const g of ordered) {
      const boxCy = clash ? TOP_PAD + ROW_H / 2 + k * ROW_H : g.pad.cy;
      k += 1;
      out.push({
        line: g.line, pad: g.pad,
        boxX: cfg.boxX, boxY: boxCy - TERM_BOX_H / 2, boxCy,
        path: "M " + g.pad.cx + " " + g.pad.cy + " L " + cfg.edgeX + " " + boxCy,
      });
    }
  }
  return out;
}

/** 接线图整块 HTML（纯函数，全部输出转义）：
 * 输入 {board, rows, wiring, showAll, inferred}——
 * board = 板定义 dict（快照内嵌 / /api/boards 同形；null = 空态）；
 * rows = 接线行（快照 rows：slug/role/role_id/pin/remark…）；
 * wiring = 本步接线引用（迭代记录 wiring：[{pin, target, note}]；tier-2
 * 增强 = wiringFromResources 反推结果，inferred: true 标注 caption 区分）；
 * showAll = 是否展开「显示全部接线」（默认 false = 只画本步高亮线）；
 * inferred = 该 wiring 是否按资源标定（非 AI 引用——caption 注明，数据纪律：
 * 两者都是同一渲染，仅来源标注不同）。
 * 空 rows / 板定义缺失 / 全非法输入 → 中文空态文案（不崩溃、不空白）。 */
export function wiringDiagramHTML({ board, rows, wiring, showAll, inferred }) {
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
  const W = TERM_R_X + TERM_W + 12;
  const parts = [];
  parts.push(`<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:900px" role="img" aria-label="${esc(board.name || "开发板")}接线图">`);
  parts.push(...boardBaseParts(board, boardRows));
  const laid = layoutWiring(board, lines);
  for (const l of laid) {
    const cls = "wiring-line" + (l.line.hl ? " wiring-hl" : " wiring-dim")
      + (l.line.power ? " wiring-power" : "");
    parts.push(`<path d="${l.path}" class="${cls}"/>`);
  }
  parts.push(...boardPinParts(board, new Set(highlight.map((l) => l.pin))));
  for (const l of laid) {
    const line = l.line;
    parts.push(`<g class="wiring-term" transform="translate(${l.boxX} ${l.boxY})">`
      + `<rect x="0" y="0" width="${TERM_W}" height="${TERM_BOX_H}" rx="4" fill="var(--panel-2)" stroke="${line.hl ? "var(--accent)" : "var(--border)"}" stroke-width="${line.hl ? "1.5" : "1"}"/>`
      + `<text x="8" y="${13}" font-size="10" fill="${line.hl ? "var(--text)" : "var(--muted)"}">${esc(line.label)}</text>`
      + (line.remark || line.note
        ? `<text x="8" y="${TERM_BOX_H + 10}" font-size="8" fill="var(--muted)">`
          + esc([line.remark, line.note].filter(Boolean).join(" · ")) + "</text>"
        : "")
      + "</g>");
  }
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
    + '<div class="wiring-caption muted">' + esc(
      (inferred ? board.name + " · 按引脚资源标定的接线" : board.name + " · 本步接线")
    ) + "</div>"
    + legend + parts.join("") + toggle + "</div>";
}
