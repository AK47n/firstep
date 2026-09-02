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
import {
  codeTabStripHTML,
  codeEditorHTML,
  codeEditorHighlight,
  conflictHTML,
  editorLineRange,
  isTabSavable,
  dirtySavableTabs,
  caretLineOf,
  indentOnEnter,
  indentLines,
  replaceAllText,
  EDITOR_TABS_MAX,
} from "/js/fx/codeeditor.js";
import { parseMarkdownBlocks, markdownPreviewHTML, markdownOutline, hasScheme } from "/js/fx/markdown.js";
import { mtimeEq } from "/js/fx/disk-baseline.js";  // mtime 相等守卫单源（工单 07 评审整改：与基线 diff/快照守卫同口径）
import { treeRenamedPath, treeOpAffected } from "/js/fx/code-tree-ops.js";  // 重命名路径映射纯件（工单 code-tree-ops/02）
import { confirmModal } from "/js/ui/confirm.js";

// ---- 模块态：目录 / 标签 / 活动文件 / 内容 memo / 监听器 ----
let codeDir = "";
let tabs = [];           // {path, lang, content, savedContent, outline, mtime_ns, utf8, mdMode, readonly}
let activePath = "";
const fileCache = new Map();  // key = fileCacheKey(path) → {ok:true, data} | {ok:false, message}

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
  cursorListeners.forEach((cb) => { try { cb(); } catch (e) { /* 监听器异常不阻断 */ } });
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
  // 编辑态（含 .md「编辑源码」态——工单 05；预览态已提前 return）：
  // 同一三明治渲染，md 与普通文件共用（评审整改：去双分支重复）。
  const lines = tab.content.split("\n").length;
  box.innerHTML = '<div class="code-gutter" aria-hidden="true">'
    + codeLineNumbersHTML(lines) + "</div>"
    + codeEditorHTML(tab.content, tab.lang, { readonly: tab.readonly });
  if (tab.readonly) renderReadonlyNote(box);
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
  notifyCursor();   // 状态栏 Ln/Col 随跳行刷新（工单 01）
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
  notifyCursor();   // 状态栏 Ln/Col 随输入即时刷新（工单 01）
}

// ===== 查找替换（工单 code-editor-utilize/03）：当前文件「全部替换」 =====
// replaceAllInActiveFile(needle, replacement)：活动标签全部替换——空针 /
// 无活动标签 / 只读标签 / 无匹配 → 0 且不改；有效时走 applyEdit 同手输路径
// （textarea 值 + 高亮/行号/脏点/标签条同步），光标置于文件尾，不自动写盘
// （用户 Ctrl+S 落盘，与手输同语义）。返回替换次数。
export function replaceAllInActiveFile(needle, replacement) {
  const tab = getActiveTab();
  if (!tab || tab.readonly) return 0;
  const r = replaceAllText(tab.content, needle, replacement);
  if (!r.count) return 0;
  applyEdit(r.value, r.value.length, r.value.length);
  return r.count;
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
      notifyCursor();   // 状态栏 Ln/Col 随选区变化刷新（工单 01）
    });
    box.addEventListener("keyup", (e) => {
      const ta = e.target;
      if (ta && ta.classList && ta.classList.contains("code-ta")) {
        setActiveLine(caretLineOf(ta.value, ta.selectionStart));
        notifyCursor();
      }
    });
  }
}
