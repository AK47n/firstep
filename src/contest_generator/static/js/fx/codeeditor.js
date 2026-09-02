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
import { codeMarksHTML } from "./code-marks.js";

// 多文件标签上限（工单 code-viewer-editor/02）：超出 toast 中文提示——
// 防病态大目录 / 大文件把内存与渲染压垮（每个 ≤1MB，10 个封顶）。
export const EDITOR_TABS_MAX = 10;

// conflictHTML(diskText, editText)：保存冲突模态内容纯件（工单
// code-viewer-editor/04）——双列等宽 pre 并排：磁盘版（外部修改）vs 我的
// 编辑，各取前 _CONFLICT_REVIEW_LINES 行 + 越界省略提示；内容 esc（调用方
// 保证传入原文，本纯件转义）。动作按钮由胶水层（模态 shell）提供。
const CONFLICT_REVIEW_LINES = 10;

export function conflictHTML(diskText, editText) {
  const clip = (t) => {
    const lines = String(t == null ? "" : t).split("\n");
    const head = lines.slice(0, CONFLICT_REVIEW_LINES);
    const shown = head.join("\n");
    return esc(shown) + (lines.length > CONFLICT_REVIEW_LINES
      ? "\n…（共 " + lines.length + " 行，仅展示前 " + CONFLICT_REVIEW_LINES + " 行）"
      : "");
  };
  return '<div class="code-conflict">'
    + '<p class="muted">磁盘上的文件已被外部修改（任务 / 深化写盘或外部编辑器）。请对比后选择动作：</p>'
    + '<div class="code-conflict-cols">'
    + '<div class="code-conflict-col"><div class="code-conflict-col-title">磁盘版（外部修改）</div>'
    + '<pre class="code-conflict-pre">' + clip(diskText) + "</pre></div>"
    + '<div class="code-conflict-col"><div class="code-conflict-col-title">我的编辑（未保存）</div>'
    + '<pre class="code-conflict-pre">' + clip(editText) + "</pre></div>"
    + "</div></div>";
}

// isTabSavable(tab)：标签是否可保存——**单源判据**（ui 保存守卫与「保存」
// 按钮可见性共用，防两处漂移）：标签存在、非只读（非 UTF-8 禁存）、且
// 内容与磁盘快照有差异。
export function isTabSavable(tab) {
  return !!tab && !tab.readonly && tab.content !== tab.savedContent;
}

// dirtySavableTabs(tabs)：需要保存的标签清单（工单 code-tab-compile/02——
// saveAllDirtyTabs 的纯决策：脏且非只读；只读/非脏跳过，零请求）。
export function dirtySavableTabs(tabs) {
  return (tabs || []).filter(isTabSavable);
}

// editorLineRange(text, line)：跳行选段纯函数——**委托 fx/code.js
// maincLineOffsetRange 单源**（spec 决策：不复制实现，改名叫法避免 main.c
// 语义耦合；越界/非法行 → null）。
export const editorLineRange = maincLineOffsetRange;

// codeTabBadge(lang)：语言徽标（C / XML / MD / 其余 TXT——lang 来自
// fx/highlight.js languageOf 单源；与只读查看器旧 codeFileTabHTML 同观感）。
export function codeTabBadge(lang) {
  return lang === "c" ? "C" : lang === "xml" ? "XML" : lang === "md" ? "MD" : "TXT";
}

