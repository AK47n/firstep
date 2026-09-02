// ui/codeeditor.js — 代码编辑器 DOM 胶水（工单 code-viewer-editor/02）
//
// 「代码」tab 中栏全部交互：多文件标签条（打开/切换/关闭/脏点/上限 10）+
// 可编辑三明治（textarea + 高亮层，无换行 + 容器滚动——逐行 span 保留跳行/
// 当前行语义）+ Tab 缩进 / Enter 自动缩进 + 光标行高亮 + 跳行（大纲/搜索/
// 文件内查找共用 setSelectionRange 路径）+ .md 两态（预览 / 编辑）与关闭脏
// tab 确认（confirmModal 单源）。文件内容 memo（dir+path）与目录上下文
// setCodeDir 由本模块持有；保存（t03）与冲突（t04）在同一状态之上扩展。
// 纯件在 fx/codeeditor.js；ui/codeview.js 只保留树 / 侧栏 / 工具栏，经
// 本模块导出面联动（openEditorFile / getActiveTab / editJumpToLine /
// setMdMode / onActiveTabChanged）。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { languageOf } from "/js/fx/highlight.js";
import { codeLineNumbersHTML } from "/js/fx/codeview.js";
import { codeFindRanges, codeMarksHTML, codeWordAt, codeWordRanges, codeIndentGuideMarks } from "/js/fx/code-marks.js";  // 标记层纯件（工单 code-editor-vscode-polish/04-06：查找/选中词/括号共用；07 缩进引导线）
import {
  BRACKET_OPEN,
  BRACKET_CLOSE,
  bracketOpen,
  bracketClose,
  bracketBackspace,
  bracketPairAt,
} from "/js/fx/code-brackets.js";  // 括号配对与自动闭合纯件（工单 code-editor-vscode-polish/06）
import {
  codeTabStripHTML,
  codeEditorHTML,
  codeEditorHighlight,
  conflictHTML,
  editorLineRange,
  isTabSavable,
  dirtySavableTabs,
  caretLineOf,
  caretColOf,
  indentOnEnter,
  indentLines,
  replaceAllText,
  replaceOneAt,
  EDITOR_TABS_MAX,
} from "/js/fx/codeeditor.js";
import { parseMarkdownBlocks, markdownPreviewHTML, markdownOutline, hasScheme } from "/js/fx/markdown.js";
import {
  shiftTab,
  deleteLine,
  moveLine,
  copyLine,
  lineRangeOf,
} from "/js/fx/code-lineops.js";  // 行操作纯件（工单 code-page-vscode-overhaul/01）
import {
  toggleLineComment,
  toggleBlockComment,
} from "/js/fx/code-comment.js";  // 注释切换纯件（工单 code-page-vscode-overhaul/02）
import { mtimeEq } from "/js/fx/disk-baseline.js";  // mtime 相等守卫单源（工单 07 评审整改：与基线 diff/快照守卫同口径）
import { treeRenamedPath, treeOpAffected } from "/js/fx/code-tree-ops.js";  // 重命名路径映射纯件（工单 code-tree-ops/02）
import {
  codeFoldRanges,
  codeFoldVisible,
  codeFoldViewToModel,
  codeFoldModelToView,
  codeFoldMapEdit,
  codeFoldGutterHTML,
  codeFoldMerge,
} from "/js/fx/code-fold.js";  // 代码折叠纯件（工单 code-editor-vscode-polish/07）
import { confirmModal } from "/js/ui/confirm.js";

// ---- 模块态：目录 / 标签 / 活动文件 / 内容 memo / 监听器 ----
let codeDir = "";
let tabs = [];           // {path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode, readonly}
let activePath = "";
const fileCache = new Map();  // key = fileCacheKey(path) → {ok:true, data} | {ok:false, message}

// ---- 折叠态（工单 code-editor-vscode-polish/07）----
// 模型 = tab.content 全量基线；有折叠时 textarea/高亮/行号/标记全部按
// 视图态渲染（viewModel = codeFoldVisible 输出：可见行 + 占位行 + 偏移映射
// segs），编辑经 codeFoldMapEdit 写回模型。无折叠（folds 空或全展开）时
// viewModel = null——走既有全量路径，零行为回归。
let folds = [];
let foldedSet = new Set();
let viewModel = null;

// fileCacheKey(path)：文件缓存键单源（dir + NUL 分隔可避免路径拼接歧义）——
// 读取 / 失效 / 保存后更新共用同一构造，防止键拼法漂移。
function fileCacheKey(path) {
  return codeDir + "\u0000" + path;
}
const activeListeners = new Set();

// 光标/选区变化监听（工单 code-editor-vscode-polish/01）：codeview 注册刷新
// 状态栏 Ln/Col——与 onActiveTabChanged 同模式（监听器异常不阻断）；光标
// 移动只刷状态栏，不重渲编辑器。
const cursorListeners = new Set();

export function onCursorChanged(cb) { cursorListeners.add(cb); }

function notifyCursor() {
  refreshMarkSetters();   // 选中词 + 括号配对标记随光标变化重算（工单 05/06；未变零渲染）
  cursorListeners.forEach((cb) => { try { cb(); } catch (e) { /* 监听器异常不阻断 */ } });
}

// scheduleCursorWork()：光标联动「只做必做、其余顺延一帧」调度（性能整改）——
// 点击/按键的同一事件回调里，setActiveLine 立即上类；选中词全文扫描 /
// 括号配对扫描 / 标记层重绘 / 状态栏更新这些**同步重活**会阻塞浏览器绘制
// （实测点击后高亮被拖到 ~100ms 才上屏——用户反馈「延时感」根因）。改为
// requestAnimationFrame 合并调度：高亮先画、重活下一帧做；连续事件只排一次
// （raf id 去重）。
let cursorRafId = 0;
function scheduleCursorWork() {
  if (cursorRafId) return;
  cursorRafId = requestAnimationFrame(() => {
    cursorRafId = 0;
    notifyCursor();
  });
}

const CODE_FLASH_MS = 1200;  // 跳行闪烁（与查看器同值：评审整改 1200 归拢）

// ===== 目录上下文 =====
export function getCodeDir() { return codeDir; }

// setCodeDir(dir)：目录切换（codeview.loadCodeDir 调用）——清标签/缓存/
// 活动态（目录变了旧文件无意义，防跨目录悬空引用）。
export function setCodeDir(dir) {
  codeDir = dir;
  tabs = [];
  activePath = "";
  fileCache.clear();
  resetFoldState();
  renderTabs();
  renderPane();
  notifyActive();
}

// ===== 标签访问 =====
export function getActiveTab() {
  return tabs.find((t) => t.path === activePath) || null;
}

// onActiveTabChanged(cb)：活动标签变化监听（codeview 注册：大纲/查找面板
// 随活动文件联动）。
export function onActiveTabChanged(cb) { activeListeners.add(cb); }

// onFileSaved(cb)：保存成功监听（codeview 注册：树节点大小刷新；main.c
// 步骤 8 状态行刷新 = 工单 05）。
const savedListeners = new Set();
export function onFileSaved(cb) { savedListeners.add(cb); }

// onFileLoaded(cb)：文件读盘成功打开监听（工单 code-ide-ai/07：codeview
// 在基线建立内容快照——「打开过的文件」才有行级 diff 数据源；仅 openEditorFile
// 新建标签的读盘路径触发——激活既有标签不走读盘，快照维持不变）。
const loadedListeners = new Set();
export function onFileLoaded(cb) { loadedListeners.add(cb); }

function notifyActive() {
  const tab = getActiveTab();
  activeListeners.forEach((cb) => { try { cb(tab); } catch (e) { /* 监听器异常不阻断 */ } });
}

function notifySaved(tab, resp) {
  savedListeners.forEach((cb) => { try { cb(tab, resp); } catch (e) { /* 同上 */ } });
}

function notifyLoaded(path, content, mtimeNs) {
  loadedListeners.forEach((cb) => { try { cb(path, content, mtimeNs); } catch (e) { /* 同上 */ } });
}

function tabOf(path) { return tabs.find((t) => t.path === path) || null; }

function tabShape(t) {
  return {
    path: t.path,
    lang: t.lang,
    dirty: t.content !== t.savedContent,
    readonly: t.readonly,
    diskChanged: !!t.diskChanged,
  };
}

// ===== 文件内容 memo（业务 400 缓存，网络 / ≥500 不缓存可重试——对偶
// 查看器 loadCodeFileState 先例） =====
function fileURL(path) {
  return "/api/code/file?dir=" + encodeURIComponent(codeDir)
    + "&path=" + encodeURIComponent(path);
}

async function loadFileState(path) {
  const key = fileCacheKey(path);
  if (fileCache.has(key)) return fileCache.get(key);
  try {
    const data = await apiGet(fileURL(path));
    const cached = { ok: true, data };
    fileCache.set(key, cached);
    return cached;
  } catch (e) {
    const cached = { ok: false, message: e.message };
    if (e.status && e.status < 500) fileCache.set(key, cached);
    return cached;
  }
}

// ===== 标记层：文件内查找高亮（工单 code-editor-vscode-polish/04）=====
// 状态挂编辑器（活动标签内容为数据源；codeview 只持查询输入与计数文案）：
// 查询 → codeFindRanges 纯件算命中区段，索引循环（Enter/Shift+Enter）→
// current 高亮 + 跳转选区。05 选中词 / 06 括号配对经 currentMarks() 追加
// 各自区段（kind 不同），一次渲染多类标记。
let editorFind = { query: "", ranges: [], index: 0 };

