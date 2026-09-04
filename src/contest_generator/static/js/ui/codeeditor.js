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
import { languageOf, lineEndState, lineStatesOf, highlightLineHTML } from "/js/fx/highlight.js";
import { codeGutterLineHTML } from "/js/fx/codeview.js";
import { codeFindRanges, codeMarksHTML, codeWordAt, codeWordRanges, codeIndentGuideMarks } from "/js/fx/code-marks.js";  // 标记层纯件（工单 code-editor-vscode-polish/04-06：查找/选中词/括号共用；07 缩进引导线）
import {
  BRACKET_OPEN,
  BRACKET_CLOSE,
  bracketOpen,
  bracketClose,
  bracketBackspace,
  bracketDepthMarks,
  bracketPairScan,
  pairScanPatch,
  bracketPairFromEntries,
} from "/js/fx/code-brackets.js";  // 括号配对与自动闭合纯件（工单 code-editor-vscode-polish/06）+ 彩虹深度标记（code-editor-refine/04）+ 配对扫描缓存（code-editor-opt/02）
import {
  codeTabStripHTML,
  codeEditorHTML,
  codeWindowRange,
  conflictHTML,
  editorLineRange,
  isTabSavable,
  dirtySavableTabs,
  caretLineOf,
  caretColOf,
  caretLineFromStarts,
  buildLineStarts,
  patchLineStarts,
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
  codeFoldGutterLines,
  codeFoldMerge,
} from "/js/fx/code-fold.js";  // 代码折叠纯件（工单 code-editor-vscode-polish/07；08 行号窗口化）
import { confirmModal } from "/js/ui/confirm.js";
import { unsavedSwitchModalHTML } from "/js/fx/exit-guard.js";  // 未保存退出保护纯件（工单 code-editor-refine/01）
import { compileErrorLinesForFile } from "/js/fx/code-compile.js";  // 编译错误→行映射纯件（工单 code-editor-refine/05）
import { insertAtPosition } from "/js/fx/ai-insert.js";  // AI 代码块插入位置纯件（工单 code-editor-refine/08）
import { editChangeSpan, marksPatch, marksPartition, wordRangesPatch } from "/js/fx/edit-patch.js";  // 变更段判定 + 标记增量修补/分区/词区段增量（工单 code-editor-opt/01+02）
import {
  windowTextBuild,
  windowEditToView,
  windowEditToModel,
  windowPosFromView,
  windowPosToView,
  windowTextMatchesModel,
} from "/js/fx/window-text.js";  // 视口化窗口文本纯件（工单 editor-textarea-viewport/01）：窗口构建 / 编辑映射 / 光标偏移换算 / 一致性校验
import { undoPush, undoStep, redoStep } from "/js/fx/undo-stack.js";  // 模型级快照撤销栈纯件（工单 editor-textarea-viewport/03）：push/undo/redo 状态机（上限 200，新编辑清空 redo）

// ---- 模块态：目录 / 标签 / 活动文件 / 内容 memo / 监听器 ----
let codeDir = "";
let tabs = [];           // {path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode, readonly}
let activePath = "";
// 编译错误（工单 code-editor-refine/05）：结构错误列表（done.parsed_errors 同型）
// 的编辑器侧显示态——状态归本模块（ui 单向依赖约定：code-compile → codeeditor，
// 反向 import 会成环、撞 ui-cycle 守卫）；写方 = code-compile 经 setCompileErrors
// （编译开始/失败/完成/清除时驱动重画），读方 = 本模块标记层/行号色点与外部
// getCompileErrors。code-compile 不 import 本模块反向边。
let compileErrors = [];

// setCompileErrors(errs)：编译错误列表更新（写方 = ui/code-compile）→ 重画
// 标记层 + 行号色点（renderEditorMarks 早退安全：无标记层/未开文件静默，打开
// 后 renderPane → winRender 自然取新状态）。
export function setCompileErrors(errs) {
  compileErrors = Array.isArray(errs) ? errs : [];
  markClean = false;   // 工单 11：错误集变化 → 标记/色点重算
  renderEditorMarks();
}

// getCompileErrors()：读方访问器（与 setCompileErrors 成对导出——工单 05 接口
// 对称；当前读方 = 本模块 currentMarks/winRenderMarks，外部可扩展）。
export function getCompileErrors() {
  return compileErrors;
}
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

// 未保存退出保护（工单 code-editor-refine/01）：任一脏标签 → 刷新/关闭页面
// 触发浏览器原生离开确认（文案由浏览器决定，无法定制）；判据动态求值——
// 保存/重载/关闭标签后自动正确，无需维护拦截状态。
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", (e) => {
    if (!dirtySavableTabs(tabs).length) return;
    e.preventDefault();
    e.returnValue = "";
  });
}

// showUnsavedSwitchModal(dir)：目录切换三选模态——「保存全部并切换 / 放弃
// 修改并切换 / 取消」→ Promise<"save" | "discard" | "cancel">。HTML 纯件
// fx/exit-guard.js；接线对齐 conflictModal 先例（Esc / × / 点遮罩 = 取消、
// Tab 焦点陷阱、关闭后焦点归还触发元素；默认焦点给「取消」防误触）。
function showUnsavedSwitchModal(dir) {
  return new Promise((resolve) => {
    const opener = document.activeElement;
    const overlayEl = document.createElement("div");
    overlayEl.className = "ref-files-overlay";
    overlayEl.innerHTML = unsavedSwitchModalHTML({ dir, dirtyTabs: dirtySavableTabs(tabs) });
    const onKey = (e) => {
      if (e.key === "Escape") { finish("cancel"); return; }
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
    let settled = false;
    const finish = (action) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey);
      overlayEl.remove();
      // 关闭后把焦点还给触发元素（对齐 confirmModal 先例 ux-walkthrough-02/19）
      if (opener && !opener.disabled && typeof opener.focus === "function"
          && opener.isConnected) opener.focus();
      resolve(action);
    };
    overlayEl.querySelector(".ref-files-close").addEventListener("click", () => finish("cancel"));
    overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) finish("cancel"); });
    overlayEl.querySelector('[data-unsaved-action="cancel"]').addEventListener("click", () => finish("cancel"));
    overlayEl.querySelector('[data-unsaved-action="save"]').addEventListener("click", () => finish("save"));
    overlayEl.querySelector('[data-unsaved-action="discard"]').addEventListener("click", () => finish("discard"));
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlayEl);
    const cancelBtn = overlayEl.querySelector('[data-unsaved-action="cancel"]');
    if (cancelBtn) cancelBtn.focus();
  });
}

// setCodeDir(dir)：目录切换（codeview.loadCodeDir 唯一调用方）——清标签/缓存/
// 活动态（目录变了旧文件无意义，防跨目录悬空引用）。未保存保护：存在脏标签
// 时先弹三选（保存全部并切换 / 放弃修改并切换 / 取消）；取消或保存未落盘 →
// 返回 false（不切换，编辑保留）；成功切换返回 true。
export async function setCodeDir(dir) {
  if (dirtySavableTabs(tabs).length > 0) {
    const action = await showUnsavedSwitchModal(dir);
    if (action === "cancel") return false;
    if (action === "save") {
      const saved = await saveAllDirtyTabs();
      if (!saved.ok) return false;   // 任一保存取消/冲突未落定：中止切换
    }
    // action === "discard"：继续清空（丢弃）
  }
  codeDir = dir;
  tabs = [];
  activePath = "";
  fileCache.clear();
  resetFoldState();
  resetUndoStack();   // 03：目录切换 → 撤销栈清空（防跨目录错撤）
  renderTabs();
  renderPane();
  notifyActive();
  return true;
}

// ===== 标签访问 =====
export function getActiveTab() {
  return tabs.find((t) => t.path === activePath) || null;
}

// onActiveTabChanged(cb)：活动标签变化监听（codeview 注册：大纲/查找面板
// 随活动文件联动）。
export function onActiveTabChanged(cb) { activeListeners.add(cb); }

// onFileSaved(cb)：保存成功监听（codeview 注册：树节点大小刷新；main.c
// 步骤 8 状态行刷新 = 工单 05；code-compile 注册自动编译钩子 = 工单 10）——
// 回调 (tab, resp, manual)：manual = 本次为用户显式保存（Ctrl+S/保存按钮/
// 「保存全部」/冲突「覆盖写盘」确认），false = 程序化自动落盘（编译前
// saveAllDirtyTabs / 守卫保存 / 磁盘重载通知）——自动编译只认手工。
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

function notifySaved(tab, resp, manual) {
  savedListeners.forEach((cb) => { try { cb(tab, resp, manual); } catch (e) { /* 同上 */ } });
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
// 工单 11 性能整改：结构性门控——纯字符编辑（无换行/括号/引号/#/tab/行首
// 空白变化）时折叠清单与标记集不变，跳过全量重算（5000 行逐键 GC/扫描主
// 热点）；任何结构变更/状态变化（查找/词/括号/错误/换 tab）置 false。
let markClean = false;
let marksCache = { content: null, marks: [] };   // 模型级标记缓存（窗口过滤每次切片）

// currentMarks(errLines?)：当前应渲染的标记清单（缩进引导线 + 括号彩虹 + 查找
// 命中 + 当前命中 + 选中词 + 括号配对 + 编译错误行；07 引导线按模型文本逐行
// 计算，折叠视图经 marksForView 映射——占位行被折叠的引导线自动丢弃）。
// errLines 可选：由 winRenderMarks 预计算的当前文件错误行（评审整改：渲染
// 路径避免 currentMarks 与 winRenderGutterErrors 各算一遍映射），缺省自算。
export function currentMarks(errLines) {
  const out = [];
  const tab = getActiveTab();
  if (tab) out.push(...indentGuideMarksCached(tab.content));
  if (tab && bracketRainbowLang(tab)) out.push(...bracketRainbowMarks(tab));
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
  // 编译错误行（工单 code-editor-refine/05）：全行标记（kind error 最高优先
  // 4，压过查找/当前/词/括号）——title = 消息（codeMarksHTML 转义后悬停）；
  // 数据源 = 编译面板结构错误列表经纯件按当前文件路径映射。空行无法经 span
  // 切割出下划线（seg 需 b>a），行号色点 + gutter title 兜底该边缘。
  if (tab) {
    const lines = tab.content.split("\n");
    const errs = errLines || compileErrorLinesForFile(getCompileErrors(), tab.path);
    for (const er of errs) {
      if (er.line < 1 || er.line > lines.length) continue;   // 越界行号钳制（评审整改）
      const ln = (lines[er.line - 1] || "").length;
      out.push({ line: er.line, start: 0, end: ln, kind: "error", title: er.message });
    }
  }
  return out;
}

// ---- 括号配对高亮（工单 code-editor-vscode-polish/06）----
// 光标在括号上/紧邻 → 配对括号两段标记（kind: "bracket"，下划线类样式）；
// 仅 .c/.h 与 xml 启用（spec：.md 编辑源码态只自动闭合不配对高亮）。
let editorBracket = null;

// ---- 括号彩虹（工单 code-editor-refine/04）----
// 全文档配对括号按嵌套深度染色（8 色环）；只随内容变化，故按 tab.content
// 引用缓存（编辑产生新字符串——引用比较即版本比较，光标移动零重算）。
// 门控 = 可编辑的 c/xml/md（工单验收：xml/md 生效、plain/txt 不生效；与既有
// 光标对描边门控 c/xml 不同——彩虹为全文档静态着色，md 源码态一并启用）。
let bracketRainbowCache = { content: null, marks: [] };

function bracketRainbowLang(tab) {
  return !!tab && !tab.readonly
    && (tab.lang === "c" || tab.lang === "xml" || tab.lang === "md");
}

function bracketRainbowMarks(tab) {
  if (bracketRainbowCache.content !== tab.content) {
    bracketRainbowCache = { content: tab.content, marks: bracketDepthMarks(tab.content) };
  }
  return bracketRainbowCache.marks;
}

// 缩进引导线缓存（工单 code-editor-opt/01）：与括号彩虹同款「按内容引用缓存」；
// 非结构编辑时由 syncEditorAfterInput 与彩虹/合并缓存一起做行级增量修补，
// 避免 currentMarks 逐键全量重扫（6000 行文件引导线扫描 + 括号扫描 = 输入链
// 主要 CPU 热点，见 spec 实测）。
let indentGuideCache = { content: null, marks: [] };

function indentGuideMarksCached(content) {
  if (indentGuideCache.content !== content) {
    indentGuideCache = { content, marks: codeIndentGuideMarks(content) };
  }
  return indentGuideCache.marks;
}

// 配对扫描缓存（工单 code-editor-opt/02）：非结构编辑不碰括号 → 配对清单增量
// 修补（pairScanPatch）后按内容引用复用；光标贴 `}`/`{` 时 updateBracketMarks
// 不再每次 bracketPairAt 全文档重扫 + 重建配对表 Map（6000 行文件实测 ~5ms +
// 大量 GC）。结构编辑/换 tab 内容引用失配 → 自动回退全量 bracketPairScan。
let pairScanCache = { content: null, entries: [] };

function pairScanEntriesCached(content) {
  if (pairScanCache.content !== content) {
    pairScanCache = { content, entries: bracketPairScan(content) };
  }
  return pairScanCache.entries;
}

// caretLineFast(pos)：光标行号快速路径（工单 code-editor-opt/02）——窗口缓存
// 的行起点数组二分 O(log n)，替代 caretLineOf 的 O(n) 逐字符数换行（6000 行
// 文件光标在末行时 ~13ms/次 → <1ms）。正确性：非结构编辑不增删换行 → 新旧
// 文本行起点集合相同，可用旧数组对新 pos；结构编辑后 winBuild 已重建数组；
// 折叠态 = 视图文本行起点，调用方传视图 pos。缓存缺失 → 兜底 caretLineOf。
function caretLineFast(pos) {
  if (winCache && winCache.lineStarts) {
    return caretLineFromStarts(winCache.lineStarts, pos);
  }
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  return caretLineOf(ta ? ta.value : "", pos);
}

// patchEditorBracket(span)：括号对高亮状态增量修补（工单 code-editor-opt/02）
// ——非结构编辑不碰括号：开/闭两段的行号不变，仅「变更行内位于变更段之后」的
// 列偏移平移 delta；供 markClean 路径把「配对高亮活跃」也纳入标记缓存复用
// （否则 cursor 贴 `}` 时每次 input 因 editorBracket 非空走全量重扫）。
function patchEditorBracket(span) {
  if (!editorBracket) return;
  const oldText = winCache ? winCache.text : "";
  const lineStart = oldText.lastIndexOf("\n", span.p - 1) + 1;
  const segStart = span.p - lineStart;
  const segEnd = segStart + span.oldSegLen;
  const delta = span.newSegLen - span.oldSegLen;
  const shiftMark = (m) => {
    if (!m || m.line !== span.line) return m;
    if (m.end <= segStart) return m;
    if (m.start >= segEnd) return { ...m, start: m.start + delta, end: m.end + delta };
    return { ...m, start: m.start, end: Math.max(m.end + delta, m.start) };
  };
  editorBracket = {
    ...editorBracket,
    open: shiftMark(editorBracket.open),
    close: shiftMark(editorBracket.close),
  };
}

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
  // 工单 code-editor-opt/02：配对清单先按内容引用查缓存（非结构编辑已增量修补；
  // 结构编辑/换 tab 内容失配 → pairScanEntriesCached 自动全量重扫一次），
  // 避免 bracketPairAt 逐键全文档重扫 + 重建配对表 Map（6000 行 + 光标贴 `}`）。
  const pair = bracketPairFromEntries(pairScanEntriesCached(tab.content), pos);
  const changed = JSON.stringify(pair) !== JSON.stringify(editorBracket);
  if (changed) editorBracket = pair;
  return changed;
}

