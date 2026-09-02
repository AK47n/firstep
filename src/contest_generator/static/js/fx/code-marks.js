// fx/code-marks.js — 编辑器标记层纯函数（工单 code-editor-vscode-polish/04-06）
//
// 三明治「高亮层之上、textarea 之下」的仅背景标记层（.code-marks）：查找命中
// （含当前命中）/ 选中词 / 括号配对共用同一渲染入口——标记 span 文本透明
// （层 color: transparent，文字由高亮层绘制），只显示背景；文本一律 esc 防
// 注入（fx/core.js 单源）。区段表达 = 1 基行号 + 0 基列偏移
// {line, start, end, kind}，kind ∈ hit | current | word | bracket（优先级
// current > hit > word = bracket——重叠时取高优先类）。模块约定见 fx/core.js
// 头部。
import { esc } from "./core.js";

// 标记优先级（codeMarksHTML 分割重叠区段用）：当前命中最醒目。
export const MARK_PRIORITY = { current: 3, hit: 2, word: 1, bracket: 1 };

// 词字符（工单 05）：字母 / 数字 / 下划线连续段（VSCode 语义——中文与符号
// 不构成标识符词；数字也是词字符，光标在数字上同样高亮同数字）。
const WORD_CHAR = /[A-Za-z0-9_]/;
function isWordChar(ch) {
  return ch !== undefined && ch !== "" && WORD_CHAR.test(ch);
}

// codeWordAt(text, pos)：光标处取词（工单 05）——pos 指在词内（含紧邻词尾
// 后 / 词首前）时返回该词；光标在空白 / 符号 / 汉字上 → ""（不误亮）。
// pos 越界钳到文本边界。
export function codeWordAt(text, pos) {
  const src = String(text == null ? "" : text);
  const p = Math.max(0, Math.min(src.length, pos | 0));
  let i = -1;
  if (p > 0 && isWordChar(src[p - 1])) i = p - 1;
  else if (p < src.length && isWordChar(src[p])) i = p;
  if (i < 0) return "";
  let start = i;
  while (start > 0 && isWordChar(src[start - 1])) start--;
  let end = i + 1;
  while (end < src.length && isWordChar(src[end])) end++;
  return src.slice(start, end);
}

// codeWordRanges(text, word)：同词全文区段（工单 05）——大小写**精确**匹配
// （与查找的大小写不敏感区分）+ 词边界（前后非词字符——"main_c" 不算
// "main" 的命中）；非重叠推进；空词 → []。返回 {line,start,end}（与
// codeFindRanges 同形状，供标记层渲染）。
export function codeWordRanges(text, word) {
  const src = String(text == null ? "" : text);
  const w = String(word == null ? "" : word);
  if (!w) return [];
  const out = [];
  const lines = src.split("\n");
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    let i = 0;
    for (;;) {
      const at = line.indexOf(w, i);
      if (at < 0) break;
      const prev = at > 0 ? line[at - 1] : "";
      const next = at + w.length < line.length ? line[at + w.length] : "";
      if (!isWordChar(prev) && !isWordChar(next)) {
        out.push({ line: li + 1, start: at, end: at + w.length });
      }
      i = at + w.length;
    }
  }
  return out;
}

// codeFindRanges(text, needle)：文件内查找命中区段纯件——大小写不敏感
// （与 fx/codeview.js fileFindFilter 同语义轴：查询 trim 后匹配——两处一致，
// 评审整改 04：列表与标记层结果不得背离）、按行边界切分（不跨行匹配，与
// 高亮层逐行渲染一致）；非重叠（命中后从 needle 长度处继续——"aaa" 对
// "aa" 只算 1 处，VSCode 语义）。空针 / 无匹配 → []。
export function codeFindRanges(text, needle) {
  const src = String(text == null ? "" : text);
  const n = String(needle == null ? "" : needle).trim();
  if (!n) return [];
  const lower = n.toLowerCase();
  const out = [];
  const lines = src.split("\n");
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li].toLowerCase();
    let i = 0;
    for (;;) {
      const at = line.indexOf(lower, i);
      if (at < 0) break;
      out.push({ line: li + 1, start: at, end: at + n.length });
      i = at + n.length;
    }
  }
  return out;
}

