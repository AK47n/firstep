// fx/edit-patch.js — 编辑器输入变更段判定 + 标记清单增量修补纯函数
// （工单 code-editor-opt/01：大文件逐键不再全量重算缩进引导线/括号彩虹）。
//
// 问题：输入事件处理链里 currentMarks 每次字符编辑都对全文重算（引导线全扫 +
// 括号扫描），CPU 采样约 20ms/击；上一轮「纯字符编辑标记沿用」的 markClean
// 门控只跳过渲染，缓存键是内容引用——内容一变缓存即失效，还是全量重算。
//
// 本模块把「这次编辑是不是结构变更 + 变更段在哪」一次算出（editChangeSpan，
// 与 ui 旧 textEditIsStructural 同口径），再对行级区间稳定的标记清单做
// 偏移修补（marksPatch）：纯字符编辑（无换行/括号/引号/#/tab 且行首空白未变）
// 时，变更行之外的标记逐字节不变（行号与行内偏移都稳定——非结构段不含换行），
// 变更行内标记按与变更段的包含关系平移。模块约定见 fx/core.js 头部。
//
// 标记形状 = {line(1 基), start(列 0 基), end, kind, title?}，与
// fx/code-marks.js 同族。
import { caretLineFromStarts } from "./codeeditor.js";

