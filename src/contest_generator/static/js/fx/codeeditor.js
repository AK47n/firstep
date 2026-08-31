// fx/codeeditor.js — 代码编辑器纯函数（工单 code-viewer-editor/02）
//
// 多文件标签条 / 可编辑三明治（textarea + 高亮层，无换行 + 容器滚动——
// 逐行 span 保留跳行/当前行语义，兑付「工单 code-viewer-editor/02」）/ 光标
// 行号 / Tab 缩进 / Enter 自动缩进。高亮与语言判定走 fx/highlight.js 单源
// （languageOf / highlightText——经 fx/codeview.js highlightCodeLines 复用，
// 逐行闭合并带 tok class）；esc 单源取自 fx/core.js；本地只做编辑纯件。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { highlightCodeLines } from "./codeview.js";
import { maincLineOffsetRange } from "./code.js";

// 多文件标签上限（工单 code-viewer-editor/02）：超出 toast 中文提示——
// 防病态大目录 / 大文件把内存与渲染压垮（每个 ≤1MB，10 个封顶）。
export const EDITOR_TABS_MAX = 10;

// editorLineRange(text, line)：跳行选段纯函数——**委托 fx/code.js
// maincLineOffsetRange 单源**（spec 决策：不复制实现，改名叫法避免 main.c
// 语义耦合；越界/非法行 → null）。
export const editorLineRange = maincLineOffsetRange;

// codeTabBadge(lang)：语言徽标（C / XML / MD / 其余 TXT——lang 来自
// fx/highlight.js languageOf 单源；与只读查看器旧 codeFileTabHTML 同观感）。
export function codeTabBadge(lang) {
  return lang === "c" ? "C" : lang === "xml" ? "XML" : lang === "md" ? "MD" : "TXT";
}

// codeTabStripHTML(tabs, activePath)：多文件标签条纯件——
// tabs = [{path, lang, dirty, readonly}]；活动 tab .on（data-tab-path 交
// 事件层）；脏点 .code-tab-dirty（aria-label 未保存）；只读 .ro + 可见
// 「只读」小标 .code-tab-ro + title；关闭钮 data-tab-close（事件层
// stopPropagation——点 × 不切 tab）。返回字符串；空 tabs → 空串（空态由
// 调用区放置）。
export function codeTabStripHTML(tabs, activePath) {
  return (tabs || []).map((t) => {
    const path = String(t.path == null ? "" : t.path);
    const name = path.split("/").pop() || path;
    const active = path === activePath;
    const ro = t.readonly ? " ro" : "";
    return '<button type="button" class="code-tab' + (active ? " on" : "") + ro
      + '" data-tab-path="' + esc(path) + '" role="tab"'
      + ' aria-selected="' + (active ? "true" : "false") + '"'
      + ' title="' + esc(path) + (t.readonly ? "（只读：非 UTF-8，禁止保存）" : "") + '">'
      + '<span class="code-tab-badge">' + codeTabBadge(t.lang) + "</span>"
      + '<span class="code-tab-name">' + esc(name) + "</span>"
      + (t.readonly ? '<span class="code-tab-ro">只读</span>' : "")
      + (t.dirty
        ? '<span class="code-tab-dirty" aria-label="未保存" title="未保存">●</span>'
        : "")
      + '<span class="code-tab-close" data-tab-close role="button"'
      + ' aria-label="关闭 ' + esc(name) + '" title="关闭">×</span>'
      + "</button>";
  }).join("");
}

// codeEditorHighlight(content, lang)：高亮层内部 HTML 单源（逐行 span，
// data-code-line 与只读视图同键）——codeEditorHTML 与 ui 胶水 input 重绘
// 共用（胶水只换 hl.innerHTML，不重建 textarea——焦点/选区/滚动零抖动）。
export function codeEditorHighlight(content, lang) {
  const src = String(content == null ? "" : content);
  return highlightCodeLines(src, lang)
    .map((h, idx) =>
      `<span class="code-hl-line" data-code-line="${idx + 1}">${h}</span>`)
    .join("");
}

