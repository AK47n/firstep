// fx/code-fold.js — 代码折叠纯函数（工单 code-editor-vscode-polish/07）
//
// 折叠三件事全在纯件：①折叠区计算（.c/.h 花括号配对——跳过字符串/字符/
// 注释内假括号、同行 {} 不折叠、嵌套按深度；.md 标题层级——折叠到同层或
// 更高层标题前，子标题并入上层区）；②可见行映射（被折叠区替换为占位行，
// 行号保留模型真实行号）；③视图 ↔ 模型偏移映射与编辑回写（编辑经静态映射
// 写回模型——模型是全量基线，保存/脏判定/冲突/磁盘感知全基于模型；占位行
// 被编辑 → 返回需展开的折叠区并按 VSCode 近似语义替换隐藏块）。
// 无 DOM/副作用；模块约定见 fx/core.js 头部。
//
// 占位行文本用「… N 行」（无 HTML 输出，不引 esc）；gutter 行号 span 生成
// 也在此（纯数字 + 固定字符，无用户文本）。

// ---- 行偏移工具 ----
function lineStartsOf(src) {
  const starts = [0];
  for (let i = 0; i < src.length; i++) if (src[i] === "\n") starts.push(i + 1);
  return starts;
}

function lineOfOffset(starts, off) {
  let lo = 0;
  let hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= off) lo = mid; else hi = mid - 1;
  }
  return lo + 1;
}

// ---- 字符串/注释跳过（与 fx/code-brackets.js 同语义；各模块局部实现——
// 跳过规则一致但属不同域（配对表 vs 折叠区），抽出共享会引入跨域耦合）----
function skipQuote(text, i) {
  const q = text[i];
  let j = i + 1;
  while (j < text.length) {
    if (text[j] === "\\") { j += 2; continue; }
    if (text[j] === q) return j + 1;
    if (text[j] === "\n") return j;
    j++;
  }
  return text.length;
}

function skipComment(text, i) {
  if (text[i + 1] === "/") {
    const nl = text.indexOf("\n", i + 2);
    return nl < 0 ? text.length : nl;
  }
  const e = text.indexOf("*/", i + 2);
  return e < 0 ? text.length : e + 2;
}

// codeFoldRanges(content, lang)：折叠区清单——[{startLine, endLine}]（1 基；
// 隐藏 = startLine+1..endLine；按 startLine 排序；.c 嵌套内层在前）。
// 语言门控（评审整改 07b）：仅 .c/.h（lang === "c"）走花括号、.md 走标题
// 层级；xml/plain/txt 无折叠区（spec：折叠对象只有 .c/.h 与 .md）。
export function codeFoldRanges(content, lang) {
  const src = String(content == null ? "" : content);
  if (lang === "md") return mdFoldRanges(src);
  if (lang === "c") return cFoldRanges(src);
  return [];
}

function cFoldRanges(src) {
  const starts = lineStartsOf(src);
  const folds = [];
  const stack = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '"' || ch === "'") { i = skipQuote(src, i); continue; }
    if (ch === "/" && (src[i + 1] === "/" || src[i + 1] === "*")) {
      i = skipComment(src, i);
      continue;
    }
    if (ch === "{") {
      stack.push(i);
    } else if (ch === "}" && stack.length) {
      const open = stack.pop();
      const ol = lineOfOffset(starts, open);
      const cl = lineOfOffset(starts, i);
      if (cl > ol) folds.push({ startLine: ol, endLine: cl });
    }
    i++;
  }
  return folds;
}