// codeStatusHTML(info)：状态栏信息区纯件（工单 code-editor-vscode-polish/01）
// —— VSCode 式右侧信息段：光标行列（Lnn, Colm）+ 语言徽标 + 编码（UTF-8 /
// 非 UTF-8（只读））+ 缩进（空格: N）+ 缩放百分比；info = {line, col, lang,
// utf8, indent, zoomPct}。lang 缺省/空 = 无活动文件 → 返回空串（调用方隐藏
// 整段）；文本一律 esc（语言徽标来自 codeTabBadge 固定映射，其余用户可见
// 数字经 esc 兜底——防未来字段接入原文）。
export function codeStatusHTML(info) {
  const i = info || {};
  const lang = String(i.lang == null ? "" : i.lang);
  if (!lang) return "";
  const line = Math.max(1, i.line | 0);
  const col = Math.max(1, i.col | 0);
  const indent = Math.max(0, i.indent | 0) || 4;
  const zoomPct = Math.max(0, i.zoomPct | 0) || 100;
  const seg = (id, text) =>
    '<span class="code-statusbar-seg" id="code-statusbar-' + id + '">'
    + esc(text) + "</span>";
  return '<span class="code-statusbar-pos">Ln ' + line + ", Col " + col + "</span>"
    + seg("lang", codeTabBadge(lang))
    + seg("enc", i.utf8 === false ? "非 UTF-8（只读）" : "UTF-8")
    + seg("indent", "空格: " + indent)
    + seg("zoom", zoomPct + "%");
}

// moveTab(tabs, fromPath, toPath, place)：标签拖拽排序纯件（工单
// code-editor-vscode-polish/03）——返回**新数组**（不改入参；fromPath 移到
// toPath 前/后，place = "before" | "after"；toPath 空/null = 追加到末尾；
// toPath === fromPath → 原样返回；fromPath 不存在 → 原样返回；toPath 不存
// 在（拖动中目标已重排）→ 还原原位）。重排路径返回新引用、无操作路径返回
// 原引用——无副作用语义靠「不改入参」保证，调用方不依赖引用身份。只重排
// tab 对象引用，内容 / 脏点 / 活动态一律不动（排序纯展示态，激活与保存
// 语义延续）。
export function moveTab(tabs, fromPath, toPath, place) {
  const src = tabs || [];
  const from = src.findIndex((t) => t.path === fromPath);
  if (from < 0) return src;
  if (toPath === fromPath) return src;
  const arr = src.slice();
  const [item] = arr.splice(from, 1);
  let insertAt = arr.length;
  if (toPath != null && toPath !== "") {
    const to = arr.findIndex((t) => t.path === toPath);
    if (to < 0) { arr.splice(from, 0, item); return arr; }
    insertAt = place === "after" ? to + 1 : to;
  }
  arr.splice(insertAt, 0, item);
  return arr;
}

