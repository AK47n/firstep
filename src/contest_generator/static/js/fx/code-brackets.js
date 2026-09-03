// fx/code-brackets.js — 括号配对与自动闭合纯函数（工单 code-editor-vscode-polish/06）
//
// 键盘行为纯件：开括号自动闭合（bracketOpen——无选区插对居中 / 有选区包裹）、
// 右括号跳过与整对替换（bracketClose）、空括号对退格删除（bracketBackspace）；
// 配对高亮（bracketPairAt——括号配对表一次正向扫描：深度匹配 + 跳过字符串 /
// 字符 / 单行注释 / 块注释内假括号，返回 1 基行号 + 0 基列偏移的标记两段）。
// 全部无副作用（纯字符串输入输出）；模块约定见 fx/core.js 头部。
// XML 的假括号防护：注释 / CDATA 内含的括号同样不配对（见 _skipRange）。
export const BRACKET_OPEN = { "(": ")", "[": "]", "{": "}" };
export const BRACKET_CLOSE = { ")": "(", "]": "[", "}": "{" };

// bracketOpen(value, selStart, selEnd, openChar)：输入开括号自动闭合——
// 无选区：插入 open+close 对、光标居中；有选区：括号对包裹选区（VSCode
// 行为）。返回 {value, start, end}（start/end = 新光标位，选区折叠为空）。
export function bracketOpen(value, selStart, selEnd, openChar) {
  const v = String(value == null ? "" : value);
  const close = BRACKET_OPEN[openChar] || openChar;
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  const end = Math.max(start, Math.min(v.length, selEnd | 0));
  const pos = start + openChar.length;
  return {
    value: v.slice(0, start) + openChar + v.slice(start, end) + close + v.slice(end),
    start: pos,
    end: pos,
  };
}

// bracketClose(value, selStart, selEnd, closeChar)：输入右括号——
// ① 选区恰为任意成对括号（如选 "()" 输入 "]"）→ 整对替换为 closeChar 的
//    成对（VSCode typing over pair：成 "[]" 光标居中）；
// ② 空选区且下一字符 == closeChar → 跳过（不重复输入），光标后移一位；
// ③ 其余 → null（胶水走浏览器默认插入）。均返回 {value, start, end}。
export function bracketClose(value, selStart, selEnd, closeChar) {
  const v = String(value == null ? "" : value);
  const open = BRACKET_CLOSE[closeChar];
  if (!open) return null;
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  const end = Math.max(start, Math.min(v.length, selEnd | 0));
  if (end > start) {
    const sel = v.slice(start, end);
    if (sel.length === 2 && BRACKET_OPEN[sel[0]] === sel[1]) {
      const pos = start + open.length;
      return {
        value: v.slice(0, start) + open + closeChar + v.slice(end),
        start: pos,
        end: pos,
      };
    }
    return null;   // 一般选区：默认替换（不特殊处理）
  }
  if (v[start] === closeChar) {
    return { value: v, start: start + 1, end: start + 1 };
  }
  return null;
}

// bracketBackspace(value, selStart, selEnd)：空选区且光标位于空括号对中间
// （前一字符 = 开括号、当前字符 = 其配对闭括号）→ 一次退格删除整对；
// 其余 → null（胶水走浏览器默认退格）。返回 {value, start, end}。
export function bracketBackspace(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  const end = Math.max(start, Math.min(v.length, selEnd | 0));
  if (start !== end || start <= 0 || start >= v.length) return null;
  const open = v[start - 1];
  if (!BRACKET_OPEN[open] || v[start] !== BRACKET_OPEN[open]) return null;
  const pos = start - 1;
  return { value: v.slice(0, pos) + v.slice(start + 1), start: pos, end: pos };
}

// ---- 配对扫描：一次正向建立配对表（深度匹配 + 假括号跳过） ----
// _skipQuote(text, i)：i 指向 " 或 ' ——跳到闭引号后（含 \" 转义；
// 行尾未闭合 → 跳到行尾，避免跨行误配对）。
function _skipQuote(text, i) {
  const q = text[i];
  let j = i + 1;
  while (j < text.length) {
    if (text[j] === "\\") { j += 2; continue; }
    if (text[j] === q) return j + 1;
    if (text[j] === "\n") return j;   // 未闭合：本行视为字符串结束
    j++;
  }
  return text.length;
}

// _skipComment(text, i)：i 指向 "//" 或 "/*" ——跳到注释终后；未闭合 → 尾。
function _skipComment(text, i) {
  if (text[i + 1] === "/") {
    const nl = text.indexOf("\n", i + 2);
    return nl < 0 ? text.length : nl;
  }
  const e = text.indexOf("*/", i + 2);
  return e < 0 ? text.length : e + 2;
}

