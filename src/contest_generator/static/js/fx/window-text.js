// fx/window-text.js — textarea 视口化的窗口文本纯函数（工单 editor-textarea-viewport/01）
//
// 视口化：textarea 从「全量全高」（6000 行文本 + 12.6 万 px 巨盒，打开 ~195ms
// 渲染大头）改为「视口高 + 窗口文本」（只装当前窗口 ~56 行）。本模块是这套
// 映射的「脑子」：
//   - windowTextBuild：视图行数组 + 窗口行区间 → 窗口文本 + 窗口内行起点表 +
//     窗口起点绝对偏移（absStart）；
//   - windowEditToView：窗口文本的编辑段（editChangeSpan 口径）→ 视图文本的
//     绝对变更段；越界/窗口与行起点表不同步 → **null**（调用方走「以模型
//     重建」兜底，不静默错位——spec：宁可重装，不可错位）；
//   - windowEditToModel：窗口编辑 → 模型全文（含折叠态：经 codeFoldMapEdit
//     承接「触碰占位 → 展开/整块覆盖」既有语义；非折叠直接绝对段替换）；
//   - windowTextMatches / windowTextMatchesModel：一致性校验（视图层 / 模型
//     推导层——折叠态模型 ≠ 视图，viewModel 即「由模型推导的视图」）。
// 模块约定见 fx/core.js 头部。行号：窗口行区间 [start, end) 0 基（与窗口化
// 渲染 codeWindowRange 同口径）；行内偏移 0 基；行起点数组 = 全量绝对偏移
// （复用 fx/codeeditor.js 单源 buildLineStarts）。
import { buildLineStarts, caretLineFromStarts } from "./codeeditor.js";
import { editChangeSpan } from "./edit-patch.js";
import { codeFoldMapEdit } from "./code-fold.js";

// windowTextBuild(viewLines, start, end, viewLineStarts?)：窗口文本构建——
// 视图行数组 [start, end) 切片 join("\n")（与窗口化渲染的窗口文本同口径：无
// 尾随换行、行间单换行）。返回 { start, end, text, winLineStarts, absStart }：
//   text          窗口文本
//   winLineStarts 窗口内行起点 0 基偏移（**相对窗口文本**——命名上避与
//                 buildLineStarts/caretLineFromStarts 的全量绝对语义混淆）
//   absStart      窗口首行的全量绝对偏移（viewLineStarts 缺省 = 0）
// start/end 钳制到 [0, viewLines.length]（越界 = 空窗口，不静默错位——调用方
// 拿 absStart 与后续映射对拍）。
export function windowTextBuild(viewLines, start, end, viewLineStarts) {
  const lines = viewLines || [];
  const len = lines.length;
  const s = Math.max(0, Math.min(len, start | 0));
  const e = Math.max(s, Math.min(len, end | 0));
  const slice = lines.slice(s, e);
  return {
    start: s,
    end: e,
    text: slice.join("\n"),
    winLineStarts: buildLineStarts(slice),
    absStart: (viewLineStarts || [])[s] || 0,
  };
}

// windowEditToView(span, winInfo, viewLineStarts)：窗口编辑段 → 视图绝对变更段
// ——span = editChangeSpan(winInfo.text, 新窗口文本) 的结果；winInfo =
// windowTextBuild 输出（含 start/winLineStarts/absStart）；viewLineStarts =
// 视图全量行起点数组。返回 {p, oldSegLen, newSegLen}（p = 视图文本绝对偏移；
// 跨行编辑段 old/new 长度不变——窗口文本就是视图文本该区间的逐字符切片）。
// 失败（窗口为空但 start 越界、行起点表与窗口不同步）→ **null**（调用方重建，
// 不静默归零——评审整改：`|| 0` 会区分不了「行 0 起点」与「越界」）。
export function windowEditToView(span, winInfo, viewLineStarts) {
  const ws = winInfo && winInfo.winLineStarts ? winInfo.winLineStarts : [];
  const startAbs = (viewLineStarts || [])[winInfo ? winInfo.start : 0];
  if (startAbs === undefined) return null;   // 窗口与行起点表不同步 / start 越界
  if (!ws.length) {
    // 空窗口：窗口文本长度为 0，编辑段 p 必为 0 → 映射到窗口起点（评审整改：
    // 此前恒返回 0 会把插入写进文档首）
    return { p: winInfo.absStart + Math.max(0, span.p | 0), oldSegLen: span.oldSegLen, newSegLen: span.newSegLen };
  }
  const p = Math.max(0, span.p | 0);
  // 窗口内行：最后一个 winLineStarts[i] <= p（p 恰在换行符上 = 前一行行尾）
  const winLine = Math.max(0, caretLineFromStarts(ws, p) - 1);
  const winStart = ws[winLine] === undefined ? null : ws[winLine];
  if (winStart === null) return null;
  const abs = (viewLineStarts || [])[winInfo.start + winLine];
  if (abs === undefined) return null;
  if (ws[winLine] > p) return null;   // 防御：行起点表与 p 矛盾
  return {
    p: abs + (p - winStart),
    oldSegLen: span.oldSegLen,
    newSegLen: span.newSegLen,
  };
}