// codeIndentGuideMarks(text)：缩进引导线标记纯件（工单 code-page-vscode-overhaul/07）
// ——逐行按前导空白在 4 列对齐（tab-size 4）位置画竖线：第 k 级引导线画在
// 边界左侧最后一个空白字符上（span [4k-1, 4k)，1ch 宽，CSS 渐变画 1.5px
// 居中竖线——4 空格单级缩进也可见，与 VSCode 观感一致）；只画行首空白区
// （不覆盖文字）。纯空格缩进 = 标准 4 列对齐；tab 混入时按字符近似（本编辑
// 器缩进走空格，主路径精确）。kind 与标记层同族（"guide"）。
export function codeIndentGuideMarks(text) {
  const src = String(text == null ? "" : text);
  const out = [];
  const lines = src.split("\n");
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    let run = 0;
    while (run < line.length && (line[run] === " " || line[run] === "\t")) run++;
    for (let c = 4; c <= run; c += 4) {
      out.push({ line: li + 1, start: c - 1, end: c, kind: "guide" });
    }
  }
  return out;
}

// codeMarksHTML(text, marks)：标记层内部 HTML 单源——逐行
// span.code-mark-line[data-code-line]（与高亮层 .code-hl-line 同 data 键，
// 跳行/当前行语义可寻址）；行内按标记边界切段，重叠段取最高优先级类；
// 无标记行 = 全行纯文本（保宽度度量，文字透明不显示）；尾 \n 空行同样渲染
// （与 .code-hl-line:empty 同行齐）。marks = [{line,start,end,kind}]。
export function codeMarksHTML(text, marks) {
  const src = String(text == null ? "" : text);
  const lines = src.split("\n");
  const list = (marks || []).slice()
    .sort((a, b) => (a.line - b.line) || (a.start - b.start) || (a.end - b.end));
  const out = [];
  let mi = 0;
  for (let li = 0; li < lines.length; li++) {
    const lineNo = li + 1;
    const line = lines[li];
    const ranges = [];
    while (mi < list.length && list[mi].line === lineNo) { ranges.push(list[mi]); mi++; }
    let html = "";
    if (ranges.length) {
      const segPts = (() => {
        const s = new Set([0, line.length]);
        for (const r of ranges) {
          s.add(Math.max(0, Math.min(line.length, r.start | 0)));
          s.add(Math.max(0, Math.min(line.length, r.end | 0)));
        }
        return [...s].sort((a, b) => a - b);
      })();
      for (let k = 0; k < segPts.length - 1; k++) {
        const a = segPts[k];
        const b = segPts[k + 1];
        if (b <= a) continue;
        let best = null;
        for (const r of ranges) {
          const rs = Math.max(0, Math.min(line.length, r.start | 0));
          const re = Math.max(0, Math.min(line.length, r.end | 0));
          if (rs <= a && re >= b) {
            const pri = MARK_PRIORITY[r.kind] || 0;
            if (!best || pri > best.pri) best = { kind: r.kind, pri };
          }
        }
        const seg = line.slice(a, b);
        html += best
          ? '<span class="code-mark code-mark-' + esc(best.kind) + '">' + esc(seg) + "</span>"
          : esc(seg);
      }
    } else {
      html = esc(line);
    }
    out.push('<span class="code-marks-line" data-code-line="' + lineNo + '">'
      + html + "</span>");
  }
  return out.join("");
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    codeFindRanges,
    codeMarksHTML,
    codeWordAt,
    codeWordRanges,
    MARK_PRIORITY,
  });
}