// currentMarks()：当前应渲染的标记清单（缩进引导线 + 查找命中 + 当前命中 +
// 选中词 + 括号配对；07 引导线按模型文本逐行计算，折叠视图经 marksForView
// 映射——占位行被折叠的引导线自动丢弃）。
export function currentMarks() {
  const out = [];
  const tab = getActiveTab();
  if (tab) out.push(...codeIndentGuideMarks(tab.content));
  if (editorFind.query && editorFind.ranges.length) {
    editorFind.ranges.forEach((r, i) => {
      out.push({ line: r.line, start: r.start, end: r.end,
        kind: i === editorFind.index ? "current" : "hit" });
    });
  }
  if (editorWord.word && editorWord.ranges.length) {
    editorWord.ranges.forEach((r) => {
      out.push({ line: r.line, start: r.start, end: r.end, kind: "word" });
    });
  }
  if (editorBracket) {
    out.push({ line: editorBracket.open.line, start: editorBracket.open.start,
      end: editorBracket.open.end, kind: "bracket" });
    out.push({ line: editorBracket.close.line, start: editorBracket.close.start,
      end: editorBracket.close.end, kind: "bracket" });
  }
  return out;
}

// ---- 括号配对高亮（工单 code-editor-vscode-polish/06）----
// 光标在括号上/紧邻 → 配对括号两段标记（kind: "bracket"，下划线类样式）；
// 仅 .c/.h 与 xml 启用（spec：.md 编辑源码态只自动闭合不配对高亮）。
let editorBracket = null;

// updateBracketMarks()：光标/内容变化后重算配对高亮——配对位置变了返回 true
// （不渲染，同 updateWordMarks 纪律）；仅 .c/.h 与 xml 启用（spec：.md 编辑
// 源码态只自动闭合不配对高亮）。
function updateBracketMarks() {
  const tab = getActiveTab();
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!tab || !ta || tab.readonly || (tab.lang !== "c" && tab.lang !== "xml")) {
    // 只读标签不启用任何（评审整改 06c）；仅 .c/.h 与 xml 启用配对高亮
    if (editorBracket) {
      editorBracket = null;
      return true;
    }
    return false;
  }
  const pos = foldCaretModelPos();   // 折叠态：选区（视图）→ 模型偏移（工单 07）
  const pair = bracketPairAt(tab.content, pos);
  const changed = JSON.stringify(pair) !== JSON.stringify(editorBracket);
  if (changed) editorBracket = pair;
  return changed;
}

// refreshMarkSetters()：选中词 + 配对高亮状态重算，变了才渲染标记层一次
// （notifyCursor / renderPane 各出口统一调用；渲染单点 = renderEditorMarks）。
function refreshMarkSetters() {
  const wc = updateWordMarks();
  const bc = updateBracketMarks();
  if (wc || bc) renderEditorMarks();
}

// ===== 折叠视图助手（工单 code-editor-vscode-polish/07）=====
// marksForView()：把模型行号的标记清单映射到视图行（占位行丢弃——被折叠的
// 命中/词/括号不显示；行内偏移不变）。
function marksForView() {
  const map = new Map();
  viewModel.lines.forEach((l, i) => { if (!l.placeholder) map.set(l.no, i + 1); });
  return currentMarks()
    .filter((m) => map.has(m.line))
    .map((m) => ({ line: map.get(m.line), start: m.start, end: m.end, kind: m.kind }));
}

// foldCaretModelPos()：当前光标 → 模型偏移（无折叠时 = 选区偏移）。
function foldCaretModelPos() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return 0;
  const viewPos = Math.max(0, ta.selectionStart | 0);
  return viewModel ? codeFoldViewToModel(viewModel.segs, viewPos) : viewPos;
}

// editorCaretModelPos()：状态栏 Ln/Col 数据源（模型行/列——折叠态下视图行号
// 与模型行号不同；导出供 codeview 状态栏刷新）。
export function editorCaretModelPos() {
  const tab = getActiveTab();
  if (!tab) return { line: 1, col: 1 };
  const modelPos = foldCaretModelPos();
  return { line: caretLineOf(tab.content, modelPos), col: caretColOf(tab.content, modelPos) };
}

// viewLineIndexOf(modelLine)：模型行号 → 视图行号（1 基）；不可见（占位/
// 越界）→ 0。
function viewLineIndexOf(modelLine) {
  if (!viewModel) return modelLine;
  const idx = viewModel.lines.findIndex((l) => !l.placeholder && l.no === modelLine);
  return idx < 0 ? 0 : idx + 1;
}

// refreshFoldView()：折叠态变更后重建视图模型并重渲染（保留光标：模型偏移
// → 新视图偏移）；全部展开 → viewModel = null 回全量路径。
function refreshFoldView() {
  const tab = getActiveTab();
  if (!tab) return;
  const box = paneBox();
  const oldTa = box && box.querySelector(".code-ta");
  const oldSegs = viewModel ? viewModel.segs : null;
  const caretModel = oldTa ? (oldSegs ? codeFoldViewToModel(oldSegs, oldTa.selectionStart) : oldTa.selectionStart) : 0;
  viewModel = (folds.length && foldedSet.size)
    ? codeFoldVisible(tab.content, folds, foldedSet)
    : null;
  renderPane();
  const ta = box && box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    const vo = viewModel ? codeFoldModelToView(viewModel.segs, caretModel) : caretModel;
    ta.focus();
    ta.setSelectionRange(vo, vo);
  }
}

// toggleFold(idx)：折叠/展开单个折叠区（gutter 箭头 / 占位行点击共用）。
function toggleFold(idx) {
  if (idx < 0 || idx >= folds.length) return;
  if (foldedSet.has(idx)) foldedSet.delete(idx); else foldedSet.add(idx);
  refreshFoldView();
}

// foldAtLine(modelLine)：包含模型行的折叠区（最内层 = 区间最短）；无 → null。
function foldAtLine(modelLine) {
  let best = null;
  folds.forEach((f, i) => {
    if (f.startLine <= modelLine && modelLine <= f.endLine) {
      if (!best || (f.endLine - f.startLine) < (best.f.endLine - best.f.startLine)) {
        best = { f, i };
      }
    }
  });
  return best ? best.i : null;
}

// resetFoldState()：切目录/切文件/关标签/磁盘重载后重算折叠态——折叠集清空
// （会话内不跨文件保持；spec：切目录/换文件重算或清空），folds 按当前活动
// 文件重算（快捷键/箭头需要折叠区清单；活动 tab 为空 → 空清单）。
function resetFoldState() {
  const tab = getActiveTab();
  folds = tab ? codeFoldRanges(tab.content, tab.lang) : [];
  foldedSet = new Set();
  viewModel = null;
}

// ---- 选中词高亮（工单 code-editor-vscode-polish/05）----
// 状态：光标处词 + 全文同词区段（大小写精确 + 词边界）；随光标变化重算
// （notifyCursor 前置钩子），内容变化也重算（词未变但偏移会变——签名比较）。
let editorWord = { word: "", ranges: [] };
let editorWordContent = null;   // 上次重算时的 tab.content 引用（性能整改：内容引用短路）

// updateWordMarks()：光标/内容变化后重算选中词标记——词变了或区段签名变了
// 返回 true（**不渲染**——渲染由调用方统一做，防 find/word/bracket 三态
// 各自渲染的错帧与双渲染，评审整改 05/06）；无 textarea（.md 预览/未开
// 文件）清空（重置也返回 true 供调用方渲染清除）。
function updateWordMarks() {
  const tab = getActiveTab();
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!tab || !ta) {
    if (editorWord.word || editorWord.ranges.length) {
      editorWord = { word: "", ranges: [] };
      editorWordContent = null;
      return true;
    }
    return false;
  }
  const content = tab.content;
  const pos = foldCaretModelPos();   // 折叠态：选区（视图）→ 模型偏移（工单 07）
  const word = codeWordAt(content, pos);
  // 性能整改（光标延时）：内容引用未变且词未变 → 同词区段必同（ranges 是
  // (content, word) 的纯函数；位置变了但词一样 = 仍在同一词内移动/词外空
  // 白，区段不变）——直接跳过 codeWordRanges 全文扫描，单词内移动零扫描。
  if (editorWordContent === content && word === editorWord.word) return false;
  const ranges = word ? codeWordRanges(content, word) : [];
  const changed = word !== editorWord.word
    || JSON.stringify(ranges) !== JSON.stringify(editorWord.ranges);
  if (changed) editorWord = { word, ranges };
  editorWordContent = content;
  return changed;
}

// renderEditorMarks()：标记层重算 + 重画单入口（评审整改 04：编辑内容后高亮
// 必须按新内容重算命中——不在输入路径留旧 ranges 错列）——query 非空时按
// 活动标签当前内容重算 codeFindRanges 并钳索引（编辑后命中数变化不越界），
// 空查询清空；.code-marks 不存在（md 预览/未开文件）静默。只重画 innerHTML
// （不重建 textarea，与 syncEditorAfterInput 同粒度）。
function renderEditorMarks() {
  const box = paneBox();
  const el = box && box.querySelector(".code-marks");
  const tab = getActiveTab();
  if (!el || !tab) return;
  if (editorFind.query) {
    editorFind.ranges = codeFindRanges(tab.content, editorFind.query);
    if (!editorFind.ranges.length) editorFind.index = -1;
    else if (editorFind.index < 0 || editorFind.index >= editorFind.ranges.length) {
      editorFind.index = 0;
    }
  } else {
    editorFind.ranges = [];
    editorFind.index = -1;
  }
  el.innerHTML = codeMarksHTML(
    viewModel ? viewModel.text : tab.content,
    viewModel ? marksForView() : currentMarks(),
  );
}