// codeEditorHTML(content, lang, opts)：可编辑三明治纯件——
// pre.code-hl（静态流内：`.code-edit` width:max-content 以它量宽、高度以它
// 定量——容器 .code-view 负责滚动，无内部滚动条、零滚动同步）+ textarea
// .code-ta（absolute inset:0 覆盖同盒：透明文字 + accent 光标，white-space:
// pre 无换行，readonly 由 opts.readonly 决定——非 UTF-8 / 只读文件禁改）。
// 三者同一 font / line-height / padding / tab-size，逐行 1:1 对齐；高亮走
// highlightCodeLines 单源（超 128KB 或 plain 自动回退纯文本）；内容转义
// （esc——textarea 内 </textarea> 等全部 &lt; 化）。
export function codeEditorHTML(content, lang, opts = {}) {
  const src = String(content == null ? "" : content);
  const ro = opts.readonly ? " ro" : "";
  const roAttr = opts.readonly ? " readonly" : "";
  return '<div class="code-edit' + ro + '">'
    + '<pre class="code-hl" aria-hidden="true">' + codeEditorHighlight(src, lang) + "</pre>"
    + '<textarea class="code-ta" spellcheck="false" wrap="off"'
    + ' aria-label="代码编辑器"' + roAttr + ">" + esc(src) + "</textarea>"
    + "</div>";
}

// caretLineOf(value, pos)：光标行号（1 基）——数 value 前 pos 个字符里换行
// 数 +1；pos 越界钳到末行；空串 → 1。textarea.selectionStart 语义：pos 落
// 在换行符上 = 前一行行尾（slice 不含该 \n），与浏览器光标视觉一致。
export function caretLineOf(value, pos) {
  const v = String(value == null ? "" : value);
  const p = Math.max(0, Math.min(v.length, pos | 0));
  let count = 0;
  for (let i = 0; i < p; i++) if (v.charCodeAt(i) === 10) count++;
  return Math.max(1, count + 1);
}

// _lineStart(value, pos)：pos 所在行行首偏移（lastIndexOf("\n", pos-1)+1）。
function _lineStart(value, pos) {
  return value.lastIndexOf("\n", pos - 1) + 1;
}

// indentOnEnter(value, selStart, selEnd)：Enter 自动缩进——
// 替换选区为「\n + 起始行前导空白」（无选区 = 插入同一串）；单行与多行
// 选区同语义（VSCode 行为：Enter 吃选区）。返回 {value, start, end}——
// start/end = 新光标位（选区被折叠为空）。
export function indentOnEnter(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  const end = Math.max(start, Math.min(v.length, selEnd | 0));
  const lineStart = _lineStart(v, start);
  const lineEnd = v.indexOf("\n", lineStart);
  const lineText = v.slice(lineStart, lineEnd === -1 ? v.length : lineEnd);
  const ws = /^[ \t]*/.exec(lineText)[0];
  const insert = "\n" + ws;
  const text = v.slice(0, start) + insert + v.slice(end);
  const pos = start + insert.length;
  return { value: text, start: pos, end: pos };
}

// indentLines(value, selStart, selEnd)：Tab 缩进（4 空格）——
// 多行选区（起始行 ≠ 尾行）→ 选区触及的每行前置 4 空格、选区扩展为整段；
// 单行（含零长选区）→ 4 空格替换选区/插入光标。返回 {value, start, end}。
export function indentLines(value, selStart, selEnd) {
  const v = String(value == null ? "" : value);
  const start = Math.max(0, Math.min(v.length, selStart | 0));
  const end = Math.max(start, Math.min(v.length, selEnd | 0));
  const startLine = _lineStart(v, start);
  const endLine = _lineStart(v, Math.max(end - 1, start));
  if (startLine !== endLine) {
    // 多行：缩进整段（尾行含行尾——不含结尾 \n，保留原样）
    const segEnd = (() => {
      const nl = v.indexOf("\n", endLine);
      return nl === -1 ? v.length : nl;
    })();
    const segment = v.slice(startLine, segEnd);
    const indented = segment.split("\n").map((l) => "    " + l).join("\n");
    const text = v.slice(0, startLine) + indented + v.slice(segEnd);
    return { value: text, start: startLine, end: startLine + indented.length };
  }
  const text = v.slice(0, start) + "    " + v.slice(end);
  const pos = start + 4;
  return { value: text, start: pos, end: pos };
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    codeTabBadge,
    codeTabStripHTML,
    codeEditorHighlight,
    codeEditorHTML,
    editorLineRange,
    caretLineOf,
    indentOnEnter,
    indentLines,
    EDITOR_TABS_MAX,
  });
}