// refreshMarkSetters()：选中词 + 配对高亮状态重算，变了才渲染标记层一次
// （notifyCursor / renderPane 各出口统一调用；渲染单点 = renderEditorMarks）。
function refreshMarkSetters() {
  const wc = updateWordMarks();
  const bc = updateBracketMarks();
  if (wc || bc) {
    markClean = false;   // 工单 11：词/括号状态变化 → 标记需重算
    renderEditorMarks();
  }
}

// ===== 折叠视图助手（工单 code-editor-vscode-polish/07）=====
// marksForView()：把模型行号的标记清单映射到视图行（占位行丢弃——被折叠的
// 命中/词/括号不显示；行内偏移不变）。
function marksForView(errLines) {
  const map = new Map();
  viewModel.lines.forEach((l, i) => { if (!l.placeholder) map.set(l.no, i + 1); });
  return currentMarks(errLines)
    .filter((m) => map.has(m.line))
    .map((m) => ({ line: map.get(m.line), start: m.start, end: m.end, kind: m.kind, title: m.title }));
}

// foldCaretModelPos()：当前光标 → 模型偏移（无折叠时 = 视图/模型偏移；
// 窗口化态 ta.selectionStart 是窗口内偏移，经 taCaretViewPos 换算）。
function foldCaretModelPos() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return 0;
  const viewPos = taCaretViewPos();
  return viewModel ? codeFoldViewToModel(viewModel.segs, viewPos) : viewPos;
}

// editorCaretModelPos()：状态栏 Ln/Col 数据源（模型行/列——折叠态下视图行号
// 与模型行号不同；导出供 codeview 状态栏刷新）。
export function editorCaretModelPos() {
  const tab = getActiveTab();
  if (!tab) return { line: 1, col: 1 };
  const modelPos = foldCaretModelPos();
  // 无折叠态且窗口缓存文本 = 模型文本 → 行起点数组二分（工单 code-editor-opt/02）；
  // 折叠态/缓存陈旧 → 走原 caretLineOf（模型文本），语义不回退。
  const line = (!viewModel && winCache && winCache.text === tab.content)
    ? caretLineFromStarts(winCache.lineStarts, modelPos)
    : caretLineOf(tab.content, modelPos);
  return { line, col: caretColOf(tab.content, modelPos) };
}

// editorSelectionView()：当前 textarea 选区的**视图**坐标（{start,end}；无选区
// → null）——窗口化态把窗口内偏移换算回视图偏移（非折叠视图=模型）；折叠态
// 选区本身即视图偏移（数据源 = 高亮层 data-code-line 同口径）。
export function editorSelectionView() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta || ta.selectionEnd <= ta.selectionStart) return null;
  const s = Math.max(0, ta.selectionStart | 0);
  const e = Math.max(0, ta.selectionEnd | 0);
  return taWinInfo
    ? { start: windowPosToView(taWinInfo, s), end: windowPosToView(taWinInfo, e) }
    : { start: s, end: e };
}

// editorSelectionModel()：当前选区的**模型**坐标（{start,end}；无选区 → null）
// ——折叠态视图→模型映射；窗口化/全量态视图=模型。供 code-ai-chat 选区上下文
// 等外部模块取模型级片段（textarea 窗口文本不能直接 slice）。
export function editorSelectionModel() {
  const v = editorSelectionView();
  if (!v) return null;
  if (viewModel) {
    return {
      start: codeFoldViewToModel(viewModel.segs, v.start),
      end: codeFoldViewToModel(viewModel.segs, v.end),
    };
  }
  return v;
}

// editorViewText()：当前视图文本（窗口化 = 模型全文；折叠 = viewModel.text）——
// 外部模块按视图行号定位高亮层时的文本源（与 .code-hl-line data-code-line 同
// 口径）。
export function editorViewText() {
  const tab = getActiveTab();
  return viewModel ? viewModel.text : (tab ? tab.content : "");
}

// viewLineIndexOf(modelLine)：模型行号 → 视图行号（1 基）；不可见（占位/
// 越界）→ 0。
function viewLineIndexOf(modelLine) {
  if (!viewModel) return modelLine;
  const idx = viewModel.lines.findIndex((l) => !l.placeholder && l.no === modelLine);
  return idx < 0 ? 0 : idx + 1;
}

// refreshFoldView()：折叠态变更后重建视图模型并重渲染（保留光标：视图偏移
// → 模型偏移 → 新视图偏移；03/04：textarea 选区在窗口化后即窗口偏移，
// taCaretViewPos 单源换算视图）；全部展开 → viewModel = null 回全量路径。
function refreshFoldView() {
  const tab = getActiveTab();
  if (!tab) return;
  const box = paneBox();
  const oldTa = box && box.querySelector(".code-ta");
  const oldSegs = viewModel ? viewModel.segs : null;
  const oldViewCaret = oldTa ? taCaretViewPos() : 0;
  const caretModel = oldSegs ? codeFoldViewToModel(oldSegs, oldViewCaret) : oldViewCaret;
  viewModel = (folds.length && foldedSet.size)
    ? codeFoldVisible(tab.content, folds, foldedSet)
    : null;
  renderPane();
  const ta = box && box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    ta.focus();
    const vo = viewModel ? codeFoldModelToView(viewModel.segs, caretModel) : caretModel;
    if (taWinInfo) taWindowApply(vo);   // 04：折叠/非折叠窗口化统一按视图偏移重装
    else ta.setSelectionRange(vo, vo);
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
// editorWord 相关状态（updateWordMarks）
let editorWord = { word: "", ranges: [] };
let editorWordContent = null;   // 上次重算时的 tab.content 引用（性能整改：内容引用短路）
// 本次输入的变更段（工单 code-editor-opt/02，模块级供 updateWordMarks 增量用；
// 仅 syncEditorAfterInput 非结构路径设置，其余路径置 null 防陈旧 span 误用）
let curEditSpan = null;

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
  // 工单 code-editor-opt/02：非结构编辑 + 词未变 → 词区段行级增量（其它行
  // 原样、变更行局部重算），替代 codeWordRanges 全文扫描 + JSON 对比。
  // 前置守卫：curEditSpan 必须与 (editorWordContent → content) 的转换一致
  // （winCache.text 仍是旧内容、editorWordContent 同引用时才启用，防陈旧 span）。
  if (curEditSpan && !curEditSpan.structural && word === editorWord.word
    && editorWordContent !== null && editorWordContent === (winCache ? winCache.text : null)
    && word) {
    // 工单 code-editor-opt/05：内容已变 → 区段位置必变（无需 JSON.stringify
    // 对比 2000+ 条——changed=true 触发重渲即可，语义与刷新路径一致）
    const ranges = wordRangesPatch(editorWord.ranges, word, editorWordContent, content, curEditSpan);
    editorWord = { word, ranges };
    editorWordContent = content;
    return true;
  }
  const ranges = word ? codeWordRanges(content, word) : [];
  // 工单 code-editor-opt/05：词变了 → 必变（常见热路径，省 2000+ 条 JSON 对比）；
  // 词未变但走到这里 = 内容变更未经增量（缓存失配等）→ 对比判定
  const changed = word !== editorWord.word
    ? true
    : JSON.stringify(ranges) !== JSON.stringify(editorWord.ranges);
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
  if (markClean) return;   // 工单 11：纯字符编辑且无命中/词/括号/错误态 → 标记层沿用
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
  winRenderMarks();
}