// setEditorFind(query)：查找输入变化 → 存查询、重算命中区段并渲染标记层——
// 返回 {total, current}（current = 当前索引 0 基；无命中 → {total:0, current:-1}）。
// 编辑器未打开时只存状态（渲染在 renderPane/sync 时落地）。
export function setEditorFind(query) {
  editorFind.query = String(query == null ? "" : query);
  editorFind.index = 0;
  renderEditorMarks();
  return { total: editorFind.ranges.length, current: editorFind.index };
}

// editorFindStep(delta)：循环上/下一命中——更新 current 索引、重渲染、滚动
// 到命中（editJumpToLine 滚动 + 选区覆盖为命中区间）。无命中 → null。
export function editorFindStep(delta) {
  const total = editorFind.ranges.length;
  if (!total) return null;
  editorFind.index = (editorFind.index + delta + total) % total;
  renderEditorMarks();
  focusFindRange(editorFind.ranges[editorFind.index]);
  return { total, current: editorFind.index };
}

// focusFindRange(range)：跳转到命中区段——先 editJumpToLine（滚动居中 +
// flash + 当前行），再把选区缩为命中区间（VSCode 当前命中选址观感）。
// 折叠态（工单 code-page-vscode-overhaul/03）：range 为模型行/列，选区按
// 视图偏移落位（模型 → 视图映射）。
function focusFindRange(range) {
  const tab = getActiveTab();
  if (!tab) return;
  editJumpToLine(range.line);
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  if (!ta || ta.readOnly) return;
  const lineStart = editorLineRange(tab.content, range.line);
  if (!lineStart) return;
  const pos = lineStart.start + range.start;
  const end = pos + (range.end - range.start);
  let vPos = pos;
  let vEnd = end;
  if (viewModel) {
    vPos = codeFoldModelToView(viewModel.segs, pos);
    vEnd = codeFoldModelToView(viewModel.segs, end);
  }
  ta.focus();
  ta.setSelectionRange(vPos, vEnd);
}

// ===== 渲染：标签条 / 中栏 =====
function renderTabs() {
  const box = $("code-tabs");
  if (!box) return;
  box.innerHTML = tabs.length
    ? codeTabStripHTML(tabs.map(tabShape), activePath)
    : '<span class="muted">打开文件后显示标签</span>';
}

function paneBox() { return $("code-viewer"); }

function renderPane() {
  const box = paneBox();
  if (!box) return;
  const tab = getActiveTab();
  if (!tab) {
    box.innerHTML = '<span class="code-empty">点左侧文件在编辑器中打开（可修改，Ctrl+S 保存）</span>';
    refreshMarkSetters();   // 无 textarea：清空选中词/括号标记（评审整改 05：磁盘重载/切目录/关标签统一路径）
    return;
  }
  if (tab.lang === "md" && tab.mdMode === "preview") {
    box.innerHTML = markdownPreviewHTML(parseMarkdownBlocks(tab.content), {
      imageUrl: mdImageUrl,
      foldPreview: true,   // 标题折叠（工单 07）：details/summary 分组，点标题收起
    });
    refreshMarkSetters();
    return;
  }
  // 编辑态（含 .md「编辑源码」态——工单 05；预览态已提前 return）：
  // 同一三明治渲染，md 与普通文件共用（评审整改：去双分支重复）。折叠态
  // （工单 07）：行号列用视图行（模型真实行号 + 折叠箭头/占位行），编辑器
  // 内容 = 视图文本，标记经 marksForView 映射到视图行。
  const src = viewModel ? viewModel.text : tab.content;
  const gutter = viewModel
    ? codeFoldGutterHTML(viewModel.lines)
    : codeLineNumbersHTML(tab.content.split("\n").length);
  box.innerHTML = '<div class="code-gutter" aria-hidden="true">' + gutter + "</div>"
    + codeEditorHTML(src, tab.lang, {
      readonly: tab.readonly,
      marks: viewModel ? marksForView() : currentMarks(),
    });
  if (tab.readonly) renderReadonlyNote(box);
  refreshMarkSetters();   // 选中词/括号标记统一兜底（activateTab/applySavedState/applyDiskState/closeTab/remap 全经本函数，评审整改 05/06）
}

function renderReadonlyNote(box) {
  if (box.querySelector(".code-ro-note")) return;
  const note = document.createElement("div");
  note.className = "code-ro-note";
  note.textContent = "只读：文件不是 UTF-8 编码（为免损坏请用外部编辑器保存）";
  box.prepend(note);
}

// ---- .md 预览图片寻址（移自 ui/codeview.js，工单 code-viewer-md-preview/02）----
function mdImageUrl(src) {
  if (hasScheme(src)) return /^https?:/i.test(src) ? src : null;
  if (src.startsWith("/")) return null;
  const tab = getActiveTab();
  const base = tab && tab.path.includes("/")
    ? tab.path.slice(0, tab.path.lastIndexOf("/"))
    : "";
  const norm = normalizeRelPath((base ? base + "/" : "") + src);
  if (norm === null) return null;
  return "/api/code/raw?dir=" + encodeURIComponent(codeDir)
    + "&path=" + encodeURIComponent(norm);
}

function normalizeRelPath(p) {
  const segs = [];
  for (const seg of String(p == null ? "" : p).split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") {
      if (!segs.length) return null;
      segs.pop();
    } else segs.push(seg);
  }
  return segs.join("/");
}

// ===== 打开 / 激活 / 关闭标签 =====
function activateTab(path) {
  activePath = path;
  const box = paneBox();
  if (box) box.scrollTop = 0;
  renderTabs();
  // 活动标签滚入视野（工单 code-editor-vscode-polish/03）：标签横向溢出被
  // 截断时自动滚到活动标签（inline nearest 不纵向跳动；renderTabs 重建 DOM
  // 后按 path 现查元素）。
  const strip = $("code-tabs");
  if (strip) {
    const el = Array.from(strip.querySelectorAll(".code-tab"))
      .find((t) => t.dataset.tabPath === path);
    if (el) el.scrollIntoView({ inline: "nearest", block: "nearest" });
  }
  resetFoldState();   // 切文件清空折叠态（会话内不跨文件保持，工单 07）
  renderPane();
  notifyActive();
}

export async function openEditorFile(path, mode) {
  const existing = tabOf(path);
  if (existing) {
    if (mode && mode !== "preview" && existing.lang === "md" && existing.mdMode !== mode) {
      setMdMode(path, mode);
    } else {
      activateTab(path);
    }
    return;
  }
  if (tabs.length >= EDITOR_TABS_MAX) {
    toast("error", "已打开 " + EDITOR_TABS_MAX + " 个文件标签：请先关闭不需要的");
    return;
  }
  paneBox().innerHTML = '<span class="code-empty">加载中…</span>';
  const cached = await loadFileState(path);
  if (!cached.ok) {
    paneBox().innerHTML = '<div class="code-empty"><div class="error">加载失败：'
      + cached.message
      + '</div><span class="muted">点击左侧文件可重试。</span></div>';
    toastError({ message: cached.message }, "打开文件失败");
    return;
  }
  const data = cached.data;
  const lang = languageOf(path);
  const tab = {
    path,
    lang,
    content: data.content || "",
    savedContent: data.content || "",
    outline: lang === "md"
      ? markdownOutline(parseMarkdownBlocks(data.content || ""))
      : data.outline || null,
    mtime_ns: data.mtime_ns || "",
    utf8: data.utf8 !== false,
    // 新建 .md tab 尊重 mode（评审整改：搜索命中【未开过的 md】也要落编辑态，
    // 否则 editJumpToFile 的跳行落在预览内滚动、无选区——a1 缺口）
    mdMode: lang === "md" ? (mode === "edit" ? "edit" : "preview") : "edit",
    readonly: data.utf8 === false,
  };
  tabs.push(tab);
  activateTab(path);
  notifyLoaded(path, tab.content, tab.mtime_ns);
}

// setMdMode(path, mode)：.md 两态切换（preview ↔ edit——工单 05 起 edit =
// 可编辑可保存；跳行/查找自动切 edit）——切换后重渲染并通知（大纲不变，
// 查找面板内容随态重算）。
export function setMdMode(path, mode) {
  const tab = tabOf(path);
  if (!tab || tab.lang !== "md" || tab.mdMode === mode) return;
  tab.mdMode = mode;
  if (activePath === path) {
    renderTabs();
    renderPane();
    notifyActive();
  }
}

export function isMdPreviewActive() {
  const tab = getActiveTab();
  return !!(tab && tab.lang === "md" && tab.mdMode === "preview");
}