// bracketPairScan(text)：单次正向扫描建配对清单——[{openPos, closePos,
// openChar, closeChar, depth, openLine, openStart, closeLine, closeStart}]
// （配对/深度/行列一次算齐；depth 0 基 = 最外层 0；行号 1 基、列 0 基）；
// 跳过字符串/字符/行注释/块注释内的假括号；栈只压同型开括号，碰到同型闭
// 括号时配最近开括号。配对表（_bracketPairsOf）与彩虹深度标记
// （bracketDepthMarks）与 ui 配对缓存（工单 code-editor-opt/02——按内容引用
// 缓存 + pairScanPatch 增量修补）共用本扫描——假括号跳过规则只维护一处。
export function bracketPairScan(text) {
  const out = [];
  const stack = [];
  let line = 1, lineStart = 0;
  const advance = (from, to) => {   // 跨过跳过段时同步行号/行首（总进度单调，O(n)）
    for (let k = from; k < to; k++) {
      if (text[k] === "\n") { line++; lineStart = k + 1; }
    }
  };
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      const j = _skipQuote(text, i);
      advance(i, j);
      i = j;
      continue;
    }
    if (ch === "/" && (text[i + 1] === "/" || text[i + 1] === "*")) {
      const j = _skipComment(text, i);
      advance(i, j);
      i = j;
      continue;
    }
    if (BRACKET_OPEN[ch]) {
      stack.push({ ch, pos: i, depth: stack.length, line, start: i - lineStart });
      i++;
      continue;
    }
    if (BRACKET_CLOSE[ch] && stack.length
      && stack[stack.length - 1].ch === BRACKET_CLOSE[ch]) {
      const o = stack.pop();
      out.push({
        openPos: o.pos, closePos: i, openChar: o.ch, closeChar: ch,
        depth: o.depth,
        openLine: o.line, openStart: o.start,
        closeLine: line, closeStart: i - lineStart,
      });
      i++;
      continue;
    }
    if (ch === "\n") { line++; lineStart = i + 1; }
    i++;
  }
  return out;
}

// _bracketPairsOf(text)：配对表——Map<pos, {openPos, closePos, openChar,
// closeChar}>（开/闭两个 pos 都指向同一 entry）；由 _bracketPairScan 派生
// （扫描与假括号跳过只维护一处）。
function _bracketPairsOf(text) {
  const pairs = new Map();
  for (const e of bracketPairScan(text)) {
    const entry = {
      openPos: e.openPos, closePos: e.closePos,
      openChar: e.openChar, closeChar: e.closeChar,
    };
    pairs.set(e.openPos, entry);
    pairs.set(e.closePos, entry);
  }
  return pairs;
}

// _offsetToLineCol(text, offset)：绝对偏移 → 1 基行号 + 0 基列（标记层
// {line,start,end} 形状：start = 列、end = 列 + 1——单字符段）。
function _offsetToLineCol(text, offset) {
  const lineStart = text.lastIndexOf("\n", offset - 1) + 1;
  let line = 1;
  for (let i = 0; i < offset; i++) if (text[i] === "\n") line++;
  return { line, start: offset - lineStart, end: offset - lineStart + 1 };
}

// bracketPairAt(text, pos)：光标在括号上或紧邻（pos 或 pos-1 命中配对表）→
// 返回 {open:{line,start,end}, close:{line,start,end}, openChar, closeChar}；
// 无配对 / 不在括号 → null。供胶水转标记层（kind: "bracket"）。
export function bracketPairAt(text, pos) {
  const src = String(text == null ? "" : text);
  const p = Math.max(0, Math.min(src.length, pos | 0));
  // 前置短路（评审整改 06）：光标不在括号上/紧邻（p 与 p-1 都不是括号）→
  // 免全文档配对表扫描。两处都要查——p 上是普通字符时不得吞掉 p-1 检查。
  const here = src[p] || "";
  const prev = p > 0 ? src[p - 1] : "";
  if (!BRACKET_OPEN[here] && !BRACKET_CLOSE[here]
    && !BRACKET_OPEN[prev] && !BRACKET_CLOSE[prev]) return null;
  const pairs = _bracketPairsOf(src);
  const entry = pairs.get(p) || (p > 0 ? pairs.get(p - 1) : null);
  if (!entry) return null;
  return {
    open: _offsetToLineCol(src, entry.openPos),
    close: _offsetToLineCol(src, entry.closePos),
    openChar: entry.openChar,
    closeChar: entry.closeChar,
  };
}