// setEditorFind(query)：查找输入变化 → 存查询、重算命中区段并渲染标记层——
// 返回 {total, current}（current = 当前索引 0 基；无命中 → {total:0, current:-1}）。
// 编辑器未打开时只存状态（渲染在 renderPane/sync 时落地）。
export function setEditorFind(query) {
  editorFind.query = String(query == null ? "" : query);
  editorFind.index = 0;
  markClean = false;   // 工单 11：查询态变化 → 标记需重算
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
  taSetRange(vPos, vEnd);
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

// ===== 滚动窗口化渲染（工单 code-page-vscode-overhaul/08）=====
// 三层（高亮 .code-hl / 标记 .code-marks / 行号 .code-gutter）只渲染视口窗口
// 行（上下各 WIN_OVERSCAN 行），上下 spacer 撑起全高——窗口内的滚动是纯
// CSS 位移（零 DOM 变更），跨窗口才重建；textarea / .code-edit 尺寸保持全量
// （选区、光标、横滚度量基础）。高亮逐行数组在内容变化时整段算一次
// （highlightCodeLines 跨行 token 在行界闭合/重开，行间独立），滚动只切片。
const WIN_OVERSCAN = 20;
let winCache = null;   // { hl: string[], gutter: string[], lineCount, probeText, probeCols }
let winLineH = 20;     // 实测行高 px（随 --code-font-size/行高变化重测）
let winLast = null;    // { start, end, lineCount }——窗口未变 → 零 DOM
let winSize = null;    // { lineCount, lineH, cols, chW }——尺寸缓存（工单 09：行数/行高/
                       // 最长列数不变则不碰样式；列数增长按 ch 宽估算，零强制布局）
let winView = { scrollTop: 0, viewportH: 0 };  // 滚动/视口缓存（工单 09：输入同步路径
                                               // 绝不读 scrollTop/clientHeight——值变更后
                                               // 首次布局读实测 50ms/次）
let taWinInfo = null;  // 当前 textarea 窗口（windowTextBuild 输出；非折叠窗口化态非空，
                       // 窗口编辑回写/光标映射/滚动同步共用——textarea 只装窗口文本）
let taWinDirty = false; // IME 组合中窗口文本随 raw 值漂移：组合中不重装，
                        // compositionend 后 sync 一次性重装（防打断候选窗）

// winReadView()：滚动/尺寸变化事件里刷新缓存（事件发生时布局已一致，读便宜）。
function winReadView() {
  const box = paneBox();
  if (!box) return;
  winView = { scrollTop: box.scrollTop, viewportH: box.clientHeight };
}

function winLineHeight() {
  const box = paneBox();
  const el = box && box.querySelector(".code-hl-line");
  if (el) {
    const lh = parseFloat(getComputedStyle(el).lineHeight);
    if (lh > 0) return lh;
  }
  const fs = parseFloat(getComputedStyle(box).fontSize) || 13;
  return fs * 1.6;
}

// winBuild(viewText, lang)：内容变化后重建逐行缓存（高亮数组 / gutter 数组 /
// 最长行探针文本 / 行数与行高）。工单 11 增存 text 与 probeIndex（增量 patch
// 判定用——逐键不再全量重建）。工单 code-editor-opt/06：hl 数组**惰性占位**
// （null = 未算，渲染取用前单行现算回填）——打开 6000 行文件不再全量 tokenize
// （实测打开 227ms 的主要成本，窗口化只画 ~56 行），打开成本降到 O(窗口)；
// 滚动即补、命中缓存零成本。自愈守卫：gutter 必须与 hl 行数 1:1——折叠视图
// 态与内容不同源（用户现场：行 26-34 无行号、框截止）时以平铺行号补齐，保证
// 行号/高亮逐行对齐（窗口化渲染切片才能同步）。
function winBuild(viewText, lang) {
  const lines = viewText.split("\n");
  const hl = new Array(lines.length).fill(null);
  const gutter = viewModel
    ? codeFoldGutterLines(viewModel.lines)
    : lines.map((_, i) => codeGutterLineHTML(i + 1));
  if (gutter.length !== lines.length) {
    // 自愈：gutter 来源行数 ≠ 当前内容行数（旧折叠视图态残留/跨文件混合）——
    // 补齐成平铺行号（不替换已有折叠箭头行，只补缺），行号与高亮恢复 1:1。
    const plain = lines.map((_, i) => codeGutterLineHTML(i + 1));
    for (let i = 0; i < lines.length; i++) {
      if (gutter[i] == null) gutter[i] = plain[i];
    }
    gutter.length = lines.length;
  }
  let probeText = "";
  let probeCols = 0;
  let probeIndex = -1;
  for (let i = 0; i < lines.length; i++) {
    const col = lines[i].replace(/\t/g, "    ").length;
    if (col > probeCols) { probeCols = col; probeText = lines[i]; probeIndex = i; }
  }
  winCache = {
    hl, gutter, lineCount: hl.length,
    lines,                    // 行数组（工单 code-editor-opt/02：窗口切片/标记窗口文本复用，免每次 split）
    lineStarts: buildLineStarts(lines),   // 行起点数组（caretLineFast 二分）
    lineStates: lineStatesOf(lines, lang),  // 逐行起始跨行态（fix：块注释/跨行字符串承接行）
    lang,                     // 惰性高亮语言（工单 code-editor-opt/06）
    probeText, probeCols, probeIndex, text: viewText,
  };
  winLast = null;
  if (!winLineH) winLineH = winLineHeight();   // 行高仅首次 / codeWindowRefresh 重测（09：避免逐键 getComputedStyle）
}

// hlLineHtml(idx)：窗口行高亮（惰性——工单 code-editor-opt/06）——hl[idx] 为
// null（未算过）时按 winCache.lines[idx] 单行现算并回填；命中缓存零成本。
// 单行高亮带跨行态（lineStates[idx]——fix：多行 /* */ 注释 / 跨行字符串的
// 承接行不再被当普通代码着色）。
function hlLineHtml(idx) {
  let h = winCache.hl[idx];
  if (h == null) {
    const line = winCache.lines ? winCache.lines[idx] : "";
    const st = winCache.lineStates ? winCache.lineStates[idx] : null;
    h = '<span class="code-hl-line" data-code-line="' + (idx + 1) + '">'
      + highlightLineHTML(line, st, winCache.lang || "text") + "</span>";
    winCache.hl[idx] = h;
  }
  return h;
}

// lineStateEq(a, b)：跨行态浅比较（null 与 {…} 两种形态）。
function lineStateEq(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  return ka.length === kb.length && ka.every((k) => a[k] === b[k]);
}

// refreshLineStatesFrom(fromIdx)：编辑后重算 fromIdx 行**之后**各行的起始跨行
// 态——fromIdx 行自身的起始态由前面行决定，不受本行编辑影响；其后每行起始态
// = 上一行（新文本）的终止态。任一行的起始态变化 → 该行起所有惰性高亮缓存
// 作废（hl 置 null，重渲染现算），防止沿用旧配色。
function refreshLineStatesFrom(fromIdx) {
  if (!winCache || !winCache.lineStates || !winCache.lines) return;
  const n = winCache.lineCount;
  if (fromIdx >= n) return;
  const lang = winCache.lang;
  let changed = -1;
  for (let k = fromIdx; k < n - 1; k++) {
    const next = lineEndState(winCache.lines[k], winCache.lineStates[k], lang);
    const old = winCache.lineStates[k + 1];
    winCache.lineStates[k + 1] = next;
    if (changed < 0 && !lineStateEq(old, next)) changed = k + 1;
  }
  if (changed >= 0) {
    for (let k = changed; k < n; k++) winCache.hl[k] = null;
  }
}

// winPatchEdit(viewText, lang, span?)：逐行缓存增量修补（工单 11 性能整改——
// 5000 行文件逐键全量重高亮 + 全量 GC 是输入链主热点；窗口化只画窗口，但缓存
// 此前每次输入整体重建）。适用：非折叠态且行数不变（普通字符增删/替换不增删
// 行）。首尾比对找出变更行区间 → 只重算这些行的高亮与探针最长行；旧探针行
// 被改掉且新行没有更长 → 全量重扫探针（罕见路径）。span 可选（工单
// code-editor-opt/02）：非结构编辑 = 单行变更 → 免整文 split/首尾比对，直接按
// 变更行取新行文本重算高亮（热路径再省一次 6000 行 split + 数组比对）。折叠态
// （gutter 模型行号整体漂移）与行数变化仍走 winBuild 全量。
function winPatchEdit(viewText, lang, span) {
  if (span && !span.structural && winCache && winCache.text.length) {
    const idx = span.line - 1;
    if (idx >= 0 && idx < winCache.lineCount) {
      // 非结构单行变更：行结构不变 → 变更行起点 = 旧文本同位置（p 所在行行首）
      const oldText = winCache.text;
      const lineStart = oldText.lastIndexOf("\n", span.p - 1) + 1;
      const segStart = span.p - lineStart;
      const segEnd = segStart + span.oldSegLen;
      const nl = viewText.indexOf("\n", lineStart);
      const lineEnd = nl === -1 ? viewText.length : nl;
      const newLineText = viewText.slice(lineStart, lineEnd);
      // 行起点表同步（fix）：非结构单行编辑改变行长度 → 变更行之后所有行的
      // 绝对行起点整体平移 delta（行起点表必须与 lines 一致，否则下一次击键
      // editSpan.line / 窗口映射会落到下一行——用户现场：第 2 行连打字符错行反转）
      if (winCache.lines) {
        const oldLineLen = winCache.lines[idx].length;
        winCache.lines[idx] = newLineText;
        winCache.lineStarts = patchLineStarts(winCache.lineStarts, idx,
          newLineText.length - oldLineLen);
        // 跨行态同步（fix）：编辑可改变行内 /* \*/ 结构 → 其后行起始态重算
        refreshLineStatesFrom(idx);
      }
      // 变更行自身按（不变的）起始态重高亮——与整段渲染在行界闭合并重开等价
      const st = winCache.lineStates ? winCache.lineStates[idx] : null;
      winCache.hl[idx] = '<span class="code-hl-line" data-code-line="' + (idx + 1) + '">'
        + highlightLineHTML(newLineText, st, lang) + "</span>";
      let probeCols = winCache.probeCols;
      let probeText = winCache.probeText;
      let probeIndex = winCache.probeIndex;
      const col = newLineText.replace(/\t/g, "    ").length;
      if (winCache.probeIndex === idx && col <= winCache.probeCols) {
        // 旧最长行被改短且无人超越：全量重扫探针（罕见——普通输入不触发）
        let probeCols = 0; let probeText = ""; let probeIndex = -1;
        for (let i = 0; i < winCache.lineCount; i++) {
          const line = i === idx ? newLineText : (winCache.lines ? winCache.lines[i] : "");
          const c = line.replace(/\t/g, "    ").length;
          if (c > probeCols) { probeCols = c; probeText = line; probeIndex = i; }
        }
        winCache.probeCols = probeCols;
        winCache.probeText = probeText;
        winCache.probeIndex = probeIndex;
      } else if (col > winCache.probeCols) {
        // 新行成为最长行（插到长行/行长增长）
        winCache.probeCols = col;
        winCache.probeText = newLineText;
        winCache.probeIndex = idx;
      }
      winCache.text = viewText;
      winLast = null;
      return;
    }
  }
  const oldLines = winCache.text.split("\n");
  const newLines = viewText.split("\n");
  const n = newLines.length;
  let a = 0;
  while (a < n && oldLines[a] === newLines[a]) a++;
  let b = 0;
  while (b < n - a && oldLines[oldLines.length - 1 - b] === newLines[n - 1 - b]) b++;
  const start = a;
  const end = n - b;   // [start, end) 变更行
  if (start < end) {
    // 行数组先落位（跨行态重算与逐行高亮都以新文本为数据源）
    if (winCache.lines) {
      // 工单 code-editor-opt/02：行数组同步变更行（非结构编辑行数不变、行起点
      // 数组零维护——窗口切片/标记窗口文本/caretLineFast 全部复用）
      for (let i = start; i < end; i++) winCache.lines[i] = newLines[i];
      // 行起点表同步（fix）：多行替换可能改变各变更行长度，其后所有行起点
      // 绝对偏移随之漂移——行起点表必须与 lines 重建一致
      winCache.lineStarts = buildLineStarts(winCache.lines);
      // 跨行态同步（fix）：变更行可能改变注释/字符串结构 → 其后行起始态重算
      // （start 行的起始态不变；起始态变化的行 hl 置 null 由 refresh 负责）
      refreshLineStatesFrom(start);
    }
    // 逐行按（重算后的）起始态重高亮——与整段渲染在行界闭合并重开等价
    for (let i = start; i < end; i++) {
      const st = winCache.lineStates ? winCache.lineStates[i] : null;
      winCache.hl[i] = '<span class="code-hl-line" data-code-line="' + (i + 1) + '">'
        + highlightLineHTML(newLines[i], st, lang) + "</span>";
    }
    let probeCols = winCache.probeCols;
    let probeText = winCache.probeText;
    let probeIndex = winCache.probeIndex;
    const probeTouched = probeIndex >= start && probeIndex < end;
    for (let i = start; i < end; i++) {
      const col = newLines[i].replace(/\t/g, "    ").length;
      if (col > probeCols) { probeCols = col; probeText = newLines[i]; probeIndex = i; }
    }
    if (probeTouched && probeText === winCache.probeText && probeCols === winCache.probeCols) {
      // 旧最长行被改掉且无人超越：全量重扫（罕见——普通输入不触发）
      probeCols = 0; probeText = ""; probeIndex = -1;
      for (let i = 0; i < n; i++) {
        const col = newLines[i].replace(/\t/g, "    ").length;
        if (col > probeCols) { probeCols = col; probeText = newLines[i]; probeIndex = i; }
      }
    }
    winCache.probeCols = probeCols;
    winCache.probeText = probeText;
    winCache.probeIndex = probeIndex;
  }
  winCache.text = viewText;
  winLast = null;   // 内容已变：强制窗口重画（winRender 同窗早退保护）
}

// winPatchRow(span)：非结构单行编辑的行级 DOM 修补（工单 code-editor-opt/02）
// ——整窗 innerHTML 重建（hl/gutter/marks 各 ~50 行 + spacer）是逐键剩余大头；
// 单行变更时只替换该行的高亮/标记行元素：gutter 行号文本未变（非结构不增删
// 行、不改行首空白）零动；活跃标记 = marksCache（已增量修补）+ editorBracket
// 两段（已修补）。变更行不在当前窗口（光标不可见）→ false，调用方回退全量
// winRender。成功后维护 winLast（窗口未变，下一事件仍可零重建早退）。
function winPatchRow(span) {
  const box = paneBox();
  if (!box || !winCache || !winCache.lines) return false;
  if (!markClean || marksCache.content !== winCache.text) return false;  // 叠加态活跃/缓存陈旧 → 全量
  const hl = box.querySelector(".code-hl");
  const gutter = box.querySelector(".code-gutter");
  const marksEl = box.querySelector(".code-marks");
  if (!hl || !marksEl) return false;
  const idx = span.line - 1;
  if (idx < 0 || idx >= winCache.lineCount) return false;
  const r = winLast || winWindow();
  if (idx < r.start || idx >= r.end) {
    // 变更行在窗口外：非结构编辑不增删行、不改行首空白 → 可见行与绝对位置
    // 全部不变，零 DOM（整窗 innerHTML 重建此前是纯浪费；工单 code-editor-opt/02）
    winLast = r;
    return true;
  }
  const lineNo = idx + 1;
  const hlRow = hl.querySelector('.code-hl-line[data-code-line="' + lineNo + '"]');
  const marksRow = marksEl.querySelector('.code-marks-line[data-code-line="' + lineNo + '"]');
  const gutRow = gutter ? gutter.querySelector('.code-gutter-line[data-code-line="' + lineNo + '"]') : null;
  if (!hlRow || !marksRow || !gutRow) return false;
  hlRow.innerHTML = hlLineHtml(idx);
  // 标记行：marksCache（+ editorBracket 两段）按变更行过滤、行号重基准为 1
  const allMarks = marksCache.marks || [];
  const lineMarks = [];
  for (const m of allMarks) {
    if (m.line === lineNo) {
      lineMarks.push({ line: 1, start: m.start, end: m.end, kind: m.kind, title: m.title });
    }
  }
  if (editorBracket) {
    for (const m of [editorBracket.open, editorBracket.close]) {
      if (m && m.line === lineNo) {
        lineMarks.push({ line: 1, start: m.start, end: m.end, kind: "bracket" });
      }
    }
  }
  const lineText = winCache.lines[idx];
  marksRow.innerHTML = codeMarksHTML(lineText, lineMarks);
  winLast = r;
  return true;
}

function winSpacer(px) {
  return px > 0 ? `<div class="code-window-spacer" style="height:${px}px"></div>` : "";
}

function winWindow() {
  if (!winCache) return { start: 0, end: 0 };
  return codeWindowRange(winView.scrollTop, winView.viewportH, winLineH,
    winCache.lineCount, WIN_OVERSCAN);
}

// ===== textarea 窗口化（工单 editor-textarea-viewport/02 + 04 三层组合）=====
// textarea 只装当前窗口 [start,end) 文本（01 纯件构建），盒高 = 视口高并
// 贴内容坐标（top = start*行高；向下延伸覆盖全视口——textarea 必须盖满
// 视口，否则点击/选区在 overscan 不覆盖区落空）。taWinInfo 记录当前窗口
// 对象（窗口编辑回写/光标映射共用）。折叠态（viewModel 非空，04 打通三层）
// 同样窗口化：winCache.lines = 视图行数组，窗口文本 = 视图切片（占位行按
// 既有折叠渲染语义在窗口内呈现），absStart = 视图偏移——模型→视图→窗口
// 三环映射链自然成立；本组函数不再对折叠态早退。

// taCaretViewPos()：当前 textarea 选区 → 视图绝对偏移（窗口化 = 窗口起点 +
// 窗口内偏移——windowPosToView 单源；折叠/全量 = 原偏移）。
function taCaretViewPos() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return 0;
  const sel = Math.max(0, ta.selectionStart | 0);
  return taWinInfo ? windowPosToView(taWinInfo, sel) : sel;
}