// closeTab(path, opts = {})：关闭标签——脏 tab 弹 confirmModal（确认丢弃 /
// 取消保留；不误丢修改）；关活动标签 → 激活右邻（无则左邻，再无一无）。
// opts.force = true 跳过脏确认（工单 code-tree-ops/02：树删除前已由
// guardTreeOpWrite 统一提示过，逐 tab 不再重复弹）。
export async function closeTab(path, opts = {}) {
  const idx = tabs.findIndex((t) => t.path === path);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (!opts.force && tab.content !== tab.savedContent) {
    const ok = await confirmModal({
      title: "关闭未保存的标签",
      message: "「" + esc(path) + "」有未保存的修改，关闭将丢弃这些修改。",
      confirmText: "确认关闭",
      cancelText: "取消",
    });
    if (!ok) return;
  }
  tabs.splice(idx, 1);
  if (activePath === path) {
    const next = tabs[Math.min(idx, tabs.length - 1)];
    activePath = next ? next.path : "";
  }
  resetFoldState();   // 关标签后重算折叠态（评审整改 07c：防旧 viewModel 残留污染新活动文件）
  renderTabs();
  renderPane();
  notifyActive();
}

// remapOpenTabPaths(oldPath, newPath, isDir)：树重命名后的 tab 路径映射
// （工单 code-tree-ops/02）——受影响 tab 的 path 改为新值（前缀替换），
// 活动路径同步；内容 / 脏点 / mtime 基准不变（rename 不改内容与磁盘 mtime，
// 保存语义延续）。目录改名 → 其下所有打开 tab 一并映射。
export function remapOpenTabPaths(oldPath, newPath, isDir) {
  let changed = false;
  for (const t of tabs) {
    if (!treeOpAffected(t.path, oldPath, isDir)) continue;
    t.path = treeRenamedPath(t.path, oldPath, newPath);
    changed = true;
  }
  if (!changed) return;
  if (treeOpAffected(activePath, oldPath, isDir)) {
    activePath = treeRenamedPath(activePath, oldPath, newPath);
  }
  resetFoldState();   // 路径映射后重算折叠态（评审整改 07c：防旧 viewModel 污染）
  renderTabs();
  renderPane();
  notifyActive();
}

// invalidateFileCache(path)：失效该文件的加载缓存（工单 code-tree-ops/02）——
// 新建前文件不存在时缓存过 {ok:false}，create 成功后再 open 会命中陈旧
// 失败缓存；重命名后旧路径缓存同理失效（新路径从未缓存过，天然干净）。
export function invalidateFileCache(path) {
  fileCache.delete(fileCacheKey(path));
}

// dirtyTabPaths()：当前有未保存修改且可保存的 tab 路径（工单
// code-tree-ops/02：树操作脏保护按「受影响 tab」判断，与 saveAllDirtyTabs
// 同判据单源）。
export function dirtyTabPaths() {
  return tabs.filter((t) => t.content !== t.savedContent && !t.readonly)
    .map((t) => t.path);
}

// openTabPaths()：当前全部打开 tab 的路径（工单 code-tree-ops/02：树删除
// 后关闭受影响 tab——用全量路径而非仅脏 tab）。
export function openTabPaths() {
  return tabs.map((t) => t.path);
}

// ===== 磁盘变更感知（工单 code-ide-flow/02）=====
// 外部/AI 写盘感知的标签侧接口：codeview 基线对比得出变更后经这些入口
// 落标签态——干净标签自动重载、脏标签置「磁盘已变更」徽章（点徽章弹既有
// 三选：覆盖/加载磁盘版/取消），绝不静默重载（spec：脏标签永不静默）。

// isTabDirty(path)：标签是否含未保存编辑（与 dirtyTabPaths 同判据单源——
// 只读标签不可编辑不会脏，但沿用同一比较式防多判据漂移）。
function isTabDirty(tab) {
  return !!tab && tab.content !== tab.savedContent;
}

// setDiskChanged(paths)：给路径命中且已打开的**脏**标签置「磁盘已变更」
// 标志（仅脏标签由调用方决定置位；未打开路径无标签自然跳过）。只重渲标签
// 条（标志是标签条的展示态——内容/大纲不受影响，评审整改：不同粒度只刷
// 必要面）。
export function setDiskChanged(paths) {
  let any = false;
  for (const path of paths || []) {
    const tab = tabOf(path);
    if (tab && isTabDirty(tab)) { tab.diskChanged = true; any = true; }
  }
  if (!any) return;
  renderTabs();
}

// clearDiskChanged(path)：保存 / 重载 / 「清空已看」后取消标志（磁盘态已
// 对齐或用户已确认知晓——未保存编辑仍由脏点 ● 表达，不丢信息）。
export function clearDiskChanged(path) {
  const tab = tabOf(path);
  if (!tab || !tab.diskChanged) return;
  tab.diskChanged = false;
  renderTabs();
}

// reloadTabFromDisk(path)：干净标签 → 直读磁盘（绕过 memo）/api/code/file
// → applyDiskState 全量对齐（内容/基准/大纲/只读），返回 "reloaded"；磁盘
// mtime 与标签基准相同（上次已同步）→ 零动作返回 "already"（避免重复渲染
// 与重复 toast 计数——基线是「用户确认点」而非「探测点」，外部改动的 diff
// 会持续存在直到「清空并确认已看」）；脏标签 → 拒绝（返回 false，调用方
// 走徽章路径）；磁盘文件已不存在 / 读取失败 → 抛错（调用方保留旧内容不
// 打断——验收 4：删除文件的可继续查看旧内容）。
export async function reloadTabFromDisk(path) {
  const tab = tabOf(path);
  if (!tab) return false;
  if (isTabDirty(tab)) return false;
  const disk = await readDiskState(path);
  if (mtimeEq(disk.mtime_ns, tab.mtime_ns)) return "already";
  applyDiskState(tab, disk);
  return "reloaded";
}

// openDiskConflict(path)：徽章点击入口——复用既有保存冲突三选模态
// （覆盖我的修改 / 加载磁盘版 / 取消；Promise 落定路径与 saveAllDirtyTabs
// 同一来源，不新造模态）。tab 不存在（已关闭）→ 静默。
export function openDiskConflict(path) {
  const tab = tabOf(path);
  if (!tab) return;
  showConflictModal(tab);
}

function closeActiveTab() { closeTab(activePath); }

// ===== 跳行（大纲 / 搜索命中 / 文件内查找共用单一路径）=====
function flashEl(el) {
  if (!el) return;
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), CODE_FLASH_MS);
}

function setActiveLine(line) {
  const box = paneBox();
  if (!box) return;
  const gut = box.querySelectorAll(".code-gutter-line")[line - 1];
  const hl = box.querySelectorAll(".code-hl-line")[line - 1];
  const pre = box.querySelectorAll(".code-pre-line")[line - 1];
  if (!gut && !hl && !pre) return;
  box.querySelectorAll(".code-pre-line.active, .code-gutter-line.active, .code-hl-line.active")
    .forEach((el) => el.classList.remove("active"));
  [gut, hl, pre].forEach((el) => el && el.classList.add("active"));
}

// editJumpToLine(line)：活动 tab 内跳行——.md 预览态滚块级元素
// （data-md-line）；其余 = 行元素 scrollIntoView + 编辑器 setSelectionRange
// （选区即持续高亮）+ flash。折叠态（工单 07）：目标行在折叠区内 → 先自动
// 展开再定位；行号/偏移经视图映射（视图行号真实 = 模型行号顺序索引）。
export function editJumpToLine(line) {
  const box = paneBox();
  if (!box) return;
  const tab = getActiveTab();
  if (!tab) return;
  if (tab.lang === "md" && tab.mdMode === "preview") {
    const el = box.querySelector('[data-md-line="' + line + '"]');
    if (!el) return;
    el.scrollIntoView({ block: "center" });
    flashEl(el);
    return;
  }
  let target = line;
  if (viewModel) {
    // 展开包含目标行的折叠区（spec：跳行落在折叠区内自动展开）
    let expanded = false;
    folds.forEach((f, i) => {
      if (foldedSet.has(i) && f.startLine < line && line <= f.endLine) {
        foldedSet.delete(i);
        expanded = true;
      }
    });
    if (expanded) {
      viewModel = (folds.length && foldedSet.size)
        ? codeFoldVisible(tab.content, folds, foldedSet)
        : null;
      renderPane();
    }
    if (viewModel) {
      const vi = viewLineIndexOf(line);
      if (!vi) return;
      target = vi;
    }
  }
  const el = box.querySelectorAll(".code-hl-line")[target - 1]
    || box.querySelectorAll(".code-pre-line")[target - 1];
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  setActiveLine(target);
  flashEl(el);
  const ta = box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    const range = editorLineRange(tab.content, line);
    if (range) {
      const start = viewModel ? codeFoldModelToView(viewModel.segs, range.start) : range.start;
      ta.focus();
      ta.setSelectionRange(start, start + (range.end - range.start));
    }
  }
  scheduleCursorWork();   // 状态栏 Ln/Col 随跳行刷新（工单 01；顺延一帧，性能整改）
}

// editJumpToFile(path, line)：跨文件跳转（搜索命中）——.md 一律切编辑态
// （行语义需要行号；已开 tab 先 setMdMode，未开 tab 经 mode="edit" 初始化
// ——评审整改 a1：不能再落预览态）→ 跳行。
export async function editJumpToFile(path, line) {
  const tab = tabOf(path);
  const isMd = tab ? tab.lang === "md" : languageOf(path) === "md";
  if (tab && isMd && tab.mdMode === "preview") setMdMode(path, "edit");
  await openEditorFile(path, isMd ? "edit" : undefined);
  editJumpToLine(line);
}