// bracketDepthMarks(text)：括号彩虹深度标记纯件（工单 code-editor-refine/04）——
// 由 _bracketPairScan 派生（与 bracketPairAt 共用同一次扫描与假括号跳过规则）：
// 栈深 = 嵌套深度（最外层 0），开/闭两个字符都输出单字符标记
// {line,start,end,kind:"bracket-depth-N"}，N = 深度 % 8（8 色环颜色索引）；
// 只有真正配成的对才输出（未配对 / 字符串 / 注释内括号不误着色）；
// 行号 1 基、列 0 基。供标记层（currentMarks 追加 → codeMarksHTML 按 kind
// 出 class）按深度着色。
export function bracketDepthMarks(text) {
  const src = String(text == null ? "" : text);
  const out = [];
  for (const e of bracketPairScan(src)) {
    const kind = "bracket-depth-" + (e.depth % 8);
    out.push({ line: e.openLine, start: e.openStart, end: e.openStart + 1, kind });
    out.push({ line: e.closeLine, start: e.closeStart, end: e.closeStart + 1, kind });
  }
  return out;
}

// pairScanPatch(entries, oldText, newText, span)：配对清单增量修补
// （工单 code-editor-opt/02——bracketPairAt 逐键全文档重扫 + 重建 Map 是输入链
// 剩余热点之一：光标贴 `}`/`{` 时每次 input 都触发）。只适用于非结构编辑
// （span.structural === false）：变更段不含换行与括号 → 括号集合与配对关系、
// 深度、行号全部不变，只有「变更行内位于变更段之后」的括号绝对/行内偏移
// 平移 delta；其余条目逐字节不动（引用保留）。输出新数组（旧数组不动）。
export function pairScanPatch(entries, oldText, newText, span) {
  const oldT = String(oldText == null ? "" : oldText);
  if (!entries || !entries.length) return [];
  if (span.identical || span.structural || span.oldSegLen === span.newSegLen) {
    return entries.slice();
  }
  const lineStart = oldT.lastIndexOf("\n", span.p - 1) + 1;
  const segStart = span.p - lineStart;          // 变更段在变更行内的 0 基列
  const segEnd = segStart + span.oldSegLen;
  const absSegEnd = span.p + span.oldSegLen;    // 变更段结束的绝对偏移
  const delta = span.newSegLen - span.oldSegLen;
  const out = [];
  for (const e of entries) {
    // 只克隆实际变化的条目（文件尾部输入时绝大多数条目不变——避免 6000 行
    // 文件逐键克隆整个配对清单产生的 GC，工单 code-editor-opt/02 实测热点）
    const openPos = e.openPos >= absSegEnd ? e.openPos + delta : e.openPos;
    const closePos = e.closePos >= absSegEnd ? e.closePos + delta : e.closePos;
    const openStart = (e.openLine === span.line && e.openStart >= segEnd)
      ? e.openStart + delta : e.openStart;
    const closeStart = (e.closeLine === span.line && e.closeStart >= segEnd)
      ? e.closeStart + delta : e.closeStart;
    if (openPos !== e.openPos || closePos !== e.closePos
      || openStart !== e.openStart || closeStart !== e.closeStart) {
      out.push({ ...e, openPos, closePos, openStart, closeStart });
    } else {
      out.push(e);
    }
  }
  return out;
}

// bracketPairFromEntries(entries, pos)：配对清单 → 光标处配对两段标记
// （与 bracketPairAt 同语义：pos 或 pos-1 命中任一开/闭位；无 → null）。
// 供 ui 配对缓存路径使用（避免逐键 bracketPairAt 全文档重扫）。
export function bracketPairFromEntries(entries, pos) {
  const list = entries || [];
  const p = Math.max(0, pos | 0);
  for (const e of list) {
    if (e.openPos === p || e.closePos === p || e.openPos === p - 1 || e.closePos === p - 1) {
      return {
        open: { line: e.openLine, start: e.openStart, end: e.openStart + 1 },
        close: { line: e.closeLine, start: e.closeStart, end: e.closeStart + 1 },
        openChar: e.openChar,
        closeChar: e.closeChar,
      };
    }
  }
  return null;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    BRACKET_OPEN,
    BRACKET_CLOSE,
    bracketOpen,
    bracketClose,
    bracketBackspace,
    bracketPairAt,
    bracketDepthMarks,
    bracketPairScan,
    pairScanPatch,
    bracketPairFromEntries,
  });
}