// taApplyWindowStyle(wi)：按窗口对象（仅用 start）贴内容坐标（top = 窗口
// 起点 * 行高）+ 向下延伸盖满视口（overscan 上缘随 scrollTop 连续变化）——
// taFillWindow 与 taWindowSync 同窗分支共用（02 评审整改：几何写一次）。
function taApplyWindowStyle(wi) {
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  if (!ta) return;
  const topPx = Math.round(wi.start * winLineH * 100) / 100;
  const cover = Math.max(0, (winView.scrollTop | 0) - topPx);   // overscan 上缘
  ta.style.top = topPx + "px";
  ta.style.height = Math.ceil((box ? box.clientHeight : 0) + cover) + "px";
}

// taFillWindow(wi, rel)：窗口对象 + 窗口内选区偏移 → 装进 textarea（值/
// 几何/选区一次落位；taWinInfo 同步）。
function taFillWindow(wi, rel) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  ta.value = wi.text;
  taWinInfo = wi;
  taWinDirty = false;
  taApplyWindowStyle(wi);
  ta.setSelectionRange(Math.max(0, Math.min(wi.text.length, rel | 0)),
    Math.max(0, Math.min(wi.text.length, rel | 0)));
  setActiveLine(caretLineFast(taCaretViewPos()));
}

// taWindowApply(caretView, follow?)：把 textarea 重装为「含光标」的窗口文本
// ——打开/输入回写/跳转/重载后调用。**视图坐标**：非折叠 模型=视图；折叠态
// （04 三层组合）调用方先 codeFoldModelToView 换算视图偏移。光标在窗口外 →
// 先滚动使其可见（居中）再重算窗口（跳转语义：光标始终在窗口内，后续输入
// 不落不可见处）。follow=false（IME compositionend 场景）：不滚动回光标——
// 组合期间用户可能已滚动，光标按窗口边缘钳制（视口不被强行拉回）。
function taWindowApply(caretView, follow = true) {
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  if (!box || !ta || !winCache) return;
  const m = Math.max(0, caretView == null ? 0 : caretView | 0);
  let r = winLast || winWindow();
  let wi = windowTextBuild(winCache.lines, r.start, r.end, winCache.lineStarts);
  let rel = windowPosFromView(wi, m);
  if (rel == null && follow) {
    const line = Math.max(1, caretLineFromStarts(winCache.lineStarts, m));
    box.scrollTop = Math.max(0, (line - 1) * winLineH - Math.floor((box.clientHeight || 0) / 2));
    winReadView();
    winRender();
    r = winLast || winWindow();
    wi = windowTextBuild(winCache.lines, r.start, r.end, winCache.lineStarts);
    rel = windowPosFromView(wi, m);
  }
  if (rel == null) {
    // 防御钳制（follow=true 时理论不可达——已按光标行重算窗口；follow=false
    // 时即「光标随视口走」的窗口边缘语义）
    rel = m < wi.absStart ? 0 : wi.text.length;
  }
  taFillWindow(wi, rel);
}

// rebuildWindowKeepCaret()：映射失配/内容漂移兜底——以模型为准重建窗口文本，
// 光标按旧选区（窗口→视图）落位，不静默错位（spec：宁可重装，不可错位）。
// syncEditorAfterInput 三处兜底共用（02 非折叠两处 + 04 折叠窗口化一处）。
function rebuildWindowKeepCaret() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  const cur = windowPosToView(taWinInfo, ta ? ta.selectionStart : 0);
  taWinInfo = null;
  taWindowApply(cur);
}

// taWindowSync()：滚动/尺寸变化后的窗口同步——仅窗口行区间变化时重装文本
// （同窗只更新 top/height 覆盖全视口，顶部 overscan 随滚动连续增减）；窗口
// 变化时选区按旧窗口文档位置换算（滚出窗口 = 钳到窗口边缘——光标随视口走，
// 输入永不静默落在不可见处）。折叠态（04 三层组合）：winCache.lines = 视图行
// 数组，窗口文本 = 视图切片（占位行经既有折叠渲染语义在窗口内呈现），
// absStart = 视图偏移——三环映射链 模型→视图→窗口 自然成立。IME 组合中不
// 重装（打断候选窗），由 taWinDirty 标记、compositionend 后补。
function taWindowSync() {
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  if (!box || !ta || !winCache) return;
  const r = winLast || winWindow();
  const changed = !taWinInfo || taWinInfo.start !== r.start || taWinInfo.end !== r.end;
  if (changed && !composing && !taWinDirty) {
    const wi = windowTextBuild(winCache.lines, r.start, r.end, winCache.lineStarts);
    const oldSel = taWinInfo ? Math.max(0, ta.selectionStart | 0) : 0;
    const oldView = taWinInfo ? windowPosToView(taWinInfo, oldSel) : 0;
    let rel = windowPosFromView(wi, oldView);
    if (rel == null) rel = oldView < wi.absStart ? 0 : wi.text.length;
    taFillWindow(wi, rel);
  } else {
    taApplyWindowStyle(r);
  }
}

// taSetRange(viewStart, viewEnd)：按视图（非折叠 = 模型）绝对偏移设置
// textarea 选区——窗口化时先确保窗口包含区间（taWindowApply 以起点重装），
// 再换算窗口偏移；折叠/全量态直接 setSelectionRange。
function taSetRange(viewStart, viewEnd) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  const s = Math.max(0, viewStart | 0);
  const e = Math.max(s, viewEnd | 0);
  if (taWinInfo) {
    let ws = windowPosFromView(taWinInfo, s);
    let we = windowPosFromView(taWinInfo, e);
    if (ws == null || we == null) {
      taWindowApply(s);
      ws = windowPosFromView(taWinInfo, s);
      we = windowPosFromView(taWinInfo, e);
    }
    if (ws == null || we == null) return;   // 防御：重装后仍越界 → 不静默设错
    ta.setSelectionRange(ws, Math.max(ws, Math.min(we, taWinInfo.text.length)));
    return;
  }
  ta.setSelectionRange(s, e);
}

// editSource()：程序化编辑（Tab/Enter/行操作/注释/括号）的数据源——
// 非折叠窗口化态 = 模型全文 + 模型选区（textarea 只装窗口文本，纯件必须基于
// 模型算，选区经 windowPosToView 单源换算）；折叠窗口化态（04 三层组合）=
// **视图全文** + 视图选区（窗口→视图换算后超集——程序化编辑须保持 07 既有
// 全视图语义：Alt+↑↓ 移动行/Ctrl+A 全选等不能把窗口边界当文档边界；ApplyEdit
// 折叠分支经 codeFoldMapEdit 视图→模型回写）；折叠/全量非窗口态 = textarea 值
// + 选区（既有语义）。返回 {text, selStart, selEnd}。
function editSource() {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  const tab = getActiveTab();
  if (ta && taWinInfo && tab && !viewModel) {
    return {
      text: tab.content,
      selStart: windowPosToView(taWinInfo, ta.selectionStart),
      selEnd: windowPosToView(taWinInfo, ta.selectionEnd),
    };
  }
  if (ta && taWinInfo && tab && viewModel) {
    return {
      text: viewModel.text,
      selStart: windowPosToView(taWinInfo, ta.selectionStart),
      selEnd: windowPosToView(taWinInfo, ta.selectionEnd),
    };
  }
  return {
    text: ta ? ta.value : "",
    selStart: ta ? Math.max(0, ta.selectionStart | 0) : 0,
    selEnd: ta ? Math.max(0, ta.selectionEnd | 0) : 0,
  };
}

// winRenderMarks()：标记层窗口化重画（查找命中/选中词/括号/缩进引导线按
// 窗口行过滤重基准——行内偏移不变）。上下 spacer 与 hl/gutter 层同高度
// ——标记层绝对定位在 .code-edit 顶部，缺 spacer 时滚动后整层y 向错位
// （引导线压到错误行/穿过代码文字，用户反馈错位的根因；scrollTop=0 时
// 恰好对齐，此前冒烟只测顶部窗口未暴露）。
function winRenderMarks() {
  const box = paneBox();
  const marksEl = box && box.querySelector(".code-marks");
  if (!marksEl || !winCache) return;
  const tab = getActiveTab();
  const r = winLast || winWindow();
  const viewText = viewModel ? viewModel.text : (tab ? tab.content : "");
  const errLines = tab ? compileErrorLinesForFile(getCompileErrors(), tab.path) : [];  // 一次映射，标记层与 gutter 共用（评审整改）
  // 工单 11：纯字符编辑（markClean）且非折叠态 → 模型级标记缓存直接复用
  //（currentMarks 全量重算 = 缩进引导线 + 括号深度扫描，逐键热点之一）。
  let marks;
  if (!viewModel && marksCache.content === viewText) {
    // 工单 code-editor-opt/02：静态层缓存（引导线/彩虹）已按内容引用增量修补
    // → 无论 markClean 与否都复用（词/查找/错误等状态标记独立于缓存、随状态
    // 追加）；markClean 仅决定行级修补是否可用（其渲染含括号对两段）。
    // 工单 code-editor-opt/05：状态标记单次拼接——不再逐类 concat 复制整份
    // 2000+ 条静态清单（4 次 concat = 4 次全量复制 + 临时数组，GC 主源）。
    const extra = [];
    if (editorBracket) {
      extra.push(
        { line: editorBracket.open.line, start: editorBracket.open.start,
          end: editorBracket.open.end, kind: "bracket" },
        { line: editorBracket.close.line, start: editorBracket.close.start,
          end: editorBracket.close.end, kind: "bracket" },
      );
    }
    if (editorWord.word && editorWord.ranges.length) {
      for (const w of editorWord.ranges) {
        extra.push({ line: w.line, start: w.start, end: w.end, kind: "word" });
      }
    }
    if (editorFind.query && editorFind.ranges.length) {
      editorFind.ranges.forEach((x, i) => {
        extra.push({ line: x.line, start: x.start, end: x.end,
          kind: i === editorFind.index ? "current" : "hit" });
      });
    }
    for (const er of errLines || []) {
      const ln = (winCache.lines && winCache.lines[er.line - 1] != null
        ? winCache.lines[er.line - 1].length : 0);
      extra.push({ line: er.line, start: 0, end: ln, kind: "error", title: er.message });
    }
    marks = extra.length ? marksCache.marks.concat(extra) : marksCache.marks;
  } else if (viewModel) {
    marks = marksForView(errLines);
  } else {
    marks = currentMarks(errLines);
    marksCache = { content: viewText, marks };
  }
  const lines = (winCache && winCache.lines) || viewText.split("\n");
  const windowText = lines.slice(r.start, r.end).join("\n");
  const windowMarks = [];
  for (const m of marks) {
    const li = m.line - 1;
    if (li >= r.start && li < r.end) {
      windowMarks.push({ line: li - r.start + 1, start: m.start, end: m.end, kind: m.kind, title: m.title });
    }
  }
  const topH = Math.round(r.start * winLineH * 100) / 100;
  const bottomH = Math.round((winCache.lineCount - r.end) * winLineH * 100) / 100;
  marksEl.innerHTML = winSpacer(topH) + codeMarksHTML(windowText, windowMarks) + winSpacer(bottomH);
  winRenderGutterErrors(errLines);   // 行号色点与标记层同一次窗口化重画（工单 05）
}