// ===== 保存写盘（工单 code-viewer-editor/03）：Ctrl+S / 按钮 →
// POST /api/code/save（后端 = 工单 01：路径安全单源 + 原子写 + 冲突 409） =====
let saving = false;

// saveActiveTab()：保存当前活动标签——非脏 / 只读（非 UTF-8）拦截中文提示；
// 保存中禁用按钮 + 文本「保存中…」（重复触发合并）；成功 = toast + 脏点
// 清除 + 大纲刷新（服务端重算响应直用）+ mtime_ns 基准更新 + 通知
// （onFileSaved：树大小刷新）；失败 = 中文 toast（400 业务 / 网络可重试，
// 脏点保留）；409 冲突占位 = 中文 message 直出（完整模态 = 工单 04）。
// postSave(tab)：保存载荷单源（工单 code-tab-compile/03 评审整改——saveActiveTab
// 与 saveTabSettled 原来各写一份 {dir, path, content, base_mtime_ns} 四字段载荷）。
// 冲突覆盖路径的 base_mtime_ns 用磁盘现状（不同基准），不经过本函数。
function postSave(tab) {
  return apiPost("/api/code/save", {
    dir: codeDir,
    path: tab.path,
    content: tab.content,
    base_mtime_ns: tab.mtime_ns,
  });
}

export async function saveActiveTab() {
  const tab = getActiveTab();
  if (!tab) { toast("info", "没有打开的文件"); return; }
  if (tab.readonly) {
    toast("error", "只读：文件不是 UTF-8 编码，为免损坏请用外部编辑器保存");
    return;
  }
  if (tab.content === tab.savedContent) { toast("info", "没有需要保存的修改"); return; }
  if (saving) return;
  saving = true;
  const btn = $("btn-code-save");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "保存中…";
  }
  try {
    const resp = await postSave(tab);
    applySavedState(tab, resp);
  } catch (e) {
    if (e.status === 409) {
      showConflictModal(tab);
    } else {
      toastError(e, "保存失败");
    }
  } finally {
    saving = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "保存";
    }
  }
}

// ===== 保存全部脏标签（工单 code-tab-compile/02）：编译前自动落盘 =====
// saveTabSettled(tab)：保存单标签并**等待**冲突处理落定——返回
// "saved"（写盘成功，含覆盖路径）/ "reload"（放弃并重新加载了磁盘版，后续
// 编译可用磁盘版内容）/ "cancel"（取消 / 关闭 × / Esc / 点遮罩 / 保存失败）。
// 与 saveActiveTab 同写盘路径（applySavedState），差异只在 409 后等待用户。
async function saveTabSettled(tab) {
  try {
    const resp = await postSave(tab);
    applySavedState(tab, resp);
    return "saved";
  } catch (e) {
    if (e.status === 409) {
      const outcome = await showConflictModal(tab);
      return outcome === "overwrite" ? "saved" : outcome;
    }
    toastError(e, "保存失败");
    return "cancel";
  }
}

// saveAllDirtyTabs()：编译前置——保存全部脏且非只读标签（只读 / 非脏跳过，
// 零请求）；任一取消（冲突取消 / 保存失败）→ 立即返回
// {ok:false, canceled:true} 并停止（不再保存其余标签，编译应中止）；
// 全部落定 → {ok:true, canceled:false}。目录切换保护：保存期间目录变了 →
// 中止（防写错位置——与冲突模态失效处理同因）。
export async function saveAllDirtyTabs() {
  const baseDir = codeDir;
  for (const tab of dirtySavableTabs(tabs)) {
    if (codeDir !== baseDir) return { ok: false, canceled: true };
    const outcome = await saveTabSettled(tab);
    if (outcome === "cancel") return { ok: false, canceled: true };
  }
  return { ok: true, canceled: false };
}

// dirtySavableTabCount()：脏且非只读标签数（工单 code-write-guard/01——写盘
// 守卫的提示计数；判据与 saveAllDirtyTabs 同源 = dirtySavableTabs 单源）。
export function dirtySavableTabCount() {
  return dirtySavableTabs(tabs).length;
}

// ===== 保存冲突模态（工单 code-viewer-editor/04）：覆盖 / 重载 / 取消 =====
// 409 后先无缓存重读磁盘（/api/code/file，拿磁盘内容 + 新 mtime_ns 基准），
// 弹「磁盘版 vs 我的编辑」双列对比（conflictHTML 纯件）+ 三动作：
// 覆盖写盘（用新基准重存——若隙间再被改会再弹）、放弃并重新加载（tab 取
// 磁盘版，脏点清除）、取消（脏点保留可再存）。模态 shell 复用 confirmModal
// 同款 overlay 类（.ref-files-modal），焦点默认给「取消」防误触。
// 工单 code-tab-compile/02 改造：返回 Promise<"overwrite"|"reload"|"cancel">，
// 供 saveAllDirtyTabs **等待**用户落定（覆盖=写盘成功后 / 重载=加载磁盘后 /
// 取消·关闭×·Esc·点遮罩·保存失败 = cancel）；单文件 Ctrl+S 路径不 await
// 即行为不变（该 Promise 永不 reject）。
let conflictActive = false;
let conflictOnKey = null;

async function readDiskState(path) {
  // 直读磁盘（绕过 memo 缓存——冲突路径必须拿磁盘现状）
  return await apiGet(fileURL(path));
}

function closeConflict() {
  conflictActive = false;
  document.querySelectorAll(".code-conflict-overlay").forEach((o) => o.remove());
  if (conflictOnKey) {
    document.removeEventListener("keydown", conflictOnKey);
    conflictOnKey = null;
  }
}

function showConflictModal(tab) {
  return new Promise((resolve) => {
    (async () => {
      try {
        // 评审整改：①先清旧态（confirmModal 级联清理会 remove 本模态 overlay 而
        // 不重置标志——残留 true 会让下次冲突静默不弹）；②conflictActive 在
        // await 读盘**前**置位——否则等待窗口内再 Ctrl+S 会二度 409 再叠一个
        // 模态（双模态竞态）。
        closeConflict();
        const dirAtOpen = codeDir;
        conflictActive = true;
        const opener = document.activeElement;
        let disk;
        try {
          disk = await readDiskState(tab.path);
        } catch (e) {
          conflictActive = false;
          toastError(e, "读取磁盘版本失败");
          resolve("cancel");
          return;
        }
        // 评审整改：读盘窗口内 tab 可能被关 / 目录可能切换——僵尸引用写盘会落
        // 错位置、toast 误导。失效 → 关闭模态并提示（编辑保留在已关的 tab 上
        // 无从落地，用户重开后处理）。
        if (tabOf(tab.path) !== tab || codeDir !== dirAtOpen) {
          conflictActive = false;
          toast("info", "文件已关闭或目录已切换：冲突处理已取消");
          resolve("cancel");
          return;
        }
        const overlayEl = document.createElement("div");
        overlayEl.className = "ref-files-overlay code-conflict-overlay";
        overlayEl.innerHTML = '<div class="ref-files-modal confirm-modal code-conflict-modal">'
          + '<div class="ref-files-head"><strong>保存冲突</strong>'
          + '<button class="ref-files-close" title="关闭">×</button></div>'
          + '<div class="ref-detail-scroll">'
          + conflictHTML(disk.content || "", tab.content)
          + "</div>"
          + '<div class="pdf-detail-actions">'
          + '<button type="button" class="danger" data-conflict-action="overwrite">覆盖写盘</button>'
          + '<button type="button" data-conflict-action="reload">放弃我的修改并重新加载</button>'
          + '<button type="button" data-confirm-cancel data-conflict-action="cancel">取消</button>'
          + "</div></div>";
        const finish = () => {
          closeConflict();
          // 关闭后把焦点还给触发元素（对齐 confirmModal 先例 ux-walkthrough-02/19）
          if (opener && !opener.disabled && typeof opener.focus === "function"
              && opener.isConnected) opener.focus();
        };
        const settleCancel = () => { finish(); resolve("cancel"); };
        // Tab 焦点陷阱：限制在弹窗内（首尾循环，对齐 confirmModal 先例）
        const onKey = (e) => {
          if (e.key === "Escape") { settleCancel(); return; }
          if (e.key === "Tab") {
            const focusables = Array.from(
              overlayEl.querySelectorAll("button, input, select, textarea, [href], [tabindex]:not([tabindex='-1'])")
            ).filter((el) => !el.disabled && el.offsetParent !== null);
            if (!focusables.length) return;
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
          }
        };
        overlayEl.querySelector(".ref-files-close").addEventListener("click", settleCancel);
        overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) settleCancel(); });
        overlayEl.querySelector('[data-conflict-action="cancel"]').addEventListener("click", settleCancel);
        overlayEl.querySelector('[data-conflict-action="overwrite"]').addEventListener("click", async () => {
          finish();
          try {
            const resp = await apiPost("/api/code/save", {
              dir: codeDir,
              path: tab.path,
              content: tab.content,
              base_mtime_ns: disk.mtime_ns,   // 新基准 = 磁盘现状
            });
            applySavedState(tab, resp, "已保存 " + tab.path + "（覆盖了外部修改）");
            resolve("overwrite");
          } catch (e2) {
            if (e2.status === 409) {
              // 覆盖时隙间又被改：旧模态已关，重新弹（冲突再演，用户再定夺）
              resolve(await showConflictModal(tab));
            } else {
              toastError(e2, "保存失败");
              resolve("cancel");
            }
          }
        });
        overlayEl.querySelector('[data-conflict-action="reload"]').addEventListener("click", () => {
          finish();
          applyDiskState(tab, disk);
          toast("info", "已重新加载磁盘版本，本地修改已放弃");
          resolve("reload");
        });
        conflictOnKey = onKey;
        document.addEventListener("keydown", conflictOnKey);
        document.body.appendChild(overlayEl);
        const cancelBtn = overlayEl.querySelector(".code-conflict-overlay [data-confirm-cancel]");
        if (cancelBtn) cancelBtn.focus();
      } catch (err) {
        conflictActive = false;
        resolve("cancel");
      }
    })();
  });
}