// codeTabStripHTML(tabs, activePath)：多文件标签条纯件——
// tabs = [{path, lang, dirty, readonly, diskChanged?}]；活动 tab .on
// （data-tab-path 交事件层）；脏点 .code-tab-dirty（aria-label 未保存）；
// 只读 .ro + 可见「只读」小标 .code-tab-ro + title；diskChanged（code-ide-
// flow/02：磁盘被外部/AI 改写但标签有未保存编辑）→「磁盘已变更」徽章
// .code-tab-disk（data-tab-disk 交事件层弹三选，不触发切 tab）；关闭钮
// data-tab-close（事件层 stopPropagation——点 × 不切 tab）。返回字符串；
// 空 tabs → 空串（空态由调用区放置）。
export function codeTabStripHTML(tabs, activePath) {
  return (tabs || []).map((t) => {
    const path = String(t.path == null ? "" : t.path);
    const name = path.split("/").pop() || path;
    const active = path === activePath;
    const ro = t.readonly ? " ro" : "";
    return '<button type="button" class="code-tab' + (active ? " on" : "") + ro
      + '" data-tab-path="' + esc(path) + '" role="tab" draggable="true"'
      + ' aria-selected="' + (active ? "true" : "false") + '"'
      + ' title="' + esc(path) + (t.readonly ? "（只读：非 UTF-8，禁止保存）" : "") + '">'
      + '<span class="code-tab-badge">' + codeTabBadge(t.lang) + "</span>"
      + '<span class="code-tab-name">' + esc(name) + "</span>"
      + (t.readonly ? '<span class="code-tab-ro">只读</span>' : "")
      + (t.diskChanged
        ? '<span class="code-tab-disk" data-tab-disk role="button"'
          + ' aria-label="磁盘已变更：点击选择保留我的编辑或加载磁盘版"'
          + ' title="磁盘已变更：点击查看">!</span>'
        : "")
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
// 定量——容器 .code-view 负责滚动，无内部滚动条、零滚动同步）+ pre.code-marks
// （仅背景标记层，工单 code-editor-vscode-polish/04-06：查找命中/选中词/括号
// 配对共用；absolute inset:0 同盒、文字透明、pointer-events:none——opts.marks
// = [{line,start,end,kind}]，内容经 fx/code-marks.js codeMarksHTML 转义）+
// textarea .code-ta（absolute inset:0 覆盖同盒：透明文字 + accent 光标，
// white-space: pre 无换行，readonly 由 opts.readonly 决定——非 UTF-8 / 只读
// 文件禁改）。三者同一 font / line-height / padding / tab-size，逐行 1:1
// 对齐；高亮走 highlightCodeLines 单源（超 128KB 或 plain 自动回退纯文本）；
// 内容转义（esc——textarea 内 </textarea> 等全部 &lt; 化）。
export function codeEditorHTML(content, lang, opts = {}) {
  const src = String(content == null ? "" : content);
  const ro = opts.readonly ? " ro" : "";
  const roAttr = opts.readonly ? " readonly" : "";
  return '<div class="code-edit' + ro + '">'
    + '<pre class="code-hl" aria-hidden="true">' + codeEditorHighlight(src, lang) + "</pre>"
    + '<pre class="code-marks" aria-hidden="true">'
    + codeMarksHTML(src, opts.marks) + "</pre>"
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

// caretColOf(value, pos)：光标列号（1 基）——pos 所在行行首偏移
// （lastIndexOf("\n", pos-1)+1）到 pos 的字符数 +1，并按行尾长度钳制
// （pos 恰在换行符上 = 行尾列，与浏览器光标视觉一致）；pos 越界钳到行尾列；
// 空串 → 1。与 caretLineOf 同族成对（评审整改 code-editor-vscode-polish/01：
// 行列计算同一 fx 单源——ui 层不再手写 lastIndexOf/indexOf 算式）。
export function caretColOf(value, pos) {
  const v = String(value == null ? "" : value);
  const p = Math.max(0, Math.min(v.length, pos | 0));
  const lineStart = v.lastIndexOf("\n", p - 1) + 1;
  const lineEnd = (() => {
    const nl = v.indexOf("\n", lineStart);
    return nl === -1 ? v.length : nl;
  })();
  return Math.min(p - lineStart + 1, lineEnd - lineStart + 1);
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

// replaceAllText(src, needle, replacement)：当前文件「全部替换」纯件（工单
// code-editor-utilize/03）——split/join 字面语义（替换串 $& / $1 等不解释为
// 模式组，规避 String.replace 陷阱），无匹配/空针 → count 0 且原样返回。
// 返回 {count, value}；src 非字符串防御为 ""。
export function replaceAllText(src, needle, replacement) {
  const v = String(src == null ? "" : src);
  const n = String(needle == null ? "" : needle);
  if (!n) return { count: 0, value: v };
  const count = v.split(n).length - 1;
  return count
    ? { count, value: v.split(n).join(String(replacement == null ? "" : replacement)) }
    : { count: 0, value: v };
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    codeTabBadge,
    codeStatusHTML,
    codeTabStripHTML,
    moveTab,
    codeEditorHighlight,
    codeEditorHTML,
    conflictHTML,
    editorLineRange,
    isTabSavable,
    dirtySavableTabs,
    caretLineOf,
    caretColOf,
    indentOnEnter,
    indentLines,
    replaceAllText,
    EDITOR_TABS_MAX,
  });
}
