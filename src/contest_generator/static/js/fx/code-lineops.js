// fx/code-lineops.js — 代码编辑器行操作纯函数（工单 code-page-vscode-overhaul/01）
//
// VSCode 式行级编辑纯件：shiftTab（反缩进）/ deleteLine（删行）/ moveLine
// （移动行）/ copyLine（复制行）/ lineRangeOf（选整行）。全部基于
// {value, selStart, selEnd} 纯输入输出（与 fx/codeeditor.js indentLines 同
// 约定），无 DOM 依赖；返回 {value, start, end}（start/end = 新的选区偏移）。
// 行模型：文本按 "\n" 切分（末行无终止符；文档以 "\n" 结尾时末元素为空行），
// lineStartsOf 记录每行行首偏移（含终止符）。
//
// 移动/复制选区语义对齐 VSCode + 既有 indentLines：非零选区移动/复制后选区
// 覆盖整块（含行尾换行）；零选区长光标按「原行 + 列」映射到新位置。

// ---- 行偏移工具（局部实现，与 fx/code-fold.js 同族独立）----

// lineStartsOf(v)：行首偏移数组（starts[0] = 0；第 i 行行首 = starts[i]）。
function lineStartsOf(v) {
  const starts = [0];
  for (let i = 0; i < v.length; i++) if (v.charCodeAt(i) === 10) starts.push(i + 1);
  return starts;
}

// lineIndexOf(starts, pos)：pos 所在行（0 基）——二分最大 starts[i] ≤ pos。
function lineIndexOf(starts, pos) {
  let lo = 0;
  let hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= pos) lo = mid; else hi = mid - 1;
  }
  return lo;
}

// lineStartOf(starts, pos)：pos 所在行行首偏移。
function lineStartOf(starts, pos) {
  return starts[lineIndexOf(starts, pos)];
}

// removeIndent(line)：单行反缩进量——前导空格最多 4 个，或前导单个 tab
// （对齐 indentLines 的 4 空格档位；tab 视为一档）。
function removeIndent(line) {
  let n = 0;
  while (n < line.length && n < 4 && line[n] === " ") n++;
  if (n === 0 && line[0] === "\t") n = 1;
  return n;
}

// clampSel(v, selStart, selEnd)：选区钳制（与 indentLines 同语义）。
function clampSel(v, selStart, selEnd) {
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  return { start, end: Math.max(start, Math.min(v.length, selEnd | 0)) };
}

// ---- shiftTab：Shift+Tab 反缩进（与 indentLines 对称）----
// 多行选区（起始行 ≠ 尾行）→ 触及的每行去一档缩进、选区扩展为整段；
// 单行（含零长选区）→ 当前行去一档，选区/光标按删除量左移（落在被删缩进
// 内 → 钳回行首）。
export function shiftTab(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const starts = lineStartsOf(v);
  const startLine = lineStartOf(starts, start);
  const endLine = lineStartOf(starts, Math.max(end - 1, start));
  if (startLine !== endLine) {
    const segEnd = (() => {
      const nl = v.indexOf("\n", endLine);
      return nl === -1 ? v.length : nl;
    })();
    const segment = v.slice(startLine, segEnd);
    const out = segment.split("\n").map((l) => l.slice(removeIndent(l))).join("\n");
    return {
      value: v.slice(0, startLine) + out + v.slice(segEnd),
      start: startLine,
      end: startLine + out.length,
    };
  }
  const lineEnd = (() => {
    const nl = v.indexOf("\n", startLine);
    return nl === -1 ? v.length : nl;
  })();
  const line = v.slice(startLine, lineEnd);
  const n = removeIndent(line);
  if (!n) return { value: v, start, end };
  const text = v.slice(0, startLine) + line.slice(n) + v.slice(lineEnd);
  const shift = (pos) => (pos <= startLine + n ? startLine : pos - n);
  return { value: text, start: shift(start), end: shift(end) };
}

// ---- deleteLine：Ctrl+Shift+K 删除选中触及的完整行 ----
// 删除 first..last 行的整段（含各行的行尾换行）；末行无终止符时连同其前
// 换行一并删除（VSCode 行为：文件末行删掉后与上一行合并）；删空文档 → ""。
// 光标落在被删段起点（= 上一段末尾）。
export function deleteLine(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const starts = lineStartsOf(v);
  const first = lineIndexOf(starts, start);
  const last = lineIndexOf(starts, Math.max(end - 1, start));
  let delStart = starts[first];
  const delEnd = last + 1 < starts.length ? starts[last + 1] : v.length;
  if (delEnd === v.length && last === starts.length - 1 && delStart > 0) {
    // 删除触及文档末行（末行无终止符，或末尾空行）：连同其前一个换行
    delStart -= 1;
  }
  const text = v.slice(0, delStart) + v.slice(delEnd);
  const caret = Math.min(delStart, text.length);
  return { value: text, start: caret, end: caret };
}