// applySavedState(tab, resp, msg)：保存成功状态落地（成功路径与覆盖路径
// 共用）——脏点清除 / 基准更新 / 大纲刷新 / toast 与通知；memo 缓存同步
// （评审整改 t04：否则关 tab 再开读到保存前的旧缓存内容）。
function applySavedState(tab, resp, msg) {
  tab.savedContent = tab.content;
  tab.mtime_ns = resp.mtime_ns;
  tab.diskChanged = false;   // code-ide-flow/02：保存后磁盘 = 我的内容
  // .md 的大纲是前端算的标题清单（后端 resp.outline 只给 .c/.h 且为
  // null——直接用会把标题大纲清空，工单 05 评审预防）
  tab.outline = tab.lang === "md"
    ? markdownOutline(parseMarkdownBlocks(tab.content))
    : resp.outline;
  fileCache.set(fileCacheKey(tab.path), {
    ok: true,
    data: {
      path: tab.path,
      size_bytes: resp.size_bytes,
      content: tab.content,
      outline: resp.outline,
      mtime_ns: resp.mtime_ns,
      utf8: tab.utf8,
    },
  });
  toast("ok", msg || ("已保存 " + tab.path));
  renderTabs();
  notifyActive();
  notifySaved(tab, resp);
}

// applyDiskState(tab, disk)：重新加载磁盘版（冲突「放弃」路径）——内容/
// 基准/大纲/只读标志全量对齐，脏点清除；memo 缓存同步（同上，防旧缓存）。
function applyDiskState(tab, disk) {
  const lang = tab.lang;
  tab.content = disk.content || "";
  tab.savedContent = tab.content;
  tab.mtime_ns = disk.mtime_ns || "";
  tab.diskChanged = false;   // code-ide-flow/02：磁盘态已对齐，徽章取消
  tab.outline = lang === "md"
    ? markdownOutline(parseMarkdownBlocks(tab.content))
    : disk.outline || null;
  tab.readonly = disk.utf8 === false;
  tab.utf8 = disk.utf8 !== false;
  resetFoldState();   // 内容整体更换：折叠区重算（工单 07）
  fileCache.set(fileCacheKey(tab.path), { ok: true, data: disk });
  renderTabs();
  renderPane();
  notifyActive();
  notifySaved(tab, disk);
}

// ===== 编辑器键盘行为：Tab 缩进 / Enter 自动缩进 / 光标行高亮 =====
// IME 组合输入保护（评审整改）：composition 期间绝不 setSelectionRange 重置
// 选区——会打断中文候选窗（input 逐键触达 sync，只做重渲染不动光标）。
let composing = false;

// ---- 程序化编辑撤销栈（工单 code-page-vscode-overhaul/04）----
// 浏览器原生撤销栈优先：execCommand("insertText")（Chrome 支持、一次一步
// 撤销；旧行为 ta.value= 直赋值会打断原生撤销栈）。execCommand 不可用/失败
// （Firefox/Safari 对 textarea 的 insertText 支持差）→ 降级直赋值 + 快照式
// 自定义撤销栈（覆盖程序化编辑段；nativeUndo 关闭时 Ctrl+Z/Y 拦截走快照）。
let nativeUndo = typeof document.execCommand === "function";
const undoStack = [];   // [{value, selStart, selEnd}] 程序化编辑前快照（限 200 条）
const redoStack = [];

function pushEditSnapshot() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  undoStack.push({ value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd });
  if (undoStack.length > 200) undoStack.shift();
  redoStack.length = 0;
}

function snapshotUndo(redo) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return false;
  const from = redo ? redoStack : undoStack;
  const to = redo ? undoStack : redoStack;
  const snap = from.pop();
  if (!snap) return false;
  to.push({ value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd });
  ta.value = snap.value;
  ta.setSelectionRange(snap.selStart, snap.selEnd);
  syncEditorAfterInput();
  return true;
}

function applyEdit(text, start, end) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  if (ta.value === text) {
    ta.setSelectionRange(start, end);
    return;
  }
  const oldText = ta.value;
  if (nativeUndo) {
    // 公共前后缀 diff → 最小替换区间 → execCommand 走浏览器原生撤销栈；
    // execCommand 会同步触发 input（既有 input 监听同步模型/高亮），随后
    // 只做选区最终落位 + 当前行/状态轻量刷新（不重复全量渲染）。
    let p = 0;
    const minLen = Math.min(oldText.length, text.length);
    while (p < minLen && oldText[p] === text[p]) p++;
    let s = 0;
    while (s < oldText.length - p && s < text.length - p
      && oldText[oldText.length - 1 - s] === text[text.length - 1 - s]) s++;
    const ins = text.slice(p, text.length - s);
    try {
      ta.focus();
      ta.setSelectionRange(p, oldText.length - s);
      if (document.execCommand("insertText", false, ins)) {
        if (ta.value === text) {
          ta.setSelectionRange(start, end);
          setActiveLine(caretLineOf(ta.value, ta.selectionStart));
          scheduleCursorWork();
          return;
        }
        // execCommand 成功但内容与预期不符（罕见）：走全量同步兜底
        syncEditorAfterInput();
        return;
      }
    } catch (err) { /* execCommand 异常 → 降级 */ }
    nativeUndo = false;
  }
  // 降级：直赋值（现状行为）+ 快照栈接管撤销/重做
  pushEditSnapshot();
  ta.focus();
  ta.value = text;
  ta.setSelectionRange(start, end);
  syncEditorAfterInput();
}

function syncEditorAfterInput() {
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  const hl = box && box.querySelector(".code-hl");
  const gutter = box && box.querySelector(".code-gutter");
  if (!box || !ta || !hl || !gutter) return;
  const tab = getActiveTab();
  if (!tab) return;
  if (viewModel) {
    // 折叠态（工单 07）：视图文本编辑 → 偏移映射写回模型；触碰占位 → 展开
    // + 重设视图文本与光标（模型偏移 → 新视图偏移）；折叠区随内容重算并
    // 按签名保留既有折叠态（codeFoldMerge）。
    const r = codeFoldMapEdit(tab.content, viewModel.segs, viewModel.text, ta.value);
    tab.content = r.model;
    r.expand.forEach((i) => foldedSet.delete(i));
    const oldFolds = folds;
    folds = codeFoldRanges(tab.content, tab.lang);
    foldedSet = codeFoldMerge(oldFolds, foldedSet, folds);
    const textChanged = viewModel.text !== ta.value;
    viewModel = (folds.length && foldedSet.size)
      ? codeFoldVisible(tab.content, folds, foldedSet)
      : null;
    if (textChanged) {
      if (viewModel) {
        ta.value = viewModel.text;
        const vo = codeFoldModelToView(viewModel.segs, r.caret);
        ta.setSelectionRange(vo, vo);
      } else {
        // 占位触碰后全部展开（评审整改 07c）：视图回全量文本、光标落插入点
        ta.value = tab.content;
        ta.setSelectionRange(r.caret, r.caret);
      }
    }
  } else {
    tab.content = ta.value;
    // 无折叠态也随输入重算折叠区清单（工单 07：快捷键/箭头基于最新内容）
    folds = codeFoldRanges(tab.content, tab.lang);
  }
  const selStart = ta.selectionStart;
  const selEnd = ta.selectionEnd;
  const scrollTop = box.scrollTop;
  const scrollLeft = box.scrollLeft;
  // 只重绘高亮层与行号列（.code-edit 的 max-content 宽度/高度随 pre 自动
  // 调整，容器滚动不变；textarea 本体不重建——焦点/选区零抖动）
  const viewText = viewModel ? viewModel.text : tab.content;
  gutter.innerHTML = viewModel
    ? codeFoldGutterHTML(viewModel.lines)
    : codeLineNumbersHTML(tab.content.split("\n").length);
  hl.innerHTML = codeEditorHighlight(viewText, tab.lang);
  // 标记层随输入重算（评审整改 05/06）：updateWordMarks/updateBracketMarks
  // 只重算状态不渲染——内容已变，无论词/括号是否变了都必须重画（查找命中
  // 偏移同样变了），此处无条件 renderEditorMarks（单次渲染，无双渲染）。
  updateWordMarks();
  updateBracketMarks();
  renderEditorMarks();
  setActiveLine(caretLineOf(viewText, selStart));
  box.scrollTop = scrollTop;
  box.scrollLeft = scrollLeft;
  if (!composing) {
    ta.focus();
    ta.setSelectionRange(selStart, selEnd);
  }
  renderTabs();   // 脏点随输入即时刷新（标签条内联渲染，事件委托不失效）
  notifyActive();   // 状态栏信息区随内容/光标刷新（onActiveTabChanged → refreshCodeStatus；不再单独 notifyCursor——避免每击键双刷）
}