// editChangeSpan(oldText, newText, lineStarts?)：变更段判定——返回
// { identical, structural, p, oldSegLen, newSegLen, line }
//   identical   旧新文本相同（调用方另有短路）
//   structural  结构变更（换行/括号/引号/井号/tab 或行首空白变化 → 标记与折叠
//               清单不可增量，调用方走全量）
//   p           公共前缀长度（变更段起于旧/新文本的 p）
//   oldSegLen   旧文本被替换段长（删除 = 旧段长 > 0，纯插入 = 0）
//   newSegLen   新文本替换段长（插入 = 新段长 > 0，纯删除 = 0）
//   line        变更起始行（1 基，按旧文本算：p 前换行数 + 1）
// 口径与 ui/codeeditor.js 旧 textEditIsStructural 完全一致（spec 决策：纯逻辑
// 进 fx 可单测，ui 不再手写第二套）。lineStarts 可选（工单 code-editor-opt/02）：
// 窗口缓存的行起点数组 → 变更行号二分 O(log n)，避免对全文再数一遍换行。
export function editChangeSpan(oldText, newText, lineStarts) {
  const oldT = String(oldText == null ? "" : oldText);
  const newT = String(newText == null ? "" : newText);
  if (oldT === newT) {
    return { identical: true, structural: true, p: 0, oldSegLen: 0, newSegLen: 0, line: 1 };
  }
  let p = 0;
  const min = Math.min(oldT.length, newT.length);
  while (p < min && oldT[p] === newT[p]) p++;
  let s = 0;
  while (s < oldT.length - p && s < newT.length - p
    && oldT[oldT.length - 1 - s] === newT[newT.length - 1 - s]) s++;
  const oldSegLen = oldT.length - p - s;
  const newSegLen = newT.length - p - s;
  const seg = newT.slice(p, p + newSegLen);
  const oldSeg = oldT.slice(p, p + oldSegLen);
  // 结构字符判定须同时扫旧/新两段（评审整改：删除侧——删括号/换行/引号/井号/
  // tab 时新段为空，只看新段会把删除误判为非结构，增量修补会带着陈旧括号深度
  // 与行号写缓存键并持续复用）。
  let structural = /[\n{}()[\]"'#\t]/.test(seg) || /[\n{}()[\]"'#\t]/.test(oldSeg);
  if (!structural) {
    // 变更段所在行的行首空白变化（缩进引导线依赖）→ structural
    const beforeLineStart = oldT.lastIndexOf("\n", p - 1) + 1;
    const afterLineStart = newT.lastIndexOf("\n", p - 1) + 1;
    const beforeLineEnd = oldT.indexOf("\n", p);
    const afterLineEnd = newT.indexOf("\n", p);
    const oldLead = oldT.slice(beforeLineStart,
      beforeLineEnd < 0 ? oldT.length : beforeLineEnd).match(/^[ \t]*/)[0];
    const newLead = newT.slice(afterLineStart,
      afterLineEnd < 0 ? newT.length : afterLineEnd).match(/^[ \t]*/)[0];
    structural = oldLead !== newLead;
  }
  let line;
  if (lineStarts && lineStarts.length) {
    // 行起点数组二分（工单 code-editor-opt/02：6000 行逐键不再 O(n) 数换行）
    line = caretLineFromStarts(lineStarts, p);
  } else {
    line = 1;
    for (let i = 0; i < p; i++) if (oldT.charCodeAt(i) === 10) line++;
  }
  return { identical: false, structural, p, oldSegLen, newSegLen, line };
}

// marksPatch(marks, oldText, newText, span)：标记清单行级增量修补——
// 输入旧标记清单 + 旧/新文本 + editChangeSpan 的 span（必须 non-structural），
// 输出修补后的新清单（新数组，旧数组不动）。规则：
//   - 变更行之外（line < span.line 与 line > span.line）：逐字节不动——非结构
//     段不含换行，后行行号与行内偏移都稳定，前行同理。
//   - 变更行内：m.end <= segStart → 不变；m.start >= segEnd → 整体平移
//     （delta = newSegLen - oldSegLen）；跨段/包段（防御性：本次实际标记种类
//     guide/rainbow 都是单字符或短段，不会跨段）→ 起点不动、终点 + delta 并
//     钳制到起点。
// 只适用于非结构编辑；结构编辑（换行/括号等）标记行号会重新编号，调用方必须
// 走全量重算（currentMarks / bracketDepthMarks 既有路径）。
export function marksPatch(marks, oldText, newText, span) {
  const oldT = String(oldText == null ? "" : oldText);
  if (!marks || !marks.length) return [];
  if (span.identical || span.structural || span.oldSegLen === span.newSegLen) {
    // identical/结构变更：调用方不该进此路径（保守返回原样，防错用）；
    // 段等长（如替换同长字符）：线内偏移不变，原样返回。
    return marks.slice();
  }
  const lineStart = oldT.lastIndexOf("\n", span.p - 1) + 1;
  const segStart = span.p - lineStart;          // 变更段在行内的 0 基列
  const segEnd = segStart + span.oldSegLen;
  const delta = span.newSegLen - span.oldSegLen;
  const out = [];
  for (const m of marks) {
    if (!m || m.line !== span.line) { out.push(m); continue; }
    const start = m.start | 0;
    const end = m.end | 0;
    if (end <= segStart) { out.push(m); continue; }
    if (start >= segEnd) {
      out.push({ ...m, start: start + delta, end: end + delta });
      continue;
    }
    // 跨段/包段：起点不动、终点平移并钳制
    out.push({ ...m, start, end: Math.max(end + delta, start) });
  }
  return out;
}

// marksPartition(marks)：按 kind 命名域分区（评审整改——ui 不再用
// startsWith("bracket-depth-") / === "guide" 硬过滤，kind 领域知识收在 fx）：
// 返回 { all, guides, rainbow, others }——all = 原清单（同引用），guides =
// kind "guide"（缩进引导线），rainbow = kind "bracket-depth-*"（括号彩虹），
// others = 其余（查找/词/括号/错误等，增量路径通常为空）。
export function marksPartition(marks) {
  const all = marks || [];
  const guides = [];
  const rainbow = [];
  const others = [];
  for (const m of all) {
    if (m.kind === "guide") guides.push(m);
    else if (String(m.kind).startsWith("bracket-depth-")) rainbow.push(m);
    else others.push(m);
  }
  return { all, guides, rainbow, others };
}

// wordRangesPatch(ranges, word, oldText, newText, span)：选中词区段清单增量修补
// （工单 code-editor-opt/02——逐键 codeWordRanges 全文扫描 + JSON 对比是输入链
// 残余热点之一）。只适用于「非结构编辑且词未变」：词未变 ⇒ 其它行的文本与词
// 边界逐字节不变（区段原样保留），只有变更行可能变化（词边界在变更段附近被
// 改动——如 'x' 插入到 "abc" 前使其不再是 "abc" 的命中）→ 该行局部重算，
// 词边界判据与 fx/code-marks.js codeWordRanges 完全一致。输出按行序自然序
// 合并（区段形状 {line,start,end} 同族）。
export function wordRangesPatch(ranges, word, oldText, newText, span) {
  const ws = String(word == null ? "" : word);
  const oldT = String(oldText == null ? "" : oldText);
  const newT = String(newText == null ? "" : newText);
  const list = ranges || [];
  if (!ws) return list.slice();
  if (!list.length) return [];
  // 变更行局部重算（与 codeWordRanges 同口径：词边界 = 前后非词字符）
  const lineStart = oldT.lastIndexOf("\n", span.p - 1) + 1;
  const nl = newT.indexOf("\n", lineStart);
  const lineEnd = nl === -1 ? newT.length : nl;
  const lineText = newT.slice(lineStart, lineEnd);
  const isWordChar = (ch) => ch !== undefined && ch !== "" && /[A-Za-z0-9_]/.test(ch);
  const parts = [];
  for (let i = 0;;) {
    const at = lineText.indexOf(ws, i);
    if (at < 0) break;
    const prev = at > 0 ? lineText[at - 1] : "";
    const next = at + ws.length < lineText.length ? lineText[at + ws.length] : "";
    if (!isWordChar(prev) && !isWordChar(next)) {
      parts.push({ line: span.line, start: at, end: at + ws.length });
    }
    i = at + ws.length;
  }
  // 其它行原样；变更行条目在行序位置插入（保持 codeWordRanges 的自然序）
  const out = [];
  let inserted = false;
  for (const r of list) {
    if (r.line === span.line) continue;
    if (!inserted && r.line > span.line) {
      out.push(...parts);
      inserted = true;
    }
    out.push(r);
  }
  if (!inserted) out.push(...parts);
  return out;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    editChangeSpan,
    marksPatch,
    marksPartition,
    wordRangesPatch,
  });
}