// windowEditToModel(model, segs, oldViewText, winInfo, viewLineStarts, newWinText)
// ：窗口编辑 → 模型全文（视口化输入回写核心）。segs 非空（折叠态）→ 构造新
// 视图文本交给 codeFoldMapEdit（触碰占位 → 展开/整块覆盖语义原样承接，
// 占位文案不会原样写进模型）；segs 空（非折叠，视图=模型）→ 绝对段直替换。
// 返回 {model, expand, caret}；映射失败 → null（调用方以模型重建窗口）。
export function windowEditToModel(model, segs, oldViewText, winInfo, viewLineStarts, newWinText) {
  const span = editChangeSpan(winInfo.text, newWinText);
  const v = windowEditToView(span, winInfo, viewLineStarts);
  if (v == null) return null;
  const mid = String(newWinText == null ? "" : newWinText).slice(span.p, span.p + span.newSegLen);
  const oldView = String(oldViewText == null ? "" : oldViewText);
  const newView = oldView.slice(0, v.p) + mid + oldView.slice(v.p + v.oldSegLen);
  if (segs && segs.length) {
    const r = codeFoldMapEdit(String(model == null ? "" : model), segs, oldView, newView);
    return { model: r.model, expand: r.expand, caret: r.caret };
  }
  return { model: newView, expand: [], caret: v.p + mid.length };
}

// windowPosFromView(winInfo, viewPos)：视图绝对偏移 → 窗口内偏移（光标/选区
// 窗口内定位）。winInfo = windowTextBuild 输出。窗口文本就是视图文本在
// [absStart, absStart+text.length) 的逐字符切片，故窗口偏移 = viewPos - absStart。
// 越界（viewPos 不在窗口区间内）→ **null**——调用方先切换窗口再定位，不静默
// 钳制错位（与 windowEditToView 同纪律）。
export function windowPosFromView(winInfo, viewPos) {
  if (!winInfo || winInfo.absStart == null || winInfo.text == null) return null;
  const rel = (viewPos | 0) - winInfo.absStart;
  if (rel < 0 || rel > winInfo.text.length) return null;
  return rel;
}

// windowPosToView(winInfo, winPos)：窗口内偏移 → 视图绝对偏移（windowPosFromView
// 的逆映射；winPos 钳制 ≥0——输入越界向上不钳制，由调用方保证窗口包含区间，
// 与 FromView 越界返回 null 的「不静默错位」语义互补）。winInfo 非法 → null。
export function windowPosToView(winInfo, winPos) {
  if (!winInfo || winInfo.absStart == null) return null;
  return winInfo.absStart + Math.max(0, winPos | 0);
}

// windowTextMatches(viewLines, start, end, text)：一致性校验（视图层）——
// 由视图行数组重建窗口文本，与实际比对（失配 = textarea 内容被外部改动/
// 粘贴异常等，调用方以模型为准重建窗口文本）。
export function windowTextMatches(viewLines, start, end, text) {
  return windowTextBuild(viewLines, start, end).text === String(text == null ? "" : text);
}

// windowTextMatchesModel(model, viewModel, start, end, text)：一致性校验
// （模型推导层，工单 01 验收口径）——viewModel 非空 = 折叠态，视图行 = 模型
// 经 codeFoldVisible 推导的 viewModel.text 切片；非折叠 = model 直接切。
export function windowTextMatchesModel(model, viewModel, start, end, text) {
  const viewLines = viewModel && viewModel.text != null
    ? String(viewModel.text).split("\n")
    : String(model == null ? "" : model).split("\n");
  return windowTextMatches(viewLines, start, end, text);
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    windowTextBuild,
    windowEditToView,
    windowEditToModel,
    windowPosFromView,
    windowPosToView,
    windowTextMatches,
    windowTextMatchesModel,
  });
}