// ===== 查找替换（工单 code-editor-utilize/03 + code-page-vscode-overhaul/03）=====
// rebaseModelContent(newContent, caret)：模型内容整体替换后的折叠重算 + 视图
// 重建 + 光标落位——折叠态 textarea 须持视图文本，不能经 applyEdit 直写模型
// （会把模型当视图喂 mapEdit → 占位误判整块替换丢内容）；caret = 模型偏移
// （null → 文件尾，与既有「替换后光标置文件尾」语义一致）。
function rebaseModelContent(newContent, caret) {
  const tab = getActiveTab();
  if (!tab) return;
  tab.content = newContent;
  const oldFolds = folds;
  folds = codeFoldRanges(tab.content, tab.lang);
  foldedSet = codeFoldMerge(oldFolds, foldedSet, folds);
  viewModel = (folds.length && foldedSet.size)
    ? codeFoldVisible(tab.content, folds, foldedSet)
    : null;
  renderPane();
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  const caretM = caret == null
    ? tab.content.length
    : Math.max(0, Math.min(tab.content.length, caret));
  const vo = viewModel
    ? codeFoldModelToView(viewModel.segs, caretM)
    : caretM;
  ta.focus();
  ta.setSelectionRange(vo, vo);
}

// replaceAllInActiveFile(needle, replacement)：活动标签全部替换——空针 /
// 无活动标签 / 只读标签 / 无匹配 → 0 且不改；有效时走 applyEdit 同手输路径
// （textarea 值 + 高亮/行号/脏点/标签条同步），光标置于文件尾，不自动写盘
// （用户 Ctrl+S 落盘，与手输同语义）。返回替换次数。
export function replaceAllInActiveFile(needle, replacement) {
  const tab = getActiveTab();
  if (!tab || tab.readonly) return 0;
  const r = replaceAllText(tab.content, needle, replacement);
  if (!r.count) return 0;
  if (viewModel) {
    // 折叠态（评审整改 07）：模型整体替换 → 折叠区按签名保留 → 重建视图 →
    // 光标落模型末尾（与既有「替换后光标置文件尾」语义一致）。
    rebaseModelContent(r.value, null);
    return r.count;
  }
  applyEdit(r.value, r.value.length, r.value.length);
  return r.count;
}

// replaceOneInActiveFile(replacement, jumpToNext)：替换当前命中（工单
// code-page-vscode-overhaul/03）——模型层替换（折叠安全），随后重算命中并
// 更新标记层；jumpToNext 且存在下一命中 → 聚焦选区（模型→视图映射）。
// 返回 {replaced, nextFound, total, current} 供计数联动；无活动标签 / 只读 /
// 空针 / 无命中 → replaced false 且不改动。
export function replaceOneInActiveFile(replacement, jumpToNext) {
  const tab = getActiveTab();
  if (!tab || tab.readonly) return { replaced: false, nextFound: false, total: 0, current: -1 };
  const needle = editorFind.query;
  if (!needle || !editorFind.ranges.length) {
    return { replaced: false, nextFound: false, total: editorFind.ranges.length, current: -1 };
  }
  const idx = editorFind.index < 0 ? 0 : editorFind.index;
  const r = replaceOneAt(tab.content, needle, replacement, idx);
  if (!r.replaced) return { replaced: false, nextFound: false, total: r.total, current: -1 };
  const repl = String(replacement == null ? "" : replacement);
  const caret = r.at + repl.length;
  if (viewModel) rebaseModelContent(r.value, caret);
  else applyEdit(r.value, caret, caret);
  // 重算命中（标记层按新内容），随后按 next 聚焦
  const total = setEditorFind(needle).total;
  let nextFound = false;
  if (jumpToNext && r.next) {
    const ni = editorFind.ranges.findIndex((g) =>
      g.line === r.next.line && g.start === r.next.start && g.end === r.next.end);
    if (ni >= 0) {
      editorFind.index = ni;
      renderEditorMarks();
      focusFindRange(editorFind.ranges[ni]);
      nextFound = true;
    }
  }
  return { replaced: true, nextFound, total, current: editorFind.index };
}