function mdFoldRanges(src) {
  const lines = src.split("\n");
  const heads = [];
  for (let k = 0; k < lines.length; k++) {
    const m = /^(#{1,6})[ \t]/.exec(lines[k]);
    if (m) heads.push({ line: k + 1, level: m[1].length });
  }
  const folds = [];
  for (let k = 0; k < heads.length; k++) {
    const h = heads[k];
    let end = lines.length;
    for (let j = k + 1; j < heads.length; j++) {
      if (heads[j].level <= h.level) { end = heads[j].line - 1; break; }
    }
    if (end > h.line) folds.push({ startLine: h.line, endLine: end });
  }
  return folds;
}

// codeFoldPlaceholderText(count)：占位行文案（「… N 行」）。
export function codeFoldPlaceholderText(count) {
  return "… " + Math.max(1, count | 0) + " 行";
}

// codeFoldVisible(content, folds, foldedSet)：视图模型——
// lines = [{no（模型行号）, text, placeholder, count, fold（折叠索引，-1 无）,
//           foldStart（是否某折叠区开行）, folded}] 按可见顺序；
// text = 可见文本（textarea 值，占位行 = 占位文案）；
// segs = [{viewStart, viewLen, modelStart, modelLen, textLen, placeholder,
//          fold}] —— 每行一段（含行尾 \n，末行无 \n；占位段 modelLen = 隐藏
//          区字符数、textLen = 占位文案字符数）。视图↔模型映射的数据源。
export function codeFoldVisible(content, folds, foldedSet) {
  const src = String(content == null ? "" : content);
  const lines = src.split("\n");
  const foldsArr = folds || [];
  const folded = foldedSet || new Set();
  const byStart = new Map();
  foldsArr.forEach((f, i) => { if (folded.has(i)) byStart.set(f.startLine, i); });
  const out = [];
  const segs = [];
  let viewPos = 0;
  let modelPos = 0;
  let ln = 1;
  while (ln <= lines.length) {
    const fIdx = byStart.get(ln);
    if (fIdx !== undefined) {
      const f = foldsArr[fIdx];
      const lineText = lines[ln - 1];
      const noNl = ln < lines.length ? 1 : 0;
      out.push({
        no: ln, text: lineText, placeholder: false, fold: fIdx,
        foldStart: true, folded: true,
      });
      segs.push({
        viewStart: viewPos, viewLen: lineText.length + noNl,
        modelStart: modelPos, modelLen: lineText.length + noNl,
        textLen: lineText.length, placeholder: false, fold: fIdx,
      });
      viewPos += lineText.length + noNl;
      modelPos += lineText.length + noNl;
      // 占位行
      const hiddenStart = modelPos;
      let hiddenEnd = modelPos;
      for (let k = f.startLine + 1; k <= f.endLine; k++) {
        hiddenEnd += lines[k - 1].length + (k < lines.length ? 1 : 0);
      }
      const ph = codeFoldPlaceholderText(f.endLine - f.startLine);
      const phNl = 1;
      out.push({
        no: f.startLine + 1, text: ph, placeholder: true,
        count: f.endLine - f.startLine, fold: fIdx, modelNo: f.startLine,
      });
      segs.push({
        viewStart: viewPos, viewLen: ph.length + phNl,
        modelStart: hiddenStart, modelLen: hiddenEnd - hiddenStart,
        textLen: ph.length, placeholder: true, fold: fIdx,
      });
      viewPos += ph.length + phNl;
      modelPos = hiddenEnd;
      ln = f.endLine + 1;
      continue;
    }
    const lineText = lines[ln - 1];
    const noNl = ln < lines.length ? 1 : 0;
    out.push({ no: ln, text: lineText, placeholder: false, fold: -1, foldStart: false, folded: false });
    segs.push({
      viewStart: viewPos, viewLen: lineText.length + noNl,
      modelStart: modelPos, modelLen: lineText.length + noNl,
      textLen: lineText.length, placeholder: false, fold: -1,
    });
    viewPos += lineText.length + noNl;
    modelPos += lineText.length + noNl;
    ln++;
  }
  return { lines: out, text: out.map((l) => l.text).join("\n"), segs };
}

// codeFoldViewToModel(segs, viewOffset)：视图偏移 → 模型偏移——占位段内：
// 未到占位文末 → 隐藏区起点；到占位文末 → 隐藏区终点（「在折叠后继续输入」
// 语义）；普通段 → 段内线性映射。
export function codeFoldViewToModel(segs, viewOffset) {
  const list = segs || [];
  const off = Math.max(0, viewOffset | 0);
  for (const s of list) {
    if (off < s.viewStart + s.viewLen) {
      if (s.placeholder) {
        const delta = off - s.viewStart;
        return delta >= s.textLen ? s.modelStart + s.modelLen : s.modelStart;
      }
      return s.modelStart + Math.min(delta0(off - s.viewStart), s.modelLen);
    }
  }
  const last = list[list.length - 1];
  return last ? last.modelStart + last.modelLen : 0;
}
function delta0(n) { return Math.max(0, n); }

// codeFoldModelToView(segs, modelOffset)：模型偏移 → 视图偏移（占位段内 →
// 占位文末，即隐藏区折叠后的可视位置）。
export function codeFoldModelToView(segs, modelOffset) {
  const list = segs || [];
  const off = Math.max(0, modelOffset | 0);
  for (const s of list) {
    if (off <= s.modelStart + s.modelLen) {
      if (s.placeholder) {
        return off <= s.modelStart ? s.viewStart : s.viewStart + s.textLen;
      }
      return s.viewStart + Math.min(Math.max(0, off - s.modelStart), s.textLen);
    }
  }
  const last = list[list.length - 1];
  return last ? last.viewStart + last.textLen : 0;
}

// codeFoldMapEdit(model, segs, oldView, newView)：把视图文本编辑写回模型——
// 公共前后缀 diff → 偏移映射到模型（无占位触碰）；碰触占位行 → 展开该折叠
// 区（expand 返回索引清单）并按 VSCode 近似语义替换隐藏块（整块覆盖）或
// 在隐藏区起点插入（部分触碰）。返回 {model, expand, caret}（caret = 编辑后
// 光标模型偏移，供胶水映射回视图）。
export function codeFoldMapEdit(model, segs, oldView, newView) {
  const m = String(model == null ? "" : model);
  const ov = String(oldView == null ? "" : oldView);
  const nv = String(newView == null ? "" : newView);
  if (ov === nv) return { model: m, expand: [], caret: 0 };
  let p = 0;
  const minLen = Math.min(ov.length, nv.length);
  while (p < minLen && ov[p] === nv[p]) p++;
  let s = 0;
  while (s < ov.length - p && s < nv.length - p
    && ov[ov.length - 1 - s] === nv[nv.length - 1 - s]) s++;
  const qOld = ov.length - s;
  const qNew = nv.length - s;
  const mid = nv.slice(p, qNew);
  const touched = [];
  const cover = [];
  for (const sp of segs || []) {
    if (!sp.placeholder) continue;
    if (p < sp.viewStart + sp.viewLen && qOld > sp.viewStart) {
      touched.push(sp);
      if (p <= sp.viewStart && qOld >= sp.viewStart + sp.textLen) cover.push(sp);
    }
  }
  if (touched.length) {
    const expand = [...new Set(touched.map((sp) => sp.fold))];
    const coverSet = new Set(cover);
    // 隐藏块 = 完整行：替换文本补行尾换行（用户用一行文本替代 N 行隐藏区，
    // VSCode 近似语义——mid 无 \n 则补，否则文本粘连下一行）。
    const repl = mid ? (mid.endsWith("\n") ? mid : mid + "\n") : "";
    let out = m;
    let caret = 0;
    const sorted = touched.slice().sort((a, b) => b.modelStart - a.modelStart);
    for (const sp of sorted) {
      if (coverSet.has(sp)) {
        out = out.slice(0, sp.modelStart) + repl + out.slice(sp.modelStart + sp.modelLen);
        caret = sp.modelStart + repl.length;
      } else {
        out = out.slice(0, sp.modelStart) + mid + out.slice(sp.modelStart);
        caret = sp.modelStart + mid.length;
      }
    }
    return { model: out, expand, caret };
  }
  const mp = codeFoldViewToModel(segs, p);
  const mq = codeFoldViewToModel(segs, qOld);
  return {
    model: m.slice(0, mp) + mid + m.slice(mq),
    expand: [],
    caret: mp + mid.length,
  };
}

// codeFoldModelGutterLines(lines, folds)：**未折叠态**的行号 gutter 行描述
// （工单 code-fold-arrow/01）——平铺文本行 + 折叠区开行标 {foldStart: true,
// fold: idx, folded: false}，交给 codeFoldGutterLines 渲染（箭头 markup 单源，
// 不复制）。未折叠态此前直接走 lines.map(codeGutterLineHTML)（无箭头）→ 可
// 折叠行没有鼠标折叠入口（只有 Ctrl+Shift+[ 的键盘路径）。
// lines = 模型行数组（split("\n")）；folds = codeFoldRanges 输出（1 基行号）。
export function codeFoldModelGutterLines(lines, folds) {
  const starts = new Map();
  (folds || []).forEach((f, i) => {
    if (f && f.startLine >= 1) starts.set(f.startLine, i);
  });
  return (lines || []).map((text, i) => {
    const no = i + 1;
    const fIdx = starts.get(no);
    return fIdx === undefined
      ? { no, text, placeholder: false, fold: -1, foldStart: false, folded: false }
      : { no, text, placeholder: false, fold: fIdx, foldStart: true, folded: false };
  });
}

// codeFoldGutterLines(lines)：行号 gutter 逐行字符串数组（工单
// code-page-vscode-overhaul/08 窗口化——滑动窗口切片用；与
// codeFoldGutterHTML 单源）。每行 span.code-gutter-line[data-code-line =
// 模型行号]；折叠区开行内嵌折叠箭头（span.code-fold-arrow[data-fold]，
// 未折叠 = ▾、已折叠 = ▸）；占位行 span.code-gutter-ph[data-fold-expand]
// （点开 = 展开，title 提示）。内容全为数字 / 固定字符，无用户文本（无需
// esc）。
export function codeFoldGutterLines(lines) {
  return (lines || []).map((l) => {
    if (l.placeholder) {
      return '<span class="code-gutter-line code-gutter-ph" data-code-line="' + l.no + '"'
        + ' data-fold-expand="' + l.fold + '" title="展开折叠区">'
        + (l.count || 0) + "</span>";
    }
    const arrow = l.foldStart
      ? '<span class="code-fold-arrow' + (l.folded ? "" : " open") + '"'
        + ' data-fold="' + l.fold + '" role="button"'
        + ' title="' + (l.folded ? "展开" : "折叠") + '">'
        + (l.folded ? "▸" : "▾") + "</span>"
      : "";
    return '<span class="code-gutter-line" data-code-line="' + l.no + '">'
      + arrow + l.no + "</span>";
  });
}

// codeFoldGutterHTML(lines)：行号 gutter HTML（可见行）——codeFoldGutterLines
// 拼接（保持既有调用面）。
export function codeFoldGutterHTML(lines) {
  return codeFoldGutterLines(lines).join("");
}

// codeFoldMerge(oldFolds, oldSet, newFolds)：内容变化后保留仍存在的折叠态——
// 签名（startLine,endLine）相同即保留索引（折叠区随内容漂移后自然放弃，
// 用户重新折叠即可；不追复杂映射）。O(n) 键集实现（工单 11 性能整改：原
// 逐对 some 扫描在 3000+ 折叠下每次击键 ~52ms——大文件逐键卡顿主因之一）。
export function codeFoldMerge(oldFolds, oldSet, newFolds) {
  const old = oldFolds || [];
  const oldFolded = oldSet || new Set();
  const keySet = new Set();
  old.forEach((of, oi) => {
    if (oldFolded.has(oi)) keySet.add(of.startLine + ":" + of.endLine);
  });
  const newSet = new Set();
  (newFolds || []).forEach((f, i) => {
    if (keySet.has(f.startLine + ":" + f.endLine)) newSet.add(i);
  });
  return newSet;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    codeFoldRanges,
    codeFoldVisible,
    codeFoldViewToModel,
    codeFoldModelToView,
    codeFoldMapEdit,
    codeFoldGutterLines,
    codeFoldModelGutterLines,
    codeFoldGutterHTML,
    codeFoldMerge,
    codeFoldPlaceholderText,
  });
}