// winRenderGutterErrors(errLines)：编译错误行号色点（工单 code-editor-refine/05）
// ——errLines = winRenderMarks 预计算的当前文件错误行（[{line,message}]），按
// 模型行号 toggle .code-err-line（红字 + ● 点 + title=消息；dataset.errTitle
// 守卫：只清自己设过的 title，不动折叠行的「展开/折叠」提示）；占位行
// （.code-gutter-ph）不标（无真实行语意）。
function winRenderGutterErrors(errLines) {
  const box = paneBox();
  const gutter = box && box.querySelector(".code-gutter");
  if (!gutter) return;
  const msgByLine = new Map((errLines || []).map((e) => [e.line, e.message]));
  gutter.querySelectorAll(".code-gutter-line").forEach((el) => {
    if (el.classList.contains("code-gutter-ph")) return;
    const n = Number(el.dataset.codeLine);
    const msg = msgByLine.get(n);
    if (msg) {
      el.classList.add("code-err-line");
      el.title = msg;
      el.dataset.errTitle = "1";
    } else if (el.classList.contains("code-err-line")) {
      el.classList.remove("code-err-line");
      if (el.dataset.errTitle) {
        el.removeAttribute("title");
        delete el.dataset.errTitle;
      }
    }
  });
}

// winApplySize()：.code-edit 显式尺寸 = 全量内容（行高*行数 + 上下 padding
// 16px；宽度 = 最长行实测宽 + 左右 padding 36px——mono 精确、CJK 兜底）。
// 工单 09 缓存：行数/行高/最长列数未变 → 不写样式不测量；列数增长按上次
// 实测 ch 宽估算（无 DOM 读）；仅首次 build 探针实测一次——大文件逐键输入
// 零强制布局（实测一次强制布局 ≈ 50-60ms）。
function winApplySize() {
  const box = paneBox();
  const edit = box && box.querySelector(".code-edit");
  if (!edit || !winCache) return;
  if (!winSize || winSize.lineCount !== winCache.lineCount
    || winSize.lineH !== winLineH) {
    edit.style.height = Math.ceil(16 + winCache.lineCount * winLineH) + "px";
    winSize = { lineCount: winCache.lineCount, lineH: winLineH, cols: -1, chW: 8 };
  }
  if (winSize.cols < 0) {
    // 首次：探测最长行实测宽（工单 code-editor-opt/06：测量元素脱离文档流
    // 固定定位——在 6000 行高的滚动容器里 getBoundingClientRect 会触发整树
    // 深布局（实测打开延迟大头之一）；固定单行 span 的测量只排版它自己，
    // 字体/字号/字重从 .code-hl 计算样式拷贝（等宽 mono，宽度精确））
    const hlEl = box.querySelector(".code-hl");
    const cs = hlEl ? getComputedStyle(hlEl) : null;
    const font = cs
      ? cs.fontFamily + ";" + cs.fontSize + ";" + cs.fontWeight
      : 'monospace;13px;400';
    let w = 0;
    let chW = winSize.chW;
    const probeText = winCache.probeText || "";
    if (probeText) {
      const m = document.createElement("span");
      m.style.cssText = "position:fixed;left:-9999px;top:0;visibility:hidden;white-space:pre;"
        + "font:" + font;
      document.body.appendChild(m);
      m.textContent = probeText;
      w = m.getBoundingClientRect().width;
      m.remove();
      if (w > 0) {
        chW = Math.max(1, w / Math.max(1, winCache.probeCols));
        edit.style.width = Math.ceil(w + 36) + "px";
      }
    }
    winSize = { ...winSize, cols: winCache.probeCols, chW };
    return;
  }
  if (winCache.probeCols > winSize.cols) {
    // 列数增长：按 ch 宽估算加宽（无 DOM 读——避免强制布局）
    const dw = (winCache.probeCols - winSize.cols) * winSize.chW;
    edit.style.width = Math.ceil(parseFloat(edit.style.width || "0") + dw) + "px";
    winSize = { ...winSize, cols: winCache.probeCols };
  }
}

// winRender()：按当前滚动窗口重画三层（窗口未变 → 零 DOM 直接返回；跨窗口
// 才切片重建），最后重挂当前行高亮（元素已重建）。
function winRender() {
  const box = paneBox();
  if (!box || !winCache) return;
  const hl = box.querySelector(".code-hl");
  const gutter = box.querySelector(".code-gutter");
  if (!hl || !gutter) return;
  // 自愈（用户现场修复）：gutter 与 hl 行数不一致 → 渲染前补齐平铺行号，
  // 保证切片后行号/高亮 1:1（窗口端错位/无行号段落彻底消除）。
  if (winCache.gutter.length !== winCache.lineCount) {
    const plain = winCache.text.split("\n").map((_, i) => codeGutterLineHTML(i + 1));
    for (let i = 0; i < winCache.lineCount; i++) {
      if (winCache.gutter[i] == null) winCache.gutter[i] = plain[i];
    }
    winCache.gutter.length = winCache.lineCount;
  }
  const r = winWindow();
  if (winLast && winLast.start === r.start && winLast.end === r.end
    && winLast.lineCount === winCache.lineCount) return;
  winLast = { start: r.start, end: r.end, lineCount: winCache.lineCount };
  const topH = Math.round(r.start * winLineH * 100) / 100;
  const bottomH = Math.round((winCache.lineCount - r.end) * winLineH * 100) / 100;
  const top = winSpacer(topH);
  const bottom = winSpacer(bottomH);
  hl.innerHTML = top + winCache.hl.slice(r.start, r.end)
    .map((_, i) => hlLineHtml(r.start + i)).join("") + bottom;
  gutter.innerHTML = top + winCache.gutter.slice(r.start, r.end).join("") + bottom;
  winRenderMarks();
  const ta = box.querySelector(".code-ta");
  if (ta) setActiveLine(caretLineFast(taCaretViewPos()));
}

// codeWindowRefresh()：缩放/布局变化后强制重测行高并重画窗口（codeview 的
// applyCodeZoom 调用）。
export function codeWindowRefresh() {
  winLineH = 0;      // 行高失效 → winBuild 重测
  winLineH = winLineHeight();
  winLast = null;
  winSize = null;    // 尺寸缓存失效（缩放后重测宽度）
  winReadView();
  winApplySize();
  winRender();
  taWindowSync();    // 视口/行高变化 → textarea 窗口与覆盖高度同步
}

