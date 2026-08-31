// ui/codeeditor.js — 代码编辑器 DOM 胶水（工单 code-viewer-editor/02）
//
// 「代码」tab 中栏全部交互：多文件标签条（打开/切换/关闭/脏点/上限 10）+
// 可编辑三明治（textarea + 高亮层，无换行 + 容器滚动——逐行 span 保留跳行/
// 当前行语义）+ Tab 缩进 / Enter 自动缩进 + 光标行高亮 + 跳行（大纲/搜索/
// 文件内查找共用 setSelectionRange 路径）+ .md 两态（预览 / 源码）与关闭脏
// tab 确认（confirmModal 单源）。文件内容 memo（dir+path）与目录上下文
// setCodeDir 由本模块持有；保存（t03）与冲突（t04）在同一状态之上扩展。
// 纯件在 fx/codeeditor.js；ui/codeview.js 只保留树 / 侧栏 / 工具栏，经
// 本模块导出面联动（openEditorFile / getActiveTab / editJumpToLine /
// setMdMode / onActiveTabChanged）。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { languageOf } from "/js/fx/highlight.js";
import { codeLineNumbersHTML, codeViewHTML } from "/js/fx/codeview.js";
import {
  codeTabStripHTML,
  codeEditorHTML,
  codeEditorHighlight,
  editorLineRange,
  isTabSavable,
  caretLineOf,
  indentOnEnter,
  indentLines,
  EDITOR_TABS_MAX,
} from "/js/fx/codeeditor.js";
import { parseMarkdownBlocks, markdownPreviewHTML, markdownOutline, hasScheme } from "/js/fx/markdown.js";
import { confirmModal } from "/js/ui/confirm.js";

// ---- 模块态：目录 / 标签 / 活动文件 / 内容 memo / 监听器 ----
let codeDir = "";
let tabs = [];           // {path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode, readonly}
let activePath = "";
const fileCache = new Map();  // key = dir + "\u0000" + path → {ok:true, data} | {ok:false, message}
const activeListeners = new Set();

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

function notifyActive() {
  const tab = getActiveTab();
  activeListeners.forEach((cb) => { try { cb(tab); } catch (e) { /* 监听器异常不阻断 */ } });
}

function notifySaved(tab, resp) {
  savedListeners.forEach((cb) => { try { cb(tab, resp); } catch (e) { /* 同上 */ } });
}

function tabOf(path) { return tabs.find((t) => t.path === path) || null; }

function tabShape(t) {
  return {
    path: t.path,
    lang: t.lang,
    dirty: t.content !== t.savedContent,
    readonly: t.readonly,
  };
}

// ===== 文件内容 memo（业务 400 缓存，网络 / ≥500 不缓存可重试——对偶
// 查看器 loadCodeFileState 先例） =====
function fileURL(path) {
  return "/api/code/file?dir=" + encodeURIComponent(codeDir)
    + "&path=" + encodeURIComponent(path);
}

async function loadFileState(path) {
  const key = codeDir + "\u0000" + path;
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
    box.innerHTML = '<span class="muted">点左侧文件在编辑器中打开（可修改，Ctrl+S 保存）</span>';
    return;
  }
  if (tab.lang === "md" && tab.mdMode === "preview") {
    box.innerHTML = markdownPreviewHTML(parseMarkdownBlocks(tab.content), { imageUrl: mdImageUrl });
    return;
  }
  if (tab.lang === "md") {  // 源码态（t02 只读视图；「编辑源码」= t05）
    box.innerHTML = codeViewHTML(tab.content, tab.lang);
    return;
  }
  const lines = tab.content.split("\n").length;
  box.innerHTML = '<div class="code-gutter" aria-hidden="true">'
    + codeLineNumbersHTML(lines) + "</div>"
    + codeEditorHTML(tab.content, tab.lang, { readonly: tab.readonly });
  const ta = box.querySelector(".code-ta");
  if (ta && tab.readonly) {
    renderReadonlyNote(box);
  }
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
  paneBox().innerHTML = '<span class="muted">加载中…</span>';
  const cached = await loadFileState(path);
  if (!cached.ok) {
    paneBox().innerHTML = '<div class="error">加载失败：' + cached.message
      + '</div><span class="muted">点击左侧文件可重试。</span>';
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
    mdMode: lang === "md" ? "preview" : "edit",
    readonly: data.utf8 === false,
  };
  tabs.push(tab);
  activateTab(path);
}

// setMdMode(path, mode)：.md 两态切换（preview ↔ source；t05 起 source =
// 可编辑）——切换后重渲染并通知（大纲不变，查找面板内容随态重算）。
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