// ---- moveLine / copyLine：行移动与复制（共用映射）----
// 行号映射规则（dir = "up" | "down"）：
//   move：块整体移位一行——down 时块后一行补到块原位（j = last+1 → j-len），
//         up 时块前一行动到块原位（j = first-1 → j+len）。
//   copy：副本插入——down 插块后（原 j → j+len），up 插块前（原 j 保持，
//         块前各行后移 len）。

// mapLineIndex(j, first, last, len, dir)：旧行号 → 新行号。
function mapLineIndex(j, first, last, len, dir, copy) {
  const inBlock = j >= first && j <= last;
  if (copy) {
    if (dir === "down") return inBlock ? j + len : (j > last ? j + len : j);
    return inBlock ? j : (j < first ? j + len : j);
  }
  if (inBlock) return dir === "down" ? j + 1 : j - 1;
  if (dir === "down") return j === last + 1 ? j - len : j;
  return j === first - 1 ? j + len : j;
}

// newStartsOf(lines)：重组后行首偏移（含各行终止符）。
function newStartsOf(lines) {
  const starts = [0];
  for (let i = 0; i < lines.length; i++) {
    starts.push(starts[i] + lines[i].length + (i < lines.length - 1 ? 1 : 0));
  }
  return starts;
}

// lineBlockResult(v, start, end, nv, arr, nStarts, first, last, len, dir, copy)：
// 移动/复制后选区映射——零选区：光标按（旧行，列）映射；非零选区：整块。
function lineBlockResult(v, start, end, nv, arr, nStarts, first, last, len, dir, copy) {
  if (start === end) {
    const starts = lineStartsOf(v);
    const li = lineIndexOf(starts, start);
    const col = start - starts[li];
    const ni = mapLineIndex(li, first, last, len, dir, copy);
    const pos = nStarts[ni] + Math.min(col, arr[ni].length);
    return { value: nv, start: pos, end: pos };
  }
  const nf = mapLineIndex(first, first, last, len, dir, copy);
  const nl = mapLineIndex(last, first, last, len, dir, copy);
  const s = nStarts[nf];
  const e = nStarts[nl] + arr[nl].length + (nl < arr.length - 1 ? 1 : 0);
  return { value: nv, start: s, end: e };
}

// moveLine(value, selStart, selEnd, dir)：Alt+↑/↓ 移动选中触及的整行——
// dir = "up" | "down"；移动后选区跟随块；边界原样返回（no-op）。
export function moveLine(value, selStart, selEnd, dir) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const lines = v.split("\n");
  const starts = lineStartsOf(v);
  const first = lineIndexOf(starts, start);
  const last = lineIndexOf(starts, Math.max(end - 1, start));
  const len = last - first + 1;
  const up = dir === "up";
  if (up ? first === 0 : last === lines.length - 1) {
    return { value: v, start, end };
  }
  const block = lines.slice(first, last + 1);
  const arr = lines.slice();
  arr.splice(first, len);
  arr.splice(up ? first - 1 : first + 1, 0, ...block);
  const nv = arr.join("\n");
  return lineBlockResult(v, start, end, nv, arr, newStartsOf(arr), first, last, len, dir, false);
}

// copyLine(value, selStart, selEnd, dir)：Shift+Alt+↑/↓ 复制选中触及的整行
// ——副本插块前（up）/块后（down），光标/选区落在副本。
export function copyLine(value, selStart, selEnd, dir) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const lines = v.split("\n");
  const starts = lineStartsOf(v);
  const first = lineIndexOf(starts, start);
  const last = lineIndexOf(starts, Math.max(end - 1, start));
  const len = last - first + 1;
  const block = lines.slice(first, last + 1);
  const arr = lines.slice();
  arr.splice(dir === "up" ? first : last + 1, 0, ...block);
  const nv = arr.join("\n");
  return lineBlockResult(v, start, end, nv, arr, newStartsOf(arr), first, last, len, dir, true);
}

// ---- lineRangeOf：Ctrl+L 选整行（含行尾换行；重复按扩展）----
// 返回 {start, end}（end 不含）；零长选区 → 当前行；已有选区终点恰落在行首
// （选区含前一行行尾换行）→ 扩展到该行；末行无换行 → 到文末。
export function lineRangeOf(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const starts = lineStartsOf(v);
  const first = lineStartOf(starts, start);
  let last = lineStartOf(starts, Math.max(end - 1, start));
  if (end > start && end > 0 && v[end - 1] === "\n") {
    last = lineStartOf(starts, Math.min(end, v.length));
  }
  const nl = v.indexOf("\n", last);
  return { start: first, end: nl === -1 ? v.length : nl + 1 };
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    shiftTab,
    deleteLine,
    moveLine,
    copyLine,
    lineRangeOf,
  });
}
