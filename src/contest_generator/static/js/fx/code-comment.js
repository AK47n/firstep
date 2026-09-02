// fx/code-comment.js — 注释切换纯函数（工单 code-page-vscode-overhaul/02）
//
// Ctrl+/ 的两条纯件路径：toggleLineComment（逐行注释：.c/.h 用 //，XML 用
// <!-- ... -->）与 toggleBlockComment（/* */ 加/去包围）。基于
// {value, selStart, selEnd} 纯输入输出（与 fx/code-lineops.js 同约定），
// 返回 {value, start, end}；无 DOM 依赖。
//
// 逐行规则（对齐 VSCode 语义）：
// - 触及行 = 选区覆盖的行（零选区 = 当前行）；空白行跳过不参与判定；
// - 全部非空行已注释 → 去注释；否则 → 加注释（插在前导空白之后）；
// - XML 行注释为成对标记（<!-- 前缀 + --> 后缀），加/去成对对称。
// 选区语义：零选区光标按（原列 + 前后缀增量）映射；非零选区扩展为整段。

// ---- 行偏移工具（与 fx/code-lineops.js 同族独立实现）----
function lineStartsOf(v) {
  const starts = [0];
  for (let i = 0; i < v.length; i++) if (v.charCodeAt(i) === 10) starts.push(i + 1);
  return starts;
}
function lineIndexOf(starts, pos) {
  let lo = 0;
  let hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= pos) lo = mid; else hi = mid - 1;
  }
  return lo;
}
function clampSel(v, selStart, selEnd) {
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  return { start, end: Math.max(start, Math.min(v.length, selEnd | 0)) };
}
// newStartsOf(lines)：重组后行首偏移（含各行终止符）。
function newStartsOf(lines) {
  const starts = [0];
  for (let i = 0; i < lines.length; i++) {
    starts.push(starts[i] + lines[i].length + (i < lines.length - 1 ? 1 : 0));
  }
  return starts;
}

// ---- toggleLineComment ----
// opts = { open, close? }：close 空 = 行注释（//）；有 close = 成对行注释
// （XML：<!-- ... -->）。
export function toggleLineComment(value, selStart, selEnd, opts) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const o = opts || {};
  const open = String(o.open == null ? "//" : o.open);
  const close = o.close ? String(o.close) : "";
  const starts = lineStartsOf(v);
  const first = lineIndexOf(starts, start);
  let last = lineIndexOf(starts, Math.max(end - 1, start));
  if (end > start && end > 0 && v[end - 1] === "\n") {
    // 选区终点恰落行首（含前一行行尾换行）→ 触及下一行（与 lineRangeOf 同规则）
    last = lineIndexOf(starts, Math.min(end, v.length));
  }
  const lines = v.split("\n");
  const touched = [];
  for (let i = first; i <= last; i++) touched.push(i);
  const nonEmpty = touched.filter((i) => lines[i].trim().length > 0);
  if (!nonEmpty.length) return { value: v, start, end };

  const wsLen = (line) => { const m = /^[ \t]*/.exec(line); return m ? m[0].length : 0; };
  const isCommented = (line) => {
    const t = line.slice(wsLen(line));
    if (!t.startsWith(open)) return false;
    return !close || t.endsWith(close);
  };
  const allCommented = nonEmpty.every((i) => isCommented(lines[i]));

  // transform(line) → {text, delta}（delta = 本行长度变化，用于光标映射）
  const transform = (line) => {
    const ws = /^[ \t]*/.exec(line)[0];
    const body = line.slice(ws.length);
    if (!body.trim()) return { text: line, delta: 0 };
    if (!allCommented) {
      if (!close) return { text: ws + open + " " + body, delta: open.length + 1 };
      return { text: ws + open + " " + body + " " + close, delta: open.length + 1 + 1 + close.length };
    }
    // 去注释
    if (!close) {
      const cut = body.startsWith(open) ? open.length + (body[open.length] === " " ? 1 : 0) : 0;
      if (!cut) return { text: line, delta: 0 };
      return { text: ws + body.slice(cut), delta: -cut };
    }
    if (body.startsWith(open) && body.endsWith(close)) {
      let inner = body.slice(open.length, body.length - close.length);
      let cutL = 0;
      let cutR = 0;
      if (inner.startsWith(" ")) { inner = inner.slice(1); cutL = 1; }
      if (inner.endsWith(" ")) { inner = inner.slice(0, -1); cutR = 1; }
      const cut = open.length + cutL + close.length + cutR;
      return { text: ws + inner, delta: -cut };
    }
    return { text: line, delta: 0 };
  };

  const newLines = lines.slice();
  const deltas = new Array(lines.length).fill(0);
  let changed = false;
  for (const i of touched) {
    const r = transform(lines[i]);
    if (r.text !== lines[i]) changed = true;
    newLines[i] = r.text;
    deltas[i] = r.delta;
  }
  if (!changed) return { value: v, start, end };
  const nStarts = newStartsOf(newLines);
  const nv = newLines.join("\n");

  if (start === end) {
    const li = lineIndexOf(starts, start);
    const col = start - starts[li];
    const line = lines[li];
    const w = wsLen(line);
    let ncol = col;
    if (li >= first && li <= last) {
      if (allCommented) {
        ncol = col <= w ? col : Math.max(w, col + deltas[li]);
      } else {
        const prefix = close ? open.length + 1 : open.length + 1;
        const suffix = close ? 1 + close.length : 0;
        ncol = col <= w ? col : (close && col === line.length ? col + prefix + suffix : col + prefix);
      }
    }
    const pos = nStarts[li] + Math.min(ncol, newLines[li].length);
    return { value: nv, start: pos, end: pos };
  }
  return { value: nv, start: nStarts[first], end: nStarts[last] + newLines[last].length };
}

// ---- toggleBlockComment ----
// opts = { open, close }：加/去 /* */ 包围——选区恰为块注释 → 去；选区含块
// 标记但非精确块 → 去最外层对（安全方向）；无块标记 → 整体包围（加）。
export function toggleBlockComment(value, selStart, selEnd, opts) {
  const v = String(value == null ? "" : value);
  const { start, end } = clampSel(v, selStart, selEnd);
  const o = opts || {};
  const open = String(o.open == null ? "/*" : o.open);
  const close = String(o.close == null ? "*/" : o.close);
  const content = v.slice(start, end);
  if (content.startsWith(open) && content.endsWith(close)) {
    const inner = content.slice(open.length, content.length - close.length);
    return { value: v.slice(0, start) + inner + v.slice(end), start, end: start + inner.length };
  }
  const oi = content.indexOf(open);
  const ci = content.lastIndexOf(close);
  if (oi !== -1 && ci > oi) {
    const inner = content.slice(oi + open.length, ci);
    const text = v.slice(0, start) + content.slice(0, oi) + inner + content.slice(ci + close.length) + v.slice(end);
    return { value: text, start, end: start + (content.length - open.length - close.length) };
  }
  const newContent = open + content + close;
  return { value: v.slice(0, start) + newContent + v.slice(end), start, end: start + newContent.length };
}

if (typeof window !== "undefined") {
  Object.assign(window, { toggleLineComment, toggleBlockComment });
}