// ===== initCodeEditor：入口绑定（host 启动区调用；DOM 已就绪）=====
export function initCodeEditor() {
  const strip = $("code-tabs");
  if (strip) strip.addEventListener("click", (e) => {
    const close = e.target.closest("[data-tab-close]");
    if (close) {
      e.stopPropagation();
      closeTab(close.closest("[data-tab-path]").dataset.tabPath);
      return;
    }
    // 「磁盘已变更」徽章（code-ide-flow/02）：点击弹既有三选，**不**触发
    // 普通点击的激活 tab（激活会连带内容切换，掩盖用户的冲突决策意图）
    const diskBadge = e.target.closest("[data-tab-disk]");
    if (diskBadge) {
      e.stopPropagation();
      const holder = diskBadge.closest("[data-tab-path]");
      if (holder) openDiskConflict(holder.dataset.tabPath);
      return;
    }
    const btn = e.target.closest("[data-tab-path]");
    if (btn) activateTab(btn.dataset.tabPath);
  });

  // 中键关闭（工单 code-editor-vscode-polish/03）：VSCode 行为——中键点击
  // 非活动标签直接关闭（脏标签仍走 closeTab 的确认弹窗）；活动标签中键不
  // 关；磁盘徽章 / 关闭钮保持显式语义（中键不绕过冲突决策与 × 入口）。
  if (strip) strip.addEventListener("auxclick", (e) => {
    if (e.button !== 1) return;
    const t = e.target.closest("[data-tab-path]");
    if (!t || t.dataset.tabPath === activePath) return;
    if (e.target.closest("[data-tab-disk]") || e.target.closest("[data-tab-close]")) return;
    e.preventDefault();
    closeTab(t.dataset.tabPath);
  });

  // 拖拽排序（工单 code-editor-vscode-polish/03）：HTML5 DnD——dragstart 记
  // 路径（dataTransfer 携带，跨标签实例），dragover 按命中 tab 中线计算插入
  // 位（before/after 用 drop-before/drop-after 指示线），drop 调 moveTab 纯件
  // 重排 + renderTabs（内容/脏点/活动态不动）；空白区拖放 = 追加末尾。
  // 合成事件（CDP 冒烟）与真实拖拽同一路径；dragend 兜底清理标记。
  if (strip) {
    let dragPath = "";
    let dropTargetPath = "";
    let dropPlace = "after";
    let dropAtEnd = false;   // 拖到空白区（无命中 tab）= 追加末尾（与 dragover 命中逻辑分开，防「空路径 = 无操作」歧义）
    const clearDropMarks = () => {
      strip.querySelectorAll(".code-tab.drop-before, .code-tab.drop-after")
        .forEach((el) => el.classList.remove("drop-before", "drop-after"));
    };
    const endDrag = () => {
      dragPath = "";
      dropTargetPath = "";
      dropAtEnd = false;
      clearDropMarks();
      strip.querySelectorAll(".code-tab.dragging")
        .forEach((el) => el.classList.remove("dragging"));
    };
    strip.addEventListener("dragstart", (e) => {
      const tab = e.target.closest("[data-tab-path]");
      if (!tab) return;
      // 从关闭钮 / 磁盘徽章按下不启动拖动（评审整改 03：显式控件保持原语义）
      if (e.target.closest("[data-tab-close]") || e.target.closest("[data-tab-disk]")) return;
      dragPath = tab.dataset.tabPath;
      try {
        e.dataTransfer.setData("text/plain", dragPath);
        e.dataTransfer.effectAllowed = "move";
      } catch (err) { /* 合成事件无 DataTransfer：容错 */ }
      tab.classList.add("dragging");
    });
    strip.addEventListener("dragover", (e) => {
      if (!dragPath) return;
      e.preventDefault();
      try { e.dataTransfer.dropEffect = "move"; } catch (err) { /* 同上 */ }
      clearDropMarks();
      const target = e.target.closest("[data-tab-path]");
      dropAtEnd = false;
      if (!target) {
        // 空白区：追加末尾（无插入位指示线）
        dropTargetPath = "";
        dropAtEnd = true;
        return;
      }
      if (target.dataset.tabPath === dragPath) {
        dropTargetPath = "";   // 拖回自身 = 无操作
        return;
      }
      const rect = target.getBoundingClientRect();
      const before = e.clientX < rect.left + rect.width / 2;
      dropTargetPath = target.dataset.tabPath;
      dropPlace = before ? "before" : "after";
      target.classList.add(before ? "drop-before" : "drop-after");
    });
    strip.addEventListener("drop", (e) => {
      if (!dragPath) return;
      e.preventDefault();
      if (dropTargetPath && dropTargetPath !== dragPath) {
        tabs = moveTab(tabs, dragPath, dropTargetPath, dropPlace);
        renderTabs();
      } else if (dropAtEnd && dropTargetPath !== dragPath) {
        tabs = moveTab(tabs, dragPath, "", "after");
        renderTabs();
      }
      endDrag();
    });
    strip.addEventListener("dragend", endDrag);
  }

  // Ctrl/Cmd+S：tab-code 活动时全局截获（与 Ctrl+F 同口径——焦点在树/侧栏
  // 也生效）；浏览器「保存网页」对话框不出现。
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "s") return;
    if (e.shiftKey) return;  // Ctrl+Shift+S 交给保存全部（initCodeSaveAll，code-tree-ops/03）
    const sec = $("tab-code");
    if (!sec || !sec.classList.contains("active")) return;
    e.preventDefault();
    saveActiveTab();
  });
  const saveBtn = $("btn-code-save");
  if (saveBtn) saveBtn.addEventListener("click", () => saveActiveTab());

  const box = paneBox();
  if (box) {
    // 点击定位光标 → 当前行即时高亮（bug 修复：select（选区变化）与 keyup
    // 双保险不覆盖「鼠标点击纯光标定位」——Chrome 对点击 textarea 定位光标
    // 不派发 select，导致点完一行只见闪烁光标、无行高亮，直到下次输入才补
    // 上。与 select/keyup 同一 setActiveLine 路径（幂等，重复触发无害）；
    // notifyCursor 联动选中词/括号/状态栏）。折叠态：ta.value 为视图文本、
    // selectionStart 为视图偏移——setActiveLine 按视图行索引，与视图行号
    // 列对齐。
    box.addEventListener("click", (e) => {
      const ta = e.target;
      if (ta && ta.classList && ta.classList.contains("code-ta")) {
        setActiveLine(caretLineOf(ta.value, ta.selectionStart));
        scheduleCursorWork();   // 重活顺延一帧：高亮先上屏（性能整改）
      }
    });
    // 折叠交互（工单 07）：gutter 箭头（data-fold）与占位行
    // （data-fold-expand）点击切换——委托在容器（渲染重建后无需重绑）。
    box.addEventListener("click", (e) => {
      const arrow = e.target.closest("[data-fold]");
      if (arrow) {
        e.stopPropagation();
        toggleFold(parseInt(arrow.dataset.fold, 10));
        return;
      }
      const ph = e.target.closest("[data-fold-expand]");
      if (ph) {
        e.stopPropagation();
        toggleFold(parseInt(ph.dataset.foldExpand, 10));
      }
    });
    // 折叠快捷键（工单 07）：Ctrl+Shift+[ 折叠 / Ctrl+Shift+] 展开光标所在
    // 折叠区（最内层）；无折叠区 → 静默。仅「代码」tab 生效。
    document.addEventListener("keydown", (e) => {
      if (!(e.ctrlKey || e.metaKey) || !e.shiftKey) return;
      if (e.key !== "[" && e.key !== "]") return;
      const sec = $("tab-code");
      if (!sec || !sec.classList.contains("active")) return;
      const tab = getActiveTab();
      if (!tab || !folds.length) return;
      e.preventDefault();
      const line = caretLineOf(tab.content, foldCaretModelPos());
      const fi = foldAtLine(line);
      if (fi === null) return;
      if (e.key === "[") {
        if (!foldedSet.has(fi)) toggleFold(fi);
      } else if (foldedSet.has(fi)) {
        toggleFold(fi);
      }
    });
    // 组合输入保护：compositionend 后补一次同步（内容一次性落定）
    box.addEventListener("compositionstart", () => { composing = true; });
    box.addEventListener("compositionend", () => {
      composing = false;
      syncEditorAfterInput();
    });
    // input：草稿同步 + 高亮/行号/尺寸刷新
    box.addEventListener("input", (e) => {
      if (e.target.classList && e.target.classList.contains("code-ta")) {
        syncEditorAfterInput();
      }
    });
    box.addEventListener("keydown", (e) => {
      const ta = e.target;
      if (!ta || !ta.classList || !ta.classList.contains("code-ta") || ta.readOnly) return;
      // 光标行高亮即时跟随（性能整改）：keydown 就更新——浏览器在 keydown
      // 处理时已按本次按键移动了光标，等 keyup 会滞后一次按键节拍（肉眼
      // 感觉 ~0.1s 延时）。setActiveLine 纯 DOM class 切换（同步、立即上
      // 屏）；选中词/括号/状态栏等重活经 scheduleCursorWork 顺延一帧，不
      // 阻塞本帧绘制。Tab/Enter/括号分支随后 applyEdit → syncEditorAfterInput
      // 会再按新选区校正一次（幂等）。
      setActiveLine(caretLineOf(ta.value, ta.selectionStart));
      scheduleCursorWork();
      if (!nativeUndo && (e.ctrlKey || e.metaKey) && !e.altKey) {
        // 快照降级（工单 04）：原生撤销栈不可用时 Ctrl+Z/Y 走自定义栈
        const k = e.key.toLowerCase();
        if (!e.shiftKey && (k === "z" || k === "y")) {
          e.preventDefault();
          snapshotUndo(k === "y");
          return;
        }
        if (e.shiftKey && k === "z") {
          e.preventDefault();
          snapshotUndo(true);
          return;
        }
      }
      if (e.key === "Tab" && e.shiftKey) {
        e.preventDefault();
        const r = shiftTab(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (e.key === "Tab") {
        e.preventDefault();
        const r = indentLines(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const r = indentOnEnter(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing
        && (e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "k") {
        // 行操作（工单 code-page-vscode-overhaul/01）：Ctrl+Shift+K 删除行
        e.preventDefault();
        const r = deleteLine(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && e.altKey && !e.ctrlKey && !e.metaKey
        && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        // 行操作（工单 code-page-vscode-overhaul/01）：Alt+↑↓ 移动行 /
        // Shift+Alt+↑↓ 复制行
        e.preventDefault();
        const dir = e.key === "ArrowUp" ? "up" : "down";
        const r = e.shiftKey
          ? copyLine(ta.value, ta.selectionStart, ta.selectionEnd, dir)
          : moveLine(ta.value, ta.selectionStart, ta.selectionEnd, dir);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && (e.ctrlKey || e.metaKey)
        && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "l") {
        // 行操作（工单 code-page-vscode-overhaul/01）：Ctrl+L 选整行
        e.preventDefault();
        const r = lineRangeOf(ta.value, ta.selectionStart, ta.selectionEnd);
        ta.setSelectionRange(r.start, r.end);
        setActiveLine(caretLineOf(ta.value, ta.selectionStart));
        scheduleCursorWork();
      } else if (!e.isComposing && !composing && (e.ctrlKey || e.metaKey)
        && !e.shiftKey && !e.altKey && e.key === "/") {
        // 注释切换（工单 code-page-vscode-overhaul/02）：.c/.h 逐行 //、
        // 选中含 /* */ 切块注释；XML 逐行 <!-- -->（仅 c/xml 编辑态）
        const tab = getActiveTab();
        if (!tab || (tab.lang !== "c" && tab.lang !== "xml")) return;
        e.preventDefault();
        const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd);
        const r = tab.lang === "xml"
          ? toggleLineComment(ta.value, ta.selectionStart, ta.selectionEnd,
            { open: "<!--", close: "-->" })
          : (sel.includes("/*")
            ? toggleBlockComment(ta.value, ta.selectionStart, ta.selectionEnd,
              { open: "/*", close: "*/" })
            : toggleLineComment(ta.value, ta.selectionStart, ta.selectionEnd,
              { open: "//" }));
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && (BRACKET_OPEN[e.key] || BRACKET_CLOSE[e.key] || e.key === "Backspace")) {
        // 括号行为（工单 06）：仅 c/xml/md 编辑态启用（spec：plain 走浏览器
        // 默认插入——评审整改 06b）；IME 组合输入中不拦截（评审整改 06a）。
        const tab = getActiveTab();
        const langOk = !!tab && (tab.lang === "c" || tab.lang === "xml" || tab.lang === "md");
        if (!langOk) return;
        if (BRACKET_OPEN[e.key]) {
          e.preventDefault();
          const r = bracketOpen(ta.value, ta.selectionStart, ta.selectionEnd, e.key);
          applyEdit(r.value, r.start, r.end);
        } else if (BRACKET_CLOSE[e.key]) {
          const r = bracketClose(ta.value, ta.selectionStart, ta.selectionEnd, e.key);
          if (r) {
            e.preventDefault();
            applyEdit(r.value, r.start, r.end);
          }
        } else if (e.key === "Backspace") {
          const r = bracketBackspace(ta.value, ta.selectionStart, ta.selectionEnd);
          if (r) {
            e.preventDefault();
            applyEdit(r.value, r.start, r.end);
          }
        }
      }
    });
    // 光标行高亮跟随（selection 变化：键盘 / 鼠标共同覆盖——select + keyup
    // 双保险；不逐按键重算，评审整改归并 keydown/click/keyup 三处）
    box.addEventListener("select", () => {
      const ta = box.querySelector(".code-ta");
      if (ta) setActiveLine(caretLineOf(ta.value, ta.selectionStart));
      scheduleCursorWork();   // 状态栏 Ln/Col 随选区变化刷新（工单 01；顺延一帧，性能整改）
    });
    box.addEventListener("keyup", (e) => {
      const ta = e.target;
      if (ta && ta.classList && ta.classList.contains("code-ta")) {
        setActiveLine(caretLineOf(ta.value, ta.selectionStart));
        scheduleCursorWork();
      }
    });
  }
}