function renderPane() {
  markClean = false;   // 工单 11：换 tab/重渲染 → 标记缓存失效
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
  // 滚动窗口化（工单 08）：hl/marks 留空壳（windowed），内容经 winBuild +
  // winApplySize + winRender 只画窗口行；.code-edit 尺寸显式 = 全量。
  const src = viewModel ? viewModel.text : tab.content;
  box.innerHTML = '<div class="code-gutter" aria-hidden="true"></div>'
    + codeEditorHTML(src, tab.lang, {
      readonly: tab.readonly,
      // 工单 code-editor-opt/06：windowed 模式 codeEditorHTML 不消费 marks
      // （hl/marks 留空壳，由 winRender 窗口化渲染）——不再预计算
      // currentMarks/marksForView（6000 行打开时白扫一次全库标记，实测占
      // 打开延迟大头之一；marksCache 由随后 winRenderMarks 正常构建）
      marks: [],
      windowed: true,
      // 工单 editor-textarea-viewport/02 + 04：textarea 一律不内嵌全文/视图
      // 全量（6000 行 108KB 标记是打开渲染大头），由下方 taWindowApply 装
      // 窗口文本——折叠态（04 三层组合）装「视图切片」而非视图全量。
      taValue: "",
    })
    + '<span class="code-window-probe" aria-hidden="true"></span>';
  winBuild(src, tab.lang);
  winReadView();
  winApplySize();
  winRender();
  taWinInfo = null;      // 重建后旧窗口对象失效（winCache 引用已换）
  taWindowApply(0);      // 打开/切换：窗口 [0,*) + 光标文档头
  // 打开/切换即算折叠区（工单 11 后补：无结构输入前 folds=[] 会导致
  // Ctrl+Shift+[/] 与折叠箭头不可用；渲染层不需要，快捷键/箭头语义需要）
  if (!viewModel) folds = codeFoldRanges(tab.content, tab.lang);
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
  resetUndoStack();   // 03：换 tab → 撤销栈清空（快照模型级，跨 tab 必错）
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
  resetUndoStack();   // 03：关标签 → 撤销栈清空（防错撤到新活动 tab）
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
  // 折叠态（用户现场修复）：textarea/高亮层用视图行号，gutter 用模型行号——
  // 直接拿视图号查 gutter 会把 active 挂到模型号恰等于视图号的行（折叠 N 行
  // 即错位 N 行，「光标与高亮行错位」根因）。此处做视图 → 模型映射：
  // hl/pre 用视图号；gutter 用对应真实行的模型行号（占位行不高亮）。
  let gutLine = line;
  if (viewModel && line >= 1 && line <= (viewModel.lines || []).length) {
    const v = viewModel.lines[line - 1];
    if (v && !v.placeholder) gutLine = v.no;
  }
  const gut = box.querySelector('.code-gutter-line[data-code-line="' + gutLine + '"]');
  const hl = box.querySelector('.code-hl-line[data-code-line="' + line + '"]');
  const pre = box.querySelector('.code-pre-line[data-code-line="' + line + '"]');
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
  let el = box.querySelector('.code-hl-line[data-code-line="' + target + '"]')
    || box.querySelector('.code-pre-line[data-code-line="' + target + '"]');
  if (!el && winCache) {
    // 滚动窗口化（工单 08）：目标行不在窗口内 → 先滚到目标附近并同步渲染
    // 窗口，再定位元素（后续 scroll 事件同窗跳过，flash 不被重建冲掉）。
    box.scrollTop = Math.max(0, (target - 1) * winLineH
      - Math.floor(box.clientHeight / 2));
    winReadView();
    winRender();
    el = box.querySelector('.code-hl-line[data-code-line="' + target + '"]')
      || box.querySelector('.code-pre-line[data-code-line="' + target + '"]');
  }
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  winReadView();   // 跳转后按真实滚动回读（scrollIntoView 的居中修正不会触发
                    // 同步滚动事件——不补读会在下次渲染用陈旧窗口造成层错位）
  winRender();
  taWindowSync();  // 窗口行区间变化 → textarea 窗口文本/覆盖高度同步（02）
  setActiveLine(target);
  flashEl(el);
  const ta = box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    const range = editorLineRange(tab.content, line);
    if (range) {
      const start = viewModel ? codeFoldModelToView(viewModel.segs, range.start) : range.start;
      const end = viewModel ? codeFoldModelToView(viewModel.segs, range.end) : range.end;
      ta.focus();
      taSetRange(start, end);
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
    applySavedState(tab, resp, undefined, true);   // 手工保存（Ctrl+S/保存按钮；工单 10 自动编译判据）
  } catch (e) {
    if (e.status === 409) {
      showConflictModal(tab, true);   // 冲突「覆盖写盘」= 用户显式确认的保存（工单 10 判据；评审整改）
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
async function saveTabSettled(tab, manual) {
  try {
    const resp = await postSave(tab);
    applySavedState(tab, resp, undefined, manual);
    return "saved";
  } catch (e) {
    if (e.status === 409) {
      const outcome = await showConflictModal(tab, manual);
      return outcome === "overwrite" ? "saved" : outcome;
    }
    toastError(e, "保存失败");
    return "cancel";
  }
}

// saveAllDirtyTabs(manual?)：保存全部脏且非只读标签（只读 / 非脏跳过，
// 零请求）；任一取消（冲突取消 / 保存失败）→ 立即返回
// {ok:false, canceled:true} 并停止（不再保存其余标签，编译应中止）；
// 全部落定 → {ok:true, canceled:false}。目录切换保护：保存期间目录变了 →
// 中止（防写错位置——与冲突模态失效处理同因）。manual = 用户显式保存（「保存
// 全部」按钮/Ctrl+Shift+S 传 true；编译前自动落盘/守卫保存缺省 false——工单
// 10 自动编译只认手工，见 onFileSaved 注释）。
export async function saveAllDirtyTabs(manual) {
  const baseDir = codeDir;
  for (const tab of dirtySavableTabs(tabs)) {
    if (codeDir !== baseDir) return { ok: false, canceled: true };
    const outcome = await saveTabSettled(tab, manual);
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

function showConflictModal(tab, manual) {
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
            applySavedState(tab, resp, "已保存 " + tab.path + "（覆盖了外部修改）", manual);
            resolve("overwrite");
          } catch (e2) {
            if (e2.status === 409) {
              // 覆盖时隙间又被改：旧模态已关，重新弹（冲突再演，用户再定夺）
              resolve(await showConflictModal(tab, manual));
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
function applySavedState(tab, resp, msg, manual) {
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
  notifySaved(tab, resp, manual);   // manual = 手工保存标记（工单 10：自动编译只认手工）
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
  resetUndoStack();   // 03：磁盘版整体替换 → 撤销栈清空（非用户编辑）
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

// ---- 撤销栈全域化（工单 editor-textarea-viewport/03）----
// 视口化后 textarea 只装窗口文本，浏览器原生撤销栈只认「textarea=全量文本」
// 的旧世界（窗口内撤销必错乱、跨窗口无意义）——明确放弃原生栈，快照栈全域
// 接管（spec：大文档直赋值 + 快照栈既有先例，风险已知可控）。快照 = 模型级
// {value, selStart, selEnd}（模型全文 + 模型选区偏移）——与窗口文本无关，
// 跨窗口/折叠态语义由「模型为唯一事实源」保证。栈状态机 = fx/undo-stack 纯件
// （上限 200、新编辑清空 redo）；本侧只做快照捕获与模型恢复。
let undoStack = [];
let redoStack = [];
let pendingSnapshot = null;    // beforeinput/compositionstart 捕获的「编辑前快照」
let compositionPushed = false; // 组合输入已入栈（一次组合 = 一步撤销）

// captureModelSnapshot()：当前模型状态快照（模型全文 + 模型选区）——textarea
// 只装窗口文本，选区经 editorSelectionModel 单源换算为模型偏移；无选区时取
// 光标模型偏移。无活动标签 → null。
function captureModelSnapshot() {
  const tab = getActiveTab();
  if (!tab) return null;
  const sel = editorSelectionModel();
  const s = sel ? sel.start : foldCaretModelPos();
  const e = sel ? sel.end : s;
  return { value: tab.content, selStart: s, selEnd: e };
}

// pushEditSnapshot(snap?)：快照入栈（栈状态机 = fx/undo-stack）——新编辑清空
// redo、上限 200。snap 缺省 = 当前模型状态捕获；编辑前调用即「编辑前快照」。
function pushEditSnapshot(snap) {
  const s = snap || captureModelSnapshot();
  if (!s) return;
  const r = undoPush(undoStack, redoStack, s);
  undoStack = r.undo;
  redoStack = r.redo;
}

// clearTypingSnapshot()：丢弃已捕获但未入栈的编辑前快照态（输入未产生真实
// 变更时调用——不产生撤销步；resetUndoStack 亦走此清空）。
function clearTypingSnapshot() {
  pendingSnapshot = null;
  compositionPushed = false;
}

// pushTypingSnapshot()：手打输入（input 事件）的入栈入口——必须在真实模型
// 变更**前**调用（此时 tab.content 仍是旧模型 = 编辑前状态）。beforeinput 已
// 捕获编辑前快照 → 直接入栈；组合输入：只认 compositionstart 那次快照（一次
// 组合 = 一步撤销，组合中中间态不单列入栈）；compositionend 收尾变更并入同一
// 撤销步；无 beforeinput 的合成输入兜底 = 当前状态捕获（不影响模型正确性）。
function pushTypingSnapshot() {
  if (composing) {
    if (pendingSnapshot) {
      pushEditSnapshot(pendingSnapshot);
      pendingSnapshot = null;
      compositionPushed = true;
    }
    return;
  }
  if (compositionPushed) {
    // compositionend 收尾变更：并入组合撤销步，不另开一步
    compositionPushed = false;
    return;
  }
  const snap = pendingSnapshot || captureModelSnapshot();
  pendingSnapshot = null;
  if (snap) pushEditSnapshot(snap);
}

// snapshotUndo(redo)：撤销/重做一步——fx 状态机弹栈并把当前状态推入对侧，
// 然后 rebaseModelContent 以模型快照重建（含折叠态：折叠区按签名保留、视图/
// 窗口重装、光标按模型落位），并按快照恢复**模型选区**（selStart..selEnd——
// 与既有「撤销恢复选区」语义一致，非只回光标）；随后刷新标签条脏点、状态栏
// 与查找/词/括号标记。返回是否成步（空栈 / 只读 / 无活动标签 → false）。
function snapshotUndo(redo) {
  const tab = getActiveTab();
  if (!tab || tab.readonly) return false;
  const cur = captureModelSnapshot();
  if (!cur) return false;
  const r = redo ? redoStep(undoStack, redoStack, cur)
    : undoStep(undoStack, redoStack, cur);
  if (!r) return false;
  undoStack = r.undo;
  redoStack = r.redo;
  const ml = tab.content.length;
  const ms = Math.max(0, Math.min(ml, r.snap.selStart | 0));
  const me = Math.max(ms, Math.min(ml, r.snap.selEnd | 0));
  rebaseModelContent(r.snap.value, ms);
  // 恢复快照的模型选区（折叠态经视图映射回窗口落位；taSetRange 单源换算）
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    ta.focus();
    let vs = ms;
    let ve = me;
    if (viewModel) {
      vs = codeFoldModelToView(viewModel.segs, ms);
      ve = codeFoldModelToView(viewModel.segs, me);
    }
    taSetRange(vs, ve);
  }
  renderTabs();            // 脏点随内容变化刷新（rebase 不经 syncTail）
  notifyActive();          // 状态栏信息区随内容/光标刷新
  renderEditorMarks();     // 查找/词/括号随模型内容刷新（rebase 不经 syncTail）
  scheduleCursorWork();    // 选中词/括号/状态栏按恢复后的光标重算
  return true;
}

// resetUndoStack()：内容上下文整体切换（换 tab/关 tab/切目录/磁盘重载）后清空
// 撤销栈——快照是模型级，跨「同一 textarea 复用不同 tab」语义必错；与原生栈
// 随 textarea 重建而清空的既有行为对齐。
function resetUndoStack() {
  undoStack = [];
  redoStack = [];
  clearTypingSnapshot();
}

// applyCachePatches(oldText, newText, span)：模型内容变更后的折叠清单与静态
// 标记缓存增量修补（非折叠共用段——手输 sync 窗口化路径与程序化 applyEdit
// 同口径：结构变更 → 折叠清单重算 + 配对清单失效；非结构 → 引导线/彩虹/配对
// 清单按变更段平移，markClean 按叠加态判定）。
function applyCachePatches(oldText, newText, span) {
  if (span && span.identical) return;
  if (span.structural) {
    // 结构变更（换行/括号/引号/#/tab/行首空白）：折叠清单须重算
    // （无折叠态也随输入重算折叠区清单——工单 07：快捷键/箭头基于最新内容）
    const tab = getActiveTab();
    folds = codeFoldRanges(tab ? tab.content : newText, tab ? tab.lang : "");
    pairScanCache = { content: null, entries: [] };   // 配对清单失效（下次全量重扫）
    return;
  }
  // 工单 11：纯字符编辑 → 折叠清单（行号/括号位未变）与标记集不变；
  // 无查找/词/错误叠加态时标记层可整体沿用（markClean——括号对状态经
  // editorBracket 增量修补并随缓存渲染，不再把「配对高亮活跃」排除在外）
  markClean = !editorFind.query && !editorWord.word
    && !getCompileErrors().length;
  // 工单 code-editor-opt/05：静态缓存（引导线/彩虹）修补**不**依赖
  // markClean——词/查找/错误活跃时同样增量（它们只关行级修补是否可用）；
  // 否则回删/词活跃的每次输入都会触发全库 bracketDepthMarks 扫描
  if (oldText !== null && marksCache.content === oldText
    && bracketRainbowCache.content === oldText
    && indentGuideCache.content === oldText) {
    const patched = marksPatch(marksCache.marks, oldText, newText, span);
    const parts = marksPartition(patched);
    marksCache = { content: newText, marks: parts.all };
    bracketRainbowCache = { content: newText, marks: parts.rainbow };
    indentGuideCache = { content: newText, marks: parts.guides };
  } else {
    // 缓存缺失/陈旧（内容引用对不上）：保守走全量
    // （winRenderMarks → currentMarks 会重建 marksCache）
    markClean = false;
  }
  // 工单 code-editor-opt/02：配对扫描清单总是增量（非结构不碰括号，条目按
  // 绝对/行内偏移平移；内容引用失配 → 置空，updateBracketMarks 全量重扫一次）
  if (oldText !== null && pairScanCache.content === oldText) {
    pairScanCache = {
      content: newText,
      entries: pairScanPatch(pairScanCache.entries, oldText, newText, span),
    };
  } else {
    pairScanCache = { content: null, entries: [] };
  }
  // 括号对高亮状态增量修补（行号不变，列偏移按插入/删除平移）
  patchEditorBracket(span);
}

// syncTail(caretModel, follow?)：syncEditorAfterInput / applyEdit 的共享尾段——
// 标记状态先行 → 逐行缓存重建/窗口渲染 → 尺寸 → 光标与窗口重装 → 脏点与状态栏。
// 窗口化态传 caretModel（模型光标，taWindowApply 重装窗口并落位）；follow 透传
// （false = compositionend 不把视口拉回光标——用户组合期间可能已滚动）。其余态
// 读 textarea 当前选区（IME 组合中不做选区回写）。
function syncTail(caretModel, follow = true) {
  const box = paneBox();
  const ta = box && box.querySelector(".code-ta");
  const tab = getActiveTab();
  if (!box || !ta || !winCache) return;
  const selStart = ta.selectionStart;
  const selEnd = ta.selectionEnd;
  // 标记状态先算：行级修补/窗口重画要用最终的 editorBracket/editorWord
  //（词/括号状态随内容/光标变化，先算后渲染——与 refreshMarkSetters 的
  // 「状态先行」纪律一致）；随后复核 markClean：词/查找/错误叠加态出现 →
  // 行级修补不可用（其渲染不含词/查找/错误标记），走全量窗口重画
  updateWordMarks();
  updateBracketMarks();
  if (editorWord.word || editorFind.query || getCompileErrors().length) {
    markClean = false;
  }
  // 工单 code-editor-opt/05：查找命中区段在窗口渲染**前**重算（渲染单点化——
  // 此前渲染后 renderEditorMarks 再全量重画一次；现在 winRenderMarks 直接用
  // 最新区段，同步尾不再二次渲染）
  if (editorFind.query) {
    editorFind.ranges = codeFindRanges(tab.content, editorFind.query);
    if (!editorFind.ranges.length) editorFind.index = -1;
    else if (editorFind.index < 0 || editorFind.index >= editorFind.ranges.length) {
      editorFind.index = 0;
    }
  }
  // 工单 09：scrollTop/Left 只在「行数变化」（内容高度变化）时读写——大
  // textarea 场景读/写滚动位置会强制布局（实测 60-150ms/次）；行数不变时
  // .code-edit 显式高度不变，窗口 innerHTML 重建不改变滚动，容器自动保持。
  const prevCount = winCache.lineCount;
  // 只重绘窗口行（滚动窗口化 08）：内容变化 → 重建逐行缓存 + 重测尺寸 +
  // 画当前滚动窗口（textarea 本体不重建——焦点/选区零抖动）。工单 11：内容
  // 未变零重建；非折叠态行数不变 → 增量 patch 只重算变更行；折叠态/行数变化
  // → 全量 winBuild。
  const viewText = viewModel ? viewModel.text : tab.content;
  if (winCache.text === viewText) {
    // 内容未变（选区/状态类输入）：零重建，尺寸/窗口均不动
  } else if (!viewModel
    && (curEditSpan && !curEditSpan.structural
      ? true   // 非结构编辑：无换行增删 → 行数必不变，免一次全量 split
      : viewText.split("\n").length === winCache.lineCount)) {
    winPatchEdit(viewText, tab.lang, curEditSpan);
    if (!(curEditSpan && !curEditSpan.structural && winPatchRow(curEditSpan))) {
      winRender();   // 行级修补失败（窗口外/元素缺失）→ 全量窗口重画
    }
  } else {
    winBuild(viewText, tab.lang);
    winRender();
  }
  const needScrollRestore = winCache.lineCount !== prevCount;
  let scrollTop = 0;
  let scrollLeft = 0;
  if (needScrollRestore) {
    scrollTop = box.scrollTop;
    scrollLeft = box.scrollLeft;
  }
  winApplySize();
  // 只写不读（需要时）：行数变化才恢复滚动（先恢复再窗口重装——taWindowApply
  // 在光标出窗时以光标为准滚动，覆盖恢复值，语义正确）
  if (needScrollRestore) {
    box.scrollTop = scrollTop;
    box.scrollLeft = scrollLeft;
  }
  // 标记层渲染单点（工单 code-editor-opt/05）：窗口渲染（winRender →
  // winRenderMarks，或 winPatchRow 行级修补）已用「状态先行」的最新
  // editorWord/editorBracket/editorFind/错误 渲染一次即终——不再调用
  // renderEditorMarks 二次全量重画（其仅保留给查找输入/命中跳转等外部入口）。
  if (taWinInfo) {
    // 窗口化（02；04 三层组合含折叠态）：窗口文本已随模型漂移——重装窗口 +
    // 光标落位。caretModel（模型偏移）在折叠态换算为视图偏移再装窗
    // （taWindowApply 契约 = 视图坐标，winCache.lines 即视图行）；IME 组合中
    // 不重装（打断候选窗），raw 值留窗、compositionend 后补。
    if (composing) {
      taWinDirty = true;
      taWinInfo = { ...taWinInfo, text: ta.value };
    } else {
      const caretM = caretModel == null ? 0 : caretModel;
      const viewCaret = viewModel
        ? codeFoldModelToView(viewModel.segs, caretM)
        : caretM;
      taWindowApply(viewCaret, follow);
    }
    setActiveLine(caretLineFast(taCaretViewPos()));
  } else {
    setActiveLine(caretLineFast(taCaretViewPos()));
    if (!composing) {
      // 工单 09：已聚焦不重复 focus / 选区未变不 setSelectionRange——大
      // textarea 下这两者是强制布局 / 光标重排的重触发点（实测占比大头）
      if (document.activeElement !== ta) ta.focus();
      if (ta.selectionStart !== selStart || ta.selectionEnd !== selEnd) {
        ta.setSelectionRange(selStart, selEnd);
      }
    }
  }
  renderTabs();   // 脏点随输入即时刷新（标签条内联渲染，事件委托不失效）
  notifyActive();   // 状态栏信息区随内容/光标刷新（onActiveTabChanged → refreshCodeStatus；不再单独 notifyCursor——避免每击键双刷）
}

// applyEdit(text, start, end)：程序化编辑（Tab/Enter/行操作/注释/括号/AI 插入/
// 查找替换共用）落库。统一「模型为唯一事实源」：
//   - 非折叠窗口化（02/03）：text/start/end = **模型**偏移——写模型 + 窗口重装 +
//     模型级快照；不再走 execCommand（原生撤销栈只认「textarea=全量文本」旧
//     语义，视口化后窗口内/跨窗口必错乱——03 明确放弃）。
//   - 折叠窗口化（04 三层组合）：text/start/end = **视图**坐标（editSource 折叠
//     态返回视图全文 + 视图选区——保持 07 既有全视图语义：Alt+↑↓ 移动行/Ctrl+A
//     全选等不能把窗口边界当文档边界）；codeFoldMapEdit 视图→模型回写（占位
//     触碰展开/整块覆盖语义原样承接），syncTail 统一窗口/光标落位。
//   - 全量兜底：直赋值 + syncEditorAfterInput。
function applyEdit(text, start, end) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
  const tab = getActiveTab();
  if (!tab || tab.readonly) return;
  if (taWinInfo && !viewModel) {
    if (tab.content === text) {
      ta.focus();
      taSetRange(start, end);
      return;
    }
    pushEditSnapshot();
    const oldText = tab.content;
    const span = editChangeSpan(oldText, text);
    curEditSpan = span.structural ? null : span;
    tab.content = text;
    applyCachePatches(oldText, text, span);
    syncTail(Math.max(0, end | 0));
    scheduleCursorWork();
    return;
  }
  if (viewModel) {
    // 折叠（07 既有语义 + 04 窗口化）：视图全文编辑 → codeFoldMapEdit 写回模型
    if (viewModel.text === text) {
      ta.focus();
      if (taWinInfo) taSetRange(start, end);   // start/end = 视图坐标
      else ta.setSelectionRange(start, end);
      return;
    }
    pushEditSnapshot();       // 03：模型级编辑前快照（程序化不进 input 事件）
    const r = codeFoldMapEdit(tab.content, viewModel.segs, viewModel.text, text);
    tab.content = r.model;
    r.expand.forEach((i) => foldedSet.delete(i));
    const oldFolds = folds;
    folds = codeFoldRanges(tab.content, tab.lang);
    foldedSet = codeFoldMerge(oldFolds, foldedSet, folds);
    viewModel = (folds.length && foldedSet.size)
      ? codeFoldVisible(tab.content, folds, foldedSet)
      : null;
    syncTail(r.caret);
    scheduleCursorWork();
    return;
  }
  if (ta.value === text) {
    ta.setSelectionRange(start, end);
    return;
  }
  // 非折叠非窗口（兜底/兼容既有全量路径）：直赋值 + 快照栈接管——
  // 编辑前模型状态经 syncEditorAfterInput 的变更入口统一入栈（pendingSnapshot
  // 携带，防双入）。
  pendingSnapshot = captureModelSnapshot();
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
  curEditSpan = null;    // 本次输入未定/结构变更时置 null（防 updateWordMarks 误用陈旧 span）
  if (viewModel) {
    // ===== 折叠态（工单 07 + 04 三层组合）=====
    // 视图文本编辑 → 偏移映射写回模型；触碰占位 → 展开 + 重设视图文本与光标
    // （模型偏移 → 新视图偏移）；折叠区随内容重算并按签名保留既有折叠态
    // （codeFoldMerge）。
    // 04：折叠态 textarea 已窗口化（装视图切片）——先经 01 窗口映射
    // 窗口→视图（windowEditToView）→ 模型（windowEditToModel，segs 非空走
    // codeFoldMapEdit 既有「触碰占位 → 展开/整块覆盖」语义）；无窗口兜底
    // 走既有全量视图映射（历史路径，防御保留）。映射失败 → 以模型重建窗口。
    const lineStarts = winCache ? winCache.lineStarts : null;
    const newWin = String(ta.value == null ? "" : ta.value);
    const v = taWinInfo
      ? windowEditToView(editChangeSpan(taWinInfo.text, newWin), taWinInfo, lineStarts)
      : null;
    const r = taWinInfo
      ? (v == null ? null
        : windowEditToModel(tab.content, viewModel.segs, viewModel.text,
            taWinInfo, lineStarts, newWin))
      : codeFoldMapEdit(tab.content, viewModel.segs, viewModel.text, ta.value);
    if (taWinInfo && (v == null || r == null)) {
      rebuildWindowKeepCaret();   // 失配（窗口与行起点表不同步等）：以模型重建窗口
      return;
    }
    const textChanged = taWinInfo ? taWinInfo.text !== newWin : viewModel.text !== ta.value;
    if (textChanged) pushTypingSnapshot();   // 03：真实变更 → 编辑前快照入栈（此时 tab.content 仍是旧模型）
    tab.content = r.model;
    r.expand.forEach((i) => foldedSet.delete(i));
    const oldFolds = folds;
    folds = codeFoldRanges(tab.content, tab.lang);
    foldedSet = codeFoldMerge(oldFolds, foldedSet, folds);
    viewModel = (folds.length && foldedSet.size)
      ? codeFoldVisible(tab.content, folds, foldedSet)
      : null;
    if (textChanged) {
      // 窗口化（含折叠）：落位统一交 syncTail——组合守卫（composing 不重装、
      // 防打断候选窗）+ 模型→视图换算单点（syncTail 内）都在那里；
      // 此处只保留「无窗口」历史全量路径的直赋值兜底（04 后折叠必窗口化）。
      if (viewModel) {
        if (!taWinInfo) {
          const vo = codeFoldModelToView(viewModel.segs, r.caret);
          ta.value = viewModel.text;
          ta.setSelectionRange(vo, vo);
        }
      } else if (!taWinInfo) {
        // 占位触碰后全部展开（评审整改 07c）：视图回全量文本、光标落插入点
        ta.value = tab.content;
        ta.setSelectionRange(r.caret, r.caret);
      }
    } else {
      clearTypingSnapshot();   // 无真实变更：不产生撤销步，丢弃已捕获快照
    }
    // 真实变更 → 光标取映射 caret；无变更（IME 取消等）→ 保持当前模型光标
    // （codeFoldMapEdit 的 identical 分支 caret 恒 0，不能拿来重装——会把
    // 光标拉回视图顶；04 评审整改）。
    syncTail(textChanged ? r.caret : foldCaretModelPos(), false);
    return;
  }
  if (taWinInfo) {
    // ===== 窗口化路径（工单 editor-textarea-viewport/02）=====
    // 窗口文本变更 → 01 映射 → 模型全文；映射失败（窗口/行起点表不同步）→
    // 以模型为准重建窗口文本（宁可重装，不可错位）。
    const oldWin = taWinInfo.text;
    const newWin = String(ta.value == null ? "" : ta.value);
    if (oldWin === newWin) {
      clearTypingSnapshot();   // 无真实变更：不产生撤销步
      // 内容未变（IME compositionend 等）：先经 01 一致性校验——窗口文本与
      // 模型推导不符（外部漂移/罕见路径）→ 以模型重建，不静默错位。
      if (!windowTextMatchesModel(tab.content, viewModel, taWinInfo.start, taWinInfo.end, newWin)) {
        rebuildWindowKeepCaret();
        return;
      }
      // 仅重装/状态刷新，光标留在原选区；follow=false：组合期间用户可能已
      // 滚动，不把视口拉回光标
      const cur = windowPosToView(taWinInfo, ta.selectionStart);
      syncTail(cur, false);
      taWinDirty = false;
      return;
    }
    const lineStarts = winCache ? winCache.lineStarts : null;
    const span = editChangeSpan(oldWin, newWin);
    const v = windowEditToView(span, taWinInfo, lineStarts);
    const r = v == null ? null
      : windowEditToModel(tab.content, null, winCache ? winCache.text : tab.content,
          taWinInfo, lineStarts, newWin);
    if (v == null || r == null) {
      rebuildWindowKeepCaret();   // 失配（窗口与行起点表不同步等）：以模型重建窗口
      return;
    }
    pushTypingSnapshot();   // 03：真实变更 → 编辑前快照入栈（此时 tab.content 仍是旧模型）
    const editSpan = {
      structural: span.structural,
      p: v.p,
      oldSegLen: v.oldSegLen,
      newSegLen: v.newSegLen,
      line: caretLineFromStarts(lineStarts || [], v.p),
    };
    curEditSpan = editSpan.structural ? null : editSpan;
    tab.content = r.model;
    applyCachePatches(winCache ? winCache.text : null, tab.content, editSpan);
    syncTail(r.caret);
    return;
  }
  // ===== 非窗口化非折叠（兜底/兼容既有全量路径）=====
  {
    const span = editChangeSpan(winCache ? winCache.text : "", ta.value,
      winCache ? winCache.lineStarts : null);
    curEditSpan = span;   // 非结构编辑：供 updateWordMarks 词区段增量（结构变更下方置 null 由行首重置兜底——此处直接设）
    if (span.structural) curEditSpan = null;
    if (!span.identical) pushTypingSnapshot();   // 03：真实变更 → 编辑前快照入栈
    else clearTypingSnapshot();
    tab.content = ta.value;
    markClean = false;   // 默认标记失效；纯字符编辑才保持
    applyCachePatches(winCache ? winCache.text : null, tab.content, span);
    syncTail(null);
  }
}

// ===== 查找替换（工单 code-editor-utilize/03 + code-page-vscode-overhaul/03）=====
// rebaseModelContent(newContent, caret)：模型内容整体替换后的折叠重算 + 视图
// 重建 + 光标落位——折叠态不能经 applyEdit 直写模型（会把模型当视图喂
// mapEdit → 占位误判整块替换丢内容），需要模型级重写（代码不变）；caret =
// 模型偏移（null → 文件尾，与既有「替换后光标置文件尾」语义一致）。03/04：
// 窗口化（含折叠三层组合）统一经 taWindowApply 按**视图坐标**重装窗口落位。
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
  ta.focus();
  const vo = viewModel
    ? codeFoldModelToView(viewModel.segs, caretM)
    : caretM;
  if (taWinInfo) taWindowApply(vo);   // 04：折叠/非折叠窗口化统一按视图偏移重装
  else ta.setSelectionRange(vo, vo);
}

// insertIntoActiveFile(text)：把文本插入活动标签当前光标/选区（工单
// code-editor-refine/08）——无选区 = 光标处插入；有选区 = 替换选区；折叠态
// 经 codeFoldViewToModel 映射到模型偏移后 rebaseModelContent（模型级重写 +
// 折叠按签名保留）；非折叠走 applyEdit 同手输路径（textarea + 高亮/行号/脏点/
// 撤销同步）。插入后光标 = 插入末尾；只读 / 无活动标签 → false 不改动；
// 不自动落盘（用户 Ctrl+S 既有保存冲突/写盘守卫）。
export function insertIntoActiveFile(text) {
  const tab = getActiveTab();
  if (!tab || tab.readonly) return false;
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return false;   // .md 预览态/未渲染：无可编辑缓冲——不做尾部追加假成功（评审整改）
  // 选区 → 模型偏移单源换算：editorSelectionModel（窗口→视图→模型，折叠/
  // 非折叠统一）；无选区（坍缩光标）→ foldCaretModelPos（同链取光标）。
  const sel = editorSelectionModel();
  const start = sel ? sel.start : foldCaretModelPos();
  const end = sel ? sel.end : start;
  const r = insertAtPosition(tab.content, text, { start, end });
  if (viewModel) {
    pushEditSnapshot();   // 折叠态走 rebase 不经 input 事件——快照栈补撤销（03 全域化：与窗口化同一模型级快照）
    rebaseModelContent(r.value, r.selStart);
  } else {
    applyEdit(r.value, r.selStart, r.selEnd);
  }
  return true;
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
    pushEditSnapshot();   // 03 全域化：折叠态 replaceAll 走 rebase 不经 input——快照栈补撤销
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
  if (viewModel) {
    pushEditSnapshot();   // 03 全域化：折叠态 replaceOne 走 rebase 不经 input——快照栈补撤销
    rebaseModelContent(r.value, caret);
  } else applyEdit(r.value, caret, caret);
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
  // 现场诊断面板（Ctrl+Alt+D，用户现场排障用——显示各层几何与命中目标，
  // 屏幕直接可读；无副作用，正常使用不触发）
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || !e.altKey || e.key.toLowerCase() !== "d") return;
    e.preventDefault();
    let old = document.getElementById("code-diag-box");
    if (old) { old.remove(); return; }
    const box = paneBox();
    if (!box) return;
    const edit = box.querySelector(".code-edit");
    const ta = box.querySelector(".code-ta");
    const hl = box.querySelector(".code-hl");
    const gutter = box.querySelector(".code-gutter");
    const r = (el) => el ? Math.round(el.getBoundingClientRect().top) + ".." + Math.round(el.getBoundingClientRect().bottom) : "无";
    const br = box.getBoundingClientRect();
    const hitLines = [];
    if (hl) {
      for (const ln of Array.from(hl.querySelectorAll(".code-hl-line"))) {
        const lr = ln.getBoundingClientRect();
        if (lr.top >= br.top - 1 && lr.top < br.bottom + 1) {
          const el = document.elementFromPoint(br.right - 30, lr.top + lr.height / 2);
          hitLines.push("行" + ln.dataset.codeLine + "→" + (el ? (el.className || el.tagName) : "无"));
        }
      }
      hitLines.sort((a, b) => parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10));
    }
    const d = document.createElement("div");
    d.id = "code-diag-box";
    d.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:99999;background:#111;color:#eee;"
      + "border:1px solid #888;border-radius:var(--radius-md);padding:10px 14px;font:12px/1.7 monospace;"
      + "max-width:640px;white-space:pre-wrap;";
    d.textContent = [
      "滚动盒: " + r(box) + " 高" + Math.round(br.height),
      "edit: " + r(edit) + " 行高?" + (edit ? edit.style.height : ""),
      "ta:   " + r(ta) + " 视图行数=" + (ta ? ta.value.split("\n").length : 0),
      "hl:   " + r(hl) + " 行元素=" + (hl ? hl.querySelectorAll(".code-hl-line").length : 0),
      "gutter:" + r(gutter) + " 行元素=" + (gutter ? gutter.querySelectorAll(".code-gutter-line").length : 0),
      "scrollTop=" + Math.round(box.scrollTop),
      "textarea 命中采样(右缘): " + (hitLines.slice(0, 6).concat(hitLines.slice(-6)).join(" | ") || "无"),
      "全部命中: " + (hitLines.length ? hitLines.join(" | ") : "无"),
      "(Ctrl+Alt+D 关闭)",
    ].join("\n");
    document.body.appendChild(d);
  });
  // 滚动窗口化（工单 08）：窗口内滚动零 DOM（winRender 同窗跳过），跨窗口
  // 同步重建；rAF 节流（工单 04）：一次 rAF 合并突发滚动事件（快速拖滚只
  // 重装一次目标窗口，不逐帧重装）——「仅窗口行区间变化才重装文本」判定在
  // taWindowSync 内（同窗零 DOM），节流只合并事件、不吞正确性。
  // 视口尺寸变化（布局/面板高度）经 ResizeObserver 同步重画（不节流——尺寸
  // 事件低频，且需要精确窗口）。
  const viewBox = paneBox();
  if (viewBox) {
    let scrollRaf = 0;
    const scrollSync = () => {
      scrollRaf = 0;
      winReadView();
      winRender();
      taWindowSync();
    };
    viewBox.addEventListener("scroll", () => {
      if (scrollRaf) return;
      scrollRaf = requestAnimationFrame(scrollSync);
    });
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(() => { winReadView(); winRender(); taWindowSync(); }).observe(viewBox);
    }
  }
  const strip = $("code-tabs");
  if (strip) strip.addEventListener("click", (e) => {
    const close = e.target.closest("[data-tab-close]");
    if (close) {
      e.stopPropagation();
      closeTab(close.closest("[data-tab-path]").dataset.tabPath);
      return;
    }    // 「磁盘已变更」徽章（code-ide-flow/02）：点击弹既有三选，**不**触发
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
        setActiveLine(caretLineFast(taCaretViewPos()));
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
    // 组合输入保护：compositionend 后补一次同步（内容一次性落定）。
    // 03 撤销全域化：compositionstart 捕获「编辑前快照」——一次组合 = 一步
    // 撤销（组合中 beforeinput 不覆盖，输入中间态不单列入栈）。
    // target 守卫与 beforeinput 同形（防其它元素组合事件误触发——评审整改）。
    box.addEventListener("compositionstart", (e) => {
      const ta = e.target;
      if (!ta || !ta.classList || !ta.classList.contains("code-ta")) return;
      composing = true;
      pendingSnapshot = captureModelSnapshot();
    });
    box.addEventListener("compositionend", (e) => {
      const ta = e.target;
      if (!ta || !ta.classList || !ta.classList.contains("code-ta")) return;
      composing = false;
      syncEditorAfterInput();
    });
    // beforeinput：手打/粘贴/剪切等真实输入前，textarea 值与选区仍是编辑前
    // 状态——捕获模型级「编辑前快照」；input 事件在真实变更入口统一入栈。
    box.addEventListener("beforeinput", (e) => {
      const ta = e.target;
      if (!ta || !ta.classList || !ta.classList.contains("code-ta") || ta.readOnly) return;
      if (composing) return;   // 组合中：保留 compositionstart 捕获的快照
      pendingSnapshot = captureModelSnapshot();
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
      setActiveLine(caretLineFast(taCaretViewPos()));
      scheduleCursorWork();
      // 撤销/重做全域接管（工单 03）：textarea 只装窗口文本，浏览器原生撤销
      // 栈语义错乱（窗口内/跨窗口）——Ctrl+Z/Y/Shift+Z 一律拦截走模型级快照
      // 栈（焦点在编辑器内即编辑器优先，与既有语义一致）。
      if ((e.ctrlKey || e.metaKey) && !e.altKey) {
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
      const eb = editSource();   // 窗口化 = 模型全文+模型选区；折叠/全量 = 视图
      if (e.key === "Tab" && e.shiftKey) {
        e.preventDefault();
        const r = shiftTab(eb.text, eb.selStart, eb.selEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (e.key === "Tab") {
        e.preventDefault();
        const r = indentLines(eb.text, eb.selStart, eb.selEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const r = indentOnEnter(eb.text, eb.selStart, eb.selEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing
        && (e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "k") {
        // 行操作（工单 code-page-vscode-overhaul/01）：Ctrl+Shift+K 删除行
        e.preventDefault();
        const r = deleteLine(eb.text, eb.selStart, eb.selEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && e.altKey && !e.ctrlKey && !e.metaKey
        && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        // 行操作（工单 code-page-vscode-overhaul/01）：Alt+↑↓ 移动行 /
        // Shift+Alt+↑↓ 复制行
        e.preventDefault();
        const dir = e.key === "ArrowUp" ? "up" : "down";
        const r = e.shiftKey
          ? copyLine(eb.text, eb.selStart, eb.selEnd, dir)
          : moveLine(eb.text, eb.selStart, eb.selEnd, dir);
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && (e.ctrlKey || e.metaKey)
        && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "l") {
        // 行操作（工单 code-page-vscode-overhaul/01）：Ctrl+L 选整行
        e.preventDefault();
        const r = lineRangeOf(eb.text, eb.selStart, eb.selEnd);
        // 折叠窗口化：r 是视图坐标 → taSetRange（视图→窗口换算）同样适用；
        // 非折叠窗口化：r 是模型（=视图）坐标；全量：直接选区
        if (taWinInfo) taSetRange(r.start, r.end);
        else ta.setSelectionRange(r.start, r.end);
        setActiveLine(caretLineFast(taCaretViewPos()));
        scheduleCursorWork();
      } else if (!e.isComposing && !composing && (e.ctrlKey || e.metaKey)
        && !e.shiftKey && !e.altKey && e.key === "/") {
        // 注释切换（工单 code-page-vscode-overhaul/02）：.c/.h 逐行 //、
        // 选中含 /* */ 切块注释；XML 逐行 <!-- -->（仅 c/xml 编辑态）
        const tab = getActiveTab();
        if (!tab || (tab.lang !== "c" && tab.lang !== "xml")) return;
        e.preventDefault();
        const sel = eb.text.slice(eb.selStart, eb.selEnd);
        const r = tab.lang === "xml"
          ? toggleLineComment(eb.text, eb.selStart, eb.selEnd,
            { open: "<!--", close: "-->" })
          : (sel.includes("/*")
            ? toggleBlockComment(eb.text, eb.selStart, eb.selEnd,
              { open: "/*", close: "*/" })
            : toggleLineComment(eb.text, eb.selStart, eb.selEnd,
              { open: "//" }));
        applyEdit(r.value, r.start, r.end);
      } else if (!e.isComposing && !composing && !e.ctrlKey && !e.metaKey && !e.altKey
        && (BRACKET_OPEN[e.key] || BRACKET_CLOSE[e.key] || e.key === "Backspace")) {
        // 括号行为（工单 06）：仅 c/xml/md 编辑态启用（spec：plain 走浏览器
        // 默认插入——评审整改 06b）；IME 组合输入中不拦截（评审整改 06a）。
        // 03/04 整改：修饰键组合不拦截——Ctrl+Shift+[/] 是折叠快捷键，不能被
        // 括号自动闭合劫持（此前 Ctrl+Shift+[ 会在光标处插入 "[]"）。
        const tab = getActiveTab();
        const langOk = !!tab && (tab.lang === "c" || tab.lang === "xml" || tab.lang === "md");
        if (!langOk) return;
        if (BRACKET_OPEN[e.key]) {
          e.preventDefault();
          const r = bracketOpen(eb.text, eb.selStart, eb.selEnd, e.key);
          applyEdit(r.value, r.start, r.end);
        } else if (BRACKET_CLOSE[e.key]) {
          const r = bracketClose(eb.text, eb.selStart, eb.selEnd, e.key);
          if (r) {
            e.preventDefault();
            applyEdit(r.value, r.start, r.end);
          }
        } else if (e.key === "Backspace") {
          const r = bracketBackspace(eb.text, eb.selStart, eb.selEnd);
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
      if (ta) setActiveLine(caretLineFast(taCaretViewPos()));
      scheduleCursorWork();   // 状态栏 Ln/Col 随选区变化刷新（工单 01；顺延一帧，性能整改）
    });
    // 点击也立即刷当前行高亮（用户现场修复：部分浏览器 textarea 点击不触发
    // select/keyup——高亮行落后光标一行；click 兜底，幂等）
    box.addEventListener("click", () => {
      const ta = box.querySelector(".code-ta");
      if (ta) setActiveLine(caretLineFast(taCaretViewPos()));
    });
    box.addEventListener("keyup", (e) => {
      const ta = e.target;
      if (ta && ta.classList && ta.classList.contains("code-ta")) {
        setActiveLine(caretLineFast(taCaretViewPos()));
        scheduleCursorWork();
      }
    });
  }
}