// closeTab(path, {force})：关闭标签——脏 tab 弹 confirmModal（确认丢弃 /
// 取消保留；不误丢修改）；关活动标签 → 激活右邻（无则左邻，再无一无）。
export async function closeTab(path) {
  const idx = tabs.findIndex((t) => t.path === path);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (tab.content !== tab.savedContent) {
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
  renderTabs();
  renderPane();
  notifyActive();
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
// （选区即持续高亮）+ flash。
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
  const el = box.querySelector('.code-hl-line[data-code-line="' + line + '"]')
    || box.querySelector('.code-pre-line[data-code-line="' + line + '"]');
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  setActiveLine(line);
  flashEl(el);
  const ta = box.querySelector(".code-ta");
  if (ta && !ta.readOnly) {
    const range = editorLineRange(tab.content, line);
    if (range) {
      ta.focus();
      ta.setSelectionRange(range.start, range.end);
    }
  }
}

// editJumpToFile(path, line)：跨文件跳转（搜索命中）——打开（.md 预览态
// 先切源码——行语义需要行号）→ 跳行。
export async function editJumpToFile(path, line) {
  const tab = tabOf(path);
  if (tab && tab.lang === "md" && tab.mdMode === "preview") setMdMode(path, "source");
  await openEditorFile(path, tab && tab.lang === "md" ? "source" : undefined);
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
    const resp = await apiPost("/api/code/save", {
      dir: codeDir,
      path: tab.path,
      content: tab.content,
      base_mtime_ns: tab.mtime_ns,
    });
    tab.savedContent = tab.content;
    tab.mtime_ns = resp.mtime_ns;
    tab.outline = resp.outline;
    toast("ok", "已保存 " + tab.path);
    renderTabs();
    notifyActive();
    notifySaved(tab, resp);
  } catch (e) {
    if (e.status === 409) {
      toast("error", e.message || "保存冲突：磁盘上的文件已被外部修改");
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

// ===== 编辑器键盘行为：Tab 缩进 / Enter 自动缩进 / 光标行高亮 =====
// IME 组合输入保护（评审整改）：composition 期间绝不 setSelectionRange 重置
// 选区——会打断中文候选窗（input 逐键触达 sync，只做重渲染不动光标）。
let composing = false;

function applyEdit(text, start, end) {
  const ta = paneBox() && paneBox().querySelector(".code-ta");
  if (!ta) return;
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
  tab.content = ta.value;
  const selStart = ta.selectionStart;
  const selEnd = ta.selectionEnd;
  const scrollTop = box.scrollTop;
  const scrollLeft = box.scrollLeft;
  // 只重绘高亮层与行号列（.code-edit 的 max-content 宽度/高度随 pre 自动
  // 调整，容器滚动不变；textarea 本体不重建——焦点/选区零抖动）
  gutter.innerHTML = codeLineNumbersHTML(tab.content.split("\n").length);
  hl.innerHTML = codeEditorHighlight(tab.content, tab.lang);
  setActiveLine(caretLineOf(tab.content, selStart));
  box.scrollTop = scrollTop;
  box.scrollLeft = scrollLeft;
  if (!composing) {
    ta.focus();
    ta.setSelectionRange(selStart, selEnd);
  }
  renderTabs();   // 脏点随输入即时刷新（标签条内联渲染，事件委托不失效）
  notifyActive();
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
    const btn = e.target.closest("[data-tab-path]");
    if (btn) activateTab(btn.dataset.tabPath);
  });

  // Ctrl/Cmd+S：tab-code 活动时全局截获（与 Ctrl+F 同口径——焦点在树/侧栏
  // 也生效）；浏览器「保存网页」对话框不出现。
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "s") return;
    const sec = $("tab-code");
    if (!sec || !sec.classList.contains("active")) return;
    e.preventDefault();
    saveActiveTab();
  });
  const saveBtn = $("btn-code-save");
  if (saveBtn) saveBtn.addEventListener("click", () => saveActiveTab());

  const box = paneBox();
  if (box) {
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
      if (e.key === "Tab") {
        e.preventDefault();
        const r = indentLines(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const r = indentOnEnter(ta.value, ta.selectionStart, ta.selectionEnd);
        applyEdit(r.value, r.start, r.end);
      }
    });
    // 光标行高亮跟随（selection 变化：键盘 / 鼠标共同覆盖——select + keyup
    // 双保险；不逐按键重算，评审整改归并 keydown/click/keyup 三处）
    box.addEventListener("select", () => {
      const ta = box.querySelector(".code-ta");
      if (ta) setActiveLine(caretLineOf(ta.value, ta.selectionStart));
    });
    box.addEventListener("keyup", (e) => {
      const ta = e.target;
      if (ta && ta.classList && ta.classList.contains("code-ta"))
        setActiveLine(caretLineOf(ta.value, ta.selectionStart));
    });
  }
}
