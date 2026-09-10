// ui/codeview.js — 代码 tab 容器胶水（工单 code-viewer/04-05 + code-viewer-editor/02）
//
// 「代码」tab 的目录/树/侧栏/工具栏：选择文件夹（/api/pick-directory）→
// 打开目录（/api/code/open）→ 树 → 右侧栏大纲/跨文件搜索/文件内查找 →
// 字号缩放 / 树调宽。中栏（多标签 + 可编辑三明治 + 保存）全部归
// ui/codeeditor.js——本模块经其导出面联动（openEditorFile / getActiveTab /
// editJumpToLine / editJumpToFile / setMdMode / setCodeDir /
// onActiveTabChanged / isMdPreviewActive）。纯件在 fx/codeview.js /
// fx/codeeditor.js。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { codeZoomClamp, parseZoomStored, isMainCPath } from "/js/fx/code.js";
import { isTabSavable, codeStatusHTML } from "/js/fx/codeeditor.js";  // 保存判据单源（code-viewer-editor/03）+ 状态栏信息纯件（code-editor-vscode-polish/01）
import { shortcutHelpHTML } from "/js/fx/code-shortcuts.js";  // 快捷键帮助数据+浮层内容纯件（code-editor-shortcut-help/01）
import {
  baselineSnapshot,
  baselineDiff,
  baselineHasChanges,
  baselineEvict,
  snapshotOf,
  migrateBaselineStore,
  mtimeEq,
} from "/js/fx/disk-baseline.js";  // 磁盘基线对比纯件（code-ide-flow/01——事实源不依赖事件载荷）；内容快照（code-ide-ai/07）；mtimeEq（mtime 守卫单源）
import { changesPanelHTML, changeSummaryText } from "/js/fx/change-panel.js";  // 「磁盘变更」面板条目渲染（code-ide-flow/03）
import { lineDiffCompute } from "/js/fx/line-diff.js";  // 行级 diff 计算（code-ide-flow/03 main.c 起步；code-ide-ai/08 泛化——面板行级展示任意打开过的文件）
import { getMainCDiskDir, loadDiskMainC, refreshMainCDiskState } from "/js/ui/generate-mainc-sync.js";  // main.c 磁盘同步（mainc-codeview-bridge/03 + code-viewer-editor/05：保存后步骤 8 状态行刷新）
import { scrollToStep } from "/js/ui/step-state.js";  // 跳回生成页滚动到步骤 8（mainc-codeview-bridge/03）
import { setCodeAiDir, onCodeAiApplied } from "/js/ui/code-ai-chat.js";  // AI 对话面板（code-ide-ai/03-04）：目录打开 → 面板可见性 + 历史；apply 成功 → 立即感知
import { showPanel, hidePanel, initCodeBottomPanels } from "/js/ui/code-bottom-panels.js";  // 底部面板 tab 化（工单 06）
onCodeAiApplied(() => checkCodeDiskChanges());  // C2 应用闭环（工单 04）：AI 写盘后立即感知（变更面板自动出现）
import {
  buildCodeTree,
  codeTreeHTML,
  breadcrumbSegments,
  breadcrumbHTML,
  outlineHTML,
  outlineEmptyHTML,
  symbolFilter,
  searchListHTML,
  fileFindFilter,
  treeWidthClamp,
  parseTreeWidthStored,
  CODE_TREE_WIDTH_MAX,
  CODE_TREE_WIDTH_DEFAULT,
  TREE_CHANGE_NEW,
  TREE_CHANGE_MODIFIED,
} from "/js/fx/codeview.js";
import {
  setCodeDir,
  openEditorFile,
  getActiveTab,
  closeTab,
  editJumpToLine,
  editJumpToFile,
  setMdMode,
  isMdPreviewActive,
  onActiveTabChanged,
  onCursorChanged,
  onFileSaved,
  onFileLoaded,
  openTabPaths,
  dirtyTabPaths,
  setDiskChanged,
  clearDiskChanged,
  reloadTabFromDisk,
  replaceAllInActiveFile,
  replaceOneInActiveFile,
  setEditorFind,
  editorFindStep,
  editorFindSetCurrent,
  codeWindowRefresh,
  editorCaretModelPos,
} from "/js/ui/codeeditor.js";

// 模块态：当前目录 / 扁平清单（中栏状态在 codeeditor.js）
let codeDir = "";
let codeFiles = [];
// codeDirSeq：目录树操作的「最新请求」序号（照 codeeditor.js openSeq 先例）——
// 覆盖**全部**会写模块级 codeFiles / 渲染树 / 写徽章的入口（loadCodeDir、
// checkCodeDiskChanges、refreshCodeTreeOnly）。0 = 从未发起。
// 详见 loadCodeDir 与 probeDiskBaseline 内的竞态注释。
let codeDirSeq = 0;
// claimCodeDirSeq()：(是否最新) 谓词工厂——调用方在**每条 await 之后**重新求值，
// 晚到就早退（一处认领、多处复核，避免每加一个 await 就补一次手写比较）。
// 只比序号：任何**更新**的认领都会让先前认领者的响应作废。
// 目录归属那一半判据不在这里，而在 probeDiskBaseline 内部（它以进入时刻的
// codeDir 为锚点）——因为认领发生在 setCodeDir **之前**（此刻 codeDir 还停在
// 上一个目录），在这里比目录会让每次认领当场自我作废（第十一轮首次实现即栽在
// 这里：目录永远加载不出来，冒烟 1-pre 全红）。
function claimCodeDirSeq() {
  const req = ++codeDirSeq;
  return () => req === codeDirSeq;
}
// 树徽章（code-ide-flow/02）：磁盘基线对比结果 {path → "new"|"modified"}，
// renderCodeTree 交 buildCodeTree/codeTreeHTML 渲染「新/变」徽章。
let codeTreeChanges = {};
// 「磁盘变更」面板数据源（code-ide-flow/03）：待审视变更集（未确认——
// 「清空并确认已看」前保持），面板渲染的单一事实。
let codeDiskChanges = { added: [], modified: [], removed: [] };

function emptyChanges() {
  return { added: [], modified: [], removed: [] };
}

// changesOf(diff)：diff → 变更集（added/modified/removed 快照单源构造——
// 面板数据源与树徽章共用同一形状，评审整改：免三处手工重建漂移）。
function changesOf(diff) {
  return {
    added: diff.added.slice(),
    modified: diff.modified.slice(),
    removed: diff.removed.slice(),
  };
}

// ===== 磁盘基线（工单 code-ide-flow/02 + code-ide-ai/07）=====
// 事实源 = 磁盘基线对比（spec：不消费 fix/task/deepen 事件载荷——那些只有
// main.c diff 或刷新即丢）。localStorage 只进胶水层（fx 无副作用约定，同
// firstep.codeTreeWidth 先例）；store = {dir → {ts, files}}，files 为
// baselineSnapshot 规范化快照；目录隔离 + evict（fx/disk-baseline.js）。
// code-ide-ai/07：files 条目可选项 content = 内容快照（cap 见 fx
// snapshotOf——「打开过的文件」才持有，行级 diff 数据源；maincContent
// 每目录特例已统一入字段，旧数据 migrateBaselineStore 兼容）。
const CODE_BASELINE_KEY = "firstep.codeBaseline";
const CODE_BASELINE_MAX_DIRS = 8;  // LRU 上限（存过多目录的旧基线无意义）

function baselineStoreLoad() {
  try {
    const v = JSON.parse(localStorage.getItem(CODE_BASELINE_KEY) || "{}");
    if (!v || typeof v !== "object" || Array.isArray(v)) return {};
    return migrateBaselineStore(v);   // 旧 maincContent 字段 → files.main.c.content（幂等）
  } catch (e) { return {}; }
}

function baselineStoreSave(store) {
  try { localStorage.setItem(CODE_BASELINE_KEY, JSON.stringify(store)); } catch (e) { /* 静默 */ }
}

// fetchCodeFile(dir, path)：读磁盘文件（/api/code/file 直出）→ 内容字符串；
// 不存在 / 失败 → null（快照与「当前磁盘内容」读取共用单实现）。
async function fetchCodeFile(dir, path) {
  try {
    const data = await apiGet("/api/code/file?dir=" + encodeURIComponent(dir)
      + "&path=" + encodeURIComponent(path));
    return data && typeof data.content === "string" ? data.content : null;
  } catch (e) { return null; }
}

// baselineDiffDisk(dir, files)：当前磁盘清单 vs 已有基线 → diff（**纯计算
// 不推进基线**——基线 = 用户最后确认点，对比只探测；推进只在：首次打开
// 目录建立 / 保存·重载单文件 / 「清空并确认已看」/ 树操作整体对齐）。无
// 基线（首次打开此目录）→ null（调用方建立基线，不感知）。
function baselineDiffDisk(dir, files) {
  const store = baselineStoreLoad();
  const prev = store[dir];
  if (!prev || !prev.files) return null;
  return baselineDiff(prev.files, baselineSnapshot(files));
}

// baselineCommitDisk(dir, files)：确认点整体推进——基线 = 当前磁盘快照
// （首次打开 / 树操作 / 「清空并确认已看」）。code-ide-ai/07：快照 = files
// 条目 content 字段（**派生**——平行清单域已删，评审整改：两形表达同概念
// 有漂移风险）；旧 content 先搬入新快照（防推进把快照丢弃），随后对持有
// content 的文件逐文件 re-fetch 当前内容覆盖（新确认内容 = 行级 diff 基准；
// 文件已不存在 / 读取失败 / 超限 → content=null 保底——无内容无从行级）。
// async：内容需逐文件 /api/code/file。
async function baselineCommitDisk(dir, files) {
  const store = baselineStoreLoad();
  const snap = baselineSnapshot(files);
  const old = store[dir] || {};
  const oldFiles = old.files || {};
  for (const p of Object.keys(oldFiles)) {
    if (Object.prototype.hasOwnProperty.call(snap, p)
      && typeof oldFiles[p].content === "string") {
      snap[p].content = oldFiles[p].content;
    }
  }
  store[dir] = { ts: Date.now(), files: snap };
  for (const p of Object.keys(snap)) {
    if (typeof snap[p].content === "string") {
      snap[p].content = snapshotOf(await fetchCodeFile(dir, p));   // null = 保底
    }
  }
  baselineStoreSave(baselineEvict(store, CODE_BASELINE_MAX_DIRS));
}

// setSnapshotContent(entry, path, snap)：写入文件条目的 content 快照（唯一
// 写点——onFileLoaded 建快照 / baselineUpdateFile 保存推进共用；「持有快照
// 的文件」由 files 派生，无独立清单）。
function setSnapshotContent(entry, path, snap) {
  const files = entry.files || {};
  files[path] = files[path] || {};
  files[path].content = snap;
}

// baselineUpdateFile(dir, path, mtimeNs, sizeBytes, content)：保存 / 重载后
// 基线单条目对齐（下次对比不再把本文件报为「修改」——写盘方 = 本 IDE 自己）。
// content = 用户确认版内容（保存动作的标签内容）——任意文件推进行级快照
// （打开过 = 持有快照的语义下保存必打开过；超限 → null 保底）。旧版本的
// main.c 特例参数已统一为通用字段（code-ide-ai/07 字段统一化）。
function baselineUpdateFile(dir, path, mtimeNs, sizeBytes, content) {
  const store = baselineStoreLoad();
  const entry = store[dir];
  if (!entry || !entry.files) return;
  if (!Object.prototype.hasOwnProperty.call(entry.files, path)) {
    entry.files[path] = {};
  }
  entry.files[path].mtime_ns = String(mtimeNs == null ? "" : mtimeNs);
  entry.files[path].size_bytes = sizeBytes == null ? "" : sizeBytes;
  setSnapshotContent(entry, path, snapshotOf(content));
  entry.ts = Date.now();
  baselineStoreSave(baselineEvict(store, CODE_BASELINE_MAX_DIRS));
}

// onFileLoaded（code-ide-ai/07 快照建立）：打开 = 读盘成功 → 基线建内容
// 快照——「打开过的文件」才有行级 diff 数据源。mtime == 基线 mtime（磁盘
// = 用户确认版）→ 快照 = 读盘内容（零额外读盘——读盘载荷复用）；mtime 不
// 等（外部已改未处理）→ 不动旧快照（保留 diff 基准 = 用户确认版）。从未
// 打开/无基线条目 → 不落快照域。
onFileLoaded((path, content, mtimeNs) => {
  const store = baselineStoreLoad();
  const entry = store[codeDir];
  const bl = entry && entry.files && entry.files[path];
  if (!bl) return;
  if (!mtimeEq(bl.mtime_ns, mtimeNs)) return;
  setSnapshotContent(entry, path, snapshotOf(content));
  baselineStoreSave(baselineEvict(store, CODE_BASELINE_MAX_DIRS));
});

// applyDiskChanges(isCurrent, diff)：基线对比命中 → 联动（spec 1）——干净标签自动
// 重载（计数 → toast）；脏标签置「磁盘已变更」徽章（点徽章弹既有三选，绝不
// 静默——脏标签永不推进，留待用户定夺）；未打开的变更文件留树徽章。树徽章
// = 磁盘改动集合（新增「新」/ 修改「变」），**不因自动重载而消失**——重载
// 只是标签跟上磁盘，用户尚未整体审视（spec 用户故事 2）；「清空并确认已
// 看」（工单 03）/保存/树操作才推进基线让集合收敛。removed 文件标签保留旧
// 内容可继续查看（保存时后端既有错误文案兜底；树重拉后条目自然消失）。
async function applyDiskChanges(isCurrent, diff) {
  const changed = diff.added.concat(diff.modified);
  const dirty = new Set(dirtyTabPaths());
  const open = new Set(openTabPaths());
  let reloaded = 0;
  for (const path of changed) {
    if (!open.has(path)) continue;
    if (dirty.has(path)) {
      setDiskChanged([path]);
      continue;
    }
    try {
      if ((await reloadTabFromDisk(path)) === "reloaded") reloaded++;
    } catch (e) {
      // 磁盘文件已不存在 / 读取失败：保留标签旧内容（验收 4），不打断
    }
  }
  // 逐文件重载含 await：期间可能已有更新的目录树操作接手 → 旧目录的变更集
  // （徽章 / 面板 / toast）一律不落界面（同 probeDiskBaseline 的守卫理由）
  if (isCurrent && !isCurrent()) return;
  const next = {};
  for (const p of diff.modified) next[p] = TREE_CHANGE_MODIFIED;
  for (const p of diff.added) next[p] = TREE_CHANGE_NEW;
  codeTreeChanges = next;
  codeDiskChanges = changesOf(diff);
  renderCodeTree();
  // main.c 被外部/AI 改写（含子目录）→ 步骤 8 状态行联动（既有路径）
  if ((diff.modified.concat(diff.added)).some(isMainCPath) && isMainCDiskDir()) {
    refreshMainCDiskState();
  }
  renderChangePanel();   // fire-and-forget（内部 fetch 已各自兜错）
  if (reloaded > 0) {
    toast("ok", reloaded + " 个文件已被外部更新，已自动重载");
  }
}

// probeDiskBaseline(isCurrent, dir)：重拉清单 + 基线探测（纯计算不推进基线；
// 无基线先建立）——loadCodeDir 与 checkCodeDiskChanges 共用同一探测序（评审
// 整改：两处同序易漂移）。无基线 → 徽章集合清空（跨目录/首次不残留旧目录徽章
// ——spec：目录隔离不串台）。**不渲染**——渲染由调用方统一（无变更一次 /
// 有变更 applyDiskChanges 内一次，评审整改：消灭双次渲染）。
//
// 晚到响应守卫（第十一轮 CDP 取证定位的第二个目录竞态，两次失败现场完全同形）：
// 本函数**无条件**写模块级 `codeFiles`，而它的触发点不止 loadCodeDir 一个——
// 切到「代码」tab 的导航点击也会调 checkCodeDiskChanges()。实测的失败序列：
//   ① openCodeViewer(B) 里 `btn.click()` **同步**触发 checkCodeDiskChanges()
//      （此刻 codeDir 还是 A）→ 对 A 发起探测；
//   ② 随后才 setCodeDir(B) 把 codeDir 改成 B + 对 B 发起探测；
//   ③ 后发起的 B 先返回（7ms）、先发起的 A 后返回（10ms）→ A 的响应把
//      `codeFiles` 覆盖成 A 的清单，而 loadCodeDir 的 stale 判定早已在
//      A 返回**之前**通过 → 树渲染出 `main.c`（A 的文件）而标签显示 b。
//      用户在 B 里点 other.c 自然点不到（树里根本没有这个节点）→「没有活动
//      标签 / 编辑器空白」，与第九轮登记的签名 ① 同一表象、不同成因。
// 修法：写 `codeFiles` 之前先复核守卫——`isCurrent` 由调用方用
// claimCodeDirSeq() 认领（loadCodeDir / checkCodeDiskChanges 各持一个），
// 晚到响应连清单都不写（新请求的清单绝不能被旧响应覆盖）。
async function probeDiskBaseline(isCurrent, dir) {
  // 本探测只回答「目录 dir 的清单与基线」——认领者可能已经走到别的目录
  // （loadCodeDir 等三选确认时 codeDir 还停在上一个目录）。故这里以**进入时刻**
  // 的 codeDir 作为目录判据锚点：之后只要 codeDir 变了（用户已切走），本次结果
  // 就作废，绝不写进模块态。
  const target = codeDir;
  const mine = () => (isCurrent ? isCurrent() : true) && codeDir === target;
  const data = await apiPost("/api/code/open", { dir });
  if (!mine()) return null;   // 晚到：清单写入与基线都不做
  codeFiles = data.files || [];
  const diff = baselineDiffDisk(dir, codeFiles);
  if (diff === null) {
    await baselineCommitDisk(dir, codeFiles);
    if (!mine()) return null;
    codeTreeChanges = {};
    codeDiskChanges = emptyChanges();
  }
  return diff;
}

// checkCodeDiskChanges()：切回「代码」tab / 显式刷新入口——重扫磁盘对比
// 基线，命中 → applyDiskChanges（loadCodeDir 成功与 refreshCodeTreeOnly
// 之外的第三触发点；与 index.html tab 切换钩子接线）。
// 与 loadCodeDir **共用同一守卫**：本函数在 tab 点击时同步发起，极易与紧随
// 其后的 loadCodeDir（同一动作里的 openCodeViewer）交叠——认领序号后，
// 任何 await 落到晚到一侧就不再渲染/不写徽章（避免用旧目录的 diff 抹掉新
// 目录的树与徽章）。
export async function checkCodeDiskChanges() {
  if (!codeDir) return;
  const isCurrent = claimCodeDirSeq();
  try {
    const diff = await probeDiskBaseline(isCurrent, codeDir);
    if (!isCurrent()) return;   // 期间已有更新的目录树操作：本次结果作废
    if (diff && baselineHasChanges(diff)) {
      await applyDiskChanges(isCurrent, diff);
    } else {
      codeTreeChanges = {};   // 变更已收敛（无 diff）：不残留旧徽章
      codeDiskChanges = emptyChanges();
      renderCodeTree();
      renderChangePanel();
    }
  } catch (e) {
    if (!isCurrent()) return;
    toastError(e, "刷新文件变化失败");
  }
}

// ===== 「磁盘变更」面板（工单 code-ide-flow/03）=====
// buildChangeEntries()：待审视变更集 → 面板条目（status/path/mtime/size；
// 元数据取自当前清单 codeFiles——removed 条目清单里没有，只剩 path）。
function buildChangeEntries() {
  const byPath = {};
  for (const f of codeFiles) byPath[f.path] = f;
  const makeEntry = (status, path) => {
    const f = byPath[path] || {};
    return {
      status,
      path,
      mtime_ns: f.mtime_ns == null ? "" : String(f.mtime_ns),
      size_bytes: f.size_bytes == null ? "" : f.size_bytes,
    };
  };
  return codeDiskChanges.added.map((p) => makeEntry("added", p))
    .concat(codeDiskChanges.modified.map((p) => makeEntry("modified", p)))
    .concat(codeDiskChanges.removed.map((p) => makeEntry("removed", p)));
}

// getBaselineContent(dir, path, loaded)：基线条目的 content 快照（用户确认
// 版）——行级 diff 的旧内容；无快照 / 超限 → null（打开过的 ≤cap 文件才
// 有）。loaded 可选（渲染循环外 load 一次复用——评审整改：逐条目重解析
// localStorage 属 O(n) 重复）。
function getBaselineContent(dir, path, loaded) {
  const store = loaded || baselineStoreLoad();
  const entry = store[dir] || {};
  const bl = (entry.files || {})[path] || {};
  return typeof bl.content === "string" ? bl.content : null;
}

// renderChangePanel()：面板渲染（条目 HTML + 摘要 + 显隐）——行级 diff 区
// 泛化（工单 code-ide-ai/08）：任何 modified 且基线有 content 快照的条目
// （打开过的文件）补行级 diff（基线快照 vs 当前磁盘；main.c 与其它文件同
// 一渲染——isMainCPath 限制移除）；快照/当前内容任一缺失 → 纯件占位。
// 无变更 → 面板隐藏。空态由面板自身收起（列表空 + hidden）。
async function renderChangePanel() {
  const panelEl = $("code-change-panel");
  const listEl = $("code-change-list");
  const summaryEl = $("code-change-summary");
  if (!panelEl || !listEl) return;
  const entries = buildChangeEntries();
  if (!entries.length) {
    hidePanel("change");
    listEl.innerHTML = "";
    if (summaryEl) summaryEl.textContent = "";
    return;
  }
  // 行级 diff 数据源（hasLineDiffSource = modified 且基线有旧版快照——打开
  // 过的文件）：旧快照（getBaselineContent）vs 当前磁盘 → lineDiffCompute；
  // 任一缺失 → 仅置源标志（纯件占位文案）。
  const store = baselineStoreLoad();
  for (const e of entries) {
    if (e.status !== "modified") continue;
    const oldContent = getBaselineContent(codeDir, e.path, store);
    if (oldContent === null) continue;
    e.hasLineDiffSource = true;
    const curContent = await fetchCodeFile(codeDir, e.path);
    if (typeof curContent === "string") {
      e.mainDiff = lineDiffCompute(oldContent, curContent);   // null = 无差异/超限 → 占位
    }
  }
  listEl.innerHTML = changesPanelHTML(entries);
  if (summaryEl) summaryEl.textContent = changeSummaryText(entries);
  showPanel("change");
}

// clearCodeDiskChanges()：「清空并确认已看」——基线推进为当前磁盘快照
// （含 main.c 内容快照），待看清单/树徽章/标签「磁盘已变更」徽章全部清空；
// 此后同类外部变更不再报（无变化）；外部再改 → 重新感知。
export async function clearCodeDiskChanges() {
  if (!codeDir) return;
  // 与 loadCodeDir / checkCodeDiskChanges 共用同一守卫（第十一轮）：本函数在
  // `await baselineCommitDisk` 之后渲染树，期间可能已切换目录（旧目录的徽章/
  // 树不该落回新目录的界面）。
  const isCurrent = claimCodeDirSeq();
  const stalePaths = Object.keys(codeTreeChanges);
  codeTreeChanges = {};
  codeDiskChanges = emptyChanges();
  for (const p of stalePaths) clearDiskChanged(p);
  await baselineCommitDisk(codeDir, codeFiles);
  if (!isCurrent()) return;
  renderCodeTree();
  await renderChangePanel();
  if (!isCurrent()) return;
  toast("ok", "已确认磁盘变更：待看清单已清空");
}

// 跳行/缩放浮标共用闪烁时延（评审整改（工单 code-viewer/09）：1200 三处归拢）
const CODE_FLASH_MS = 1200;

// 树面板拖拽调宽（工单 code-viewer-tree-resize/01）：宽度持久化键——
// localStorage 只进胶水层（fx 无副作用约定，同 firstep.mainc.zoom 先例）。
const CODE_TREE_W_KEY = "firstep.codeTreeWidth";
const CODE_TREE_WIDTH_STEP = 16;  // 键盘 ←/→ 步进（spec：16px 微调）

export function codeTabActive() {
  const sec = $("tab-code");
  return !!(sec && sec.classList.contains("active"));
}

// openCodeViewer(dir, filePath?)：外部桥（最近记录卡「查看代码」/ 生成页
// 结果区 chips / 步骤 8「编辑 main.c」）——先切到「代码」tab 再加载目录；
// filePath 非空时目录加载完成后直接打开该文件（复用 openEditorFile，md 走
// 默认态）；dir 为空 → toast 中文。
export function openCodeViewer(dir, filePath) {
  const btn = document.querySelector('nav button[data-tab="code"]');
  if (btn) btn.click();
  loadCodeDir(dir || "", filePath || "");
}

async function loadCodeDir(dir, filePath) {
  if (!dir) { toast("error", "目录为空：无法打开（请从最近记录或「选择文件夹」进入）"); return; }
  // 目录加载竞态（第十/十一轮 CDP 取证定位，两轮各一半）：
  // ① 两次 loadCodeDir 交叠时（快速连点两个目录 / 外部桥连发），后发起的请求
  //    通常先返回，而**先发起的晚到响应**会写回模块级 `codeFiles` → 树被旧
  //    目录的清单覆盖（标签显示新目录、树里还是旧目录的文件，用户点不到目标
  //    文件 =「点了没反应」）；
  // ② 触发点不止本函数——openCodeViewer 先 `btn.click()` 切 tab，那会**同步**
  //    调 checkCodeDiskChanges()，此刻 codeDir 还是上一个目录 → 对旧目录发起
  //    探测，其晚到响应同样覆盖 `codeFiles`（第十一轮实测现场：label=b 而
  //    treeFiles=["main.c"]，两次失败完全同形）。
  // 修法照 openEditorFile 的 openSeq 先例：**统一序号**——本函数与
  // checkCodeDiskChanges / refreshCodeTreeOnly 共用 claimCodeDirSeq()，只有最新
  // 一次认领者的响应可以提交状态（清单 / 徽章 / 渲染 / 错误 / 打开指定文件）；
  // 晚到者直接丢弃（用户意图已变，旧目录的任何状态都不该落回界面）。序号在本
  // 函数**最前面**认领（早于 setCodeDir 的三选确认等待），这样「切目录等待用户
  // 确认」期间旧目录的晚到响应也不会落回界面；目录归属那一半判据在
  // probeDiskBaseline 内锚定（见该函数注释）。
  const isCurrent = claimCodeDirSeq();
  // 未保存退出保护（工单 code-editor-refine/01）：setCodeDir 内有脏标签 →
  // 三选确认（保存全部并切换 / 放弃修改并切换 / 取消）；取消或保存未落盘 →
  // 返回 false，不切换目录（编辑保留）。网络请求放确认之后——避免白拉树。
  // 注意：**不要**在 setCodeDir 之前抢先赋 codeDir —— 守卫的第 ② 条判据是
  // 「认领时与现在的 codeDir 是否相同」，抢跑会让本次认领当场自我作废
  // （第十一轮首次实现即栽在这里：目录永远加载不出来，冒烟 1-pre 全红）。
  const switched = await setCodeDir(dir);
  // 取消 / 保存未落定：目录没换 → 界面一概不动（**先前**的实现已把树清成
  // 「加载中…」，取消后停在占位上是可见缺陷；清树已移到探测成功之后，见下）
  if (!switched) return;
  codeDir = dir;
  $("code-dir-label").textContent = dir;
  setCodeAiDir(dir);  // AI 对话面板（code-ide-ai/03）：跟随目录显示 + 拉历史
  updateGotoGenerateVisibility();
  $("code-tree").innerHTML = '<span class="muted">加载中…</span>';
  try {
    // code-ide-flow/02：基线探测——首次打开建基线（无感知）；已打开过 →
    // 对比旧基线感知（上次会话/外部编辑器改过）→ 联动（干净重载 / 脏标签
    // 徽章 / 树徽章）。基线**不**随打开推进——diff 是待审视变更集，用户
    // 点「清空并确认已看」（工单 03）才整体确认（spec 用户故事 2）。
    const diff = await probeDiskBaseline(isCurrent, codeDir);
    if (!isCurrent()) return;   // 期间已发起更新的目录树操作：本次结果作废
    renderOutline();
    renderSearchResults([]);
    $("code-find-input").value = "";
    $("code-find-results").innerHTML = '<span class="muted">在当前文件内查找</span>';
    if (diff && baselineHasChanges(diff)) {
      await applyDiskChanges(isCurrent, diff);   // 内部渲染树（带「新/变」徽章）+ 变更面板
    } else {
      codeTreeChanges = {};           // 跨目录/无变更：不残留上一目录徽章
      codeDiskChanges = emptyChanges();
      renderCodeTree();
      renderChangePanel();
    }
    if (filePath) await openEditorFile(filePath);   // 外部桥指定文件：目录就位后直接打开（工单 code-editor-utilize/01）
  } catch (e) {
    if (!isCurrent()) return;   // 旧目录的失败不该把新目录的树写成错误态
    codeFiles = [];
    $("code-tree").innerHTML = '<div class="error">加载失败：' + esc(e.message) + "</div>";
    toastError(e, "打开目录失败");
  }
}

// isMainCDiskDir()：当前打开目录 === 生成上下文目录（单源谓词——「去生成页
// 编辑 main.c」可见性、main.c 保存联动与代码栏编译引导共用，防多处漂移；
// code-tab-compile/03 起 export：ui/code-compile.js 直接 import 同一实现）。
export function isMainCDiskDir() {
  return !!codeDir && codeDir === getMainCDiskDir();
}

// updateGotoGenerateVisibility()：当前打开目录 === 生成上下文目录 → 顶栏
// 「去生成页编辑 main.c」可见（mainc-codeview-bridge/03 双向跳转桥——生成页
// 步骤 8 仍是 main.c 编辑入口之一，编辑器与步骤 8 双入口共存）。
function updateGotoGenerateVisibility() {
  const btn = $("btn-code-goto-generate");
  if (!btn) return;
  btn.classList.toggle("hidden", !isMainCDiskDir());
}

function renderCodeTree() {
  const box = $("code-tree");
  const nodes = buildCodeTree(codeFiles, codeTreeChanges);
  box.innerHTML = nodes.length
    ? '<ul class="code-tree">' + codeTreeHTML(nodes) + "</ul>"
    : '<span class="muted">（没有文件）</span>';
}

// refreshCodeTreeOnly()：仅重拉清单 + 重渲染树（工单 code-tree-ops/02）——
// 树操作（新建/重命名/删除）成功后刷新用；**不**碰中栏标签/内容（相对
// loadCodeDir：后者会 setCodeDir 清全部标签，树操作不能丢编辑态）。
// code-ide-flow/02：树操作是用户在本 IDE 内主动改盘——基线整体对齐为当前
// 快照（不视为外部变更，徽章清空），避免下次对比把自己改的报「修改」。
export async function refreshCodeTreeOnly() {
  if (!codeDir) return;
  // 与 loadCodeDir / checkCodeDiskChanges 共用同一守卫（第十一轮）：树操作触发的
  // 重拉同样可能被并发目录加载的晚到响应覆盖（或反之），认领序号后逐 await 复核。
  const isCurrent = claimCodeDirSeq();
  try {
    const data = await apiPost("/api/code/open", { dir: codeDir });
    if (!isCurrent()) return;   // 期间已切换目录：旧目录的清单不落界面
    codeFiles = data.files || [];
    await baselineCommitDisk(codeDir, codeFiles);
    if (!isCurrent()) return;
    codeTreeChanges = {};
    codeDiskChanges = emptyChanges();
    renderCodeTree();
    renderChangePanel();
  } catch (e) {
    if (!isCurrent()) return;
    toastError(e, "刷新文件树失败");
  }
}

// getCodeTreeDir() / getCodeTreeFiles()：当前目录与清单只读出口（工单
// code-tree-ops/02：树操作判定 is_dir / 组装请求 payload）。
export function getCodeTreeDir() { return codeDir; }
export function getCodeTreeFiles() { return codeFiles; }

// ===== 右侧栏：大纲（活动标签来自 codeeditor） =====
// outlineSelIdx：过滤态「当前选中」符号索引（Enter 跳它；↑/↓ 移动，循环）。
let outlineSelIdx = 0;

function applyOutlineSel() {
  const btns = document.querySelectorAll("#code-outline .code-outline-item");
  btns.forEach((b, i) => b.classList.toggle("on", i === outlineSelIdx));
  const cur = btns[outlineSelIdx];
  if (cur) cur.scrollIntoView({ block: "nearest" });
}

function renderOutline() {
  const box = $("code-outline");
  const tab = getActiveTab();
  if (!tab) {
    box.innerHTML = '<span class="muted">打开 .c/.h / .md 文件后显示函数 / 宏 / include（.md 为标题）</span>';
    return;
  }
  const filter = $("code-outline-filter");
  const q = filter ? (filter.value || "") : "";
  if (q) {
    const hits = symbolFilter(tab.outline, q);
    if (!hits.length) {
      outlineSelIdx = 0;
      box.innerHTML = '<div class="muted code-side-empty">无匹配符号</div>';
      return;
    }
    if (outlineSelIdx >= hits.length) outlineSelIdx = 0;
    box.innerHTML = outlineHTML(hits);
    applyOutlineSel();
    return;
  }
  outlineSelIdx = 0;
  box.innerHTML = tab.outline && tab.outline.length
    ? outlineHTML(tab.outline)
    : outlineEmptyHTML();
}

// ===== 右侧栏：跨文件搜索 =====
async function runProjectSearch(q) {
  const needle = String(q || "").trim();
  if (!needle) { renderSearchResults([]); return; }
  const box = $("code-search-results");
  box.innerHTML = '<span class="muted">搜索中…</span>';
  try {
    const data = await apiGet("/api/code/search?dir=" + encodeURIComponent(codeDir)
      + "&q=" + encodeURIComponent(needle));
    renderSearchResults(data.hits || [], data);
  } catch (e) {
    box.innerHTML = '<div class="error">搜索失败：' + esc(e.message) + "</div>";
    toastError(e, "搜索失败");
  }
}

function renderSearchResults(hits, data) {
  const box = $("code-search-results");
  const active = getActiveTab();
  box.innerHTML = '<ul class="code-side-summary">'
    + `<li><span class="muted">${(hits || []).length} 条命中${data && data.truncated ? "（已达上限）" : ""}${data ? " · 扫描 " + data.files_scanned + " 个文件" : ""}</span></li>`
    + "</ul>" + searchListHTML(hits, active ? active.path : "");
}

// ===== 右侧栏：当前文件 Ctrl+F（数据 = codeeditor 活动标签内容） =====
function renderFindPanel(q, lineHits) {
  const box = $("code-find-results");
  const tab = getActiveTab();
  if (!tab) { box.innerHTML = ""; return; }
  if (!q) { box.innerHTML = '<span class="muted">在当前文件内查找</span>'; return; }
  if (!lineHits.length) { box.innerHTML = '<span class="muted">当前文件没有匹配</span>'; return; }
  box.innerHTML = '<ul class="code-find-list">' + lineHits.map((n) =>
    `<li><button type="button" class="code-find-item" data-find-line="${n}">
        <span class="code-search-path">第 ${esc(n)} 行</span>
        <span class="code-search-text">${esc(String(tab.content.split("\n")[n - 1] || "").trim().slice(0, 80))}</span></button></li>`)
    .join("") + "</ul>";
}

function refreshFindPanel() {
  const input = $("code-find-input");
  const tab = getActiveTab();
  renderFindPanel(input ? input.value || "" : "",
    tab ? fileFindFilter(tab.content.split("\n"), input ? input.value || "" : "") : []);
}

// updateFindCount(status, q)：计数文案——无查询隐藏；有查询无命中显示
// 「无匹配」（评审整改 04：不隐藏，让用户知道查了但没中）；有命中
// 「第 N / 共 M 处」。同时同步替换按钮可用态（工单 code-page-vscode-overhaul/03
// 在途盘点补口）：无查询或无命中 = 禁用，避免「点了才弹 toast」。
const REPLACE_BUTTON_IDS = [
  "btn-code-replace-one", "btn-code-replace-next", "btn-code-replace-all",
];

function setReplaceButtonsDisabled(disabled) {
  for (const id of REPLACE_BUTTON_IDS) {
    const btn = $(id);
    if (btn) btn.disabled = disabled;
  }
}

function updateFindCount(status, q) {
  const el = $("code-find-count");
  setReplaceButtonsDisabled(!(q && status && status.total));
  if (!el) return;
  if (!q) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.classList.remove("hidden");
  el.textContent = status.total
    ? "第 " + (status.current + 1) + " / 共 " + status.total + " 处"
    : "无匹配";
}

// applyEditorFind(q)：查询值 → 编辑器标记层 + 查找计数 + 替换计数
// （「将替换 N 处」）单入口（输入 / 标签切换 / 替换后刷新共用）。
function applyEditorFind(q) {
  const status = setEditorFind(q || "");
  updateFindCount(status, q || "");
  const rc = $("code-replace-count");
  if (rc) {
    if (q && status.total) {
      rc.classList.remove("hidden");
      rc.textContent = "将替换 " + status.total + " 处";
    } else {
      rc.classList.add("hidden");
      rc.textContent = "";
    }
  }
}

// ===== 代码字号缩放（工单 code-viewer-zoom/01） =====
// Ctrl/Cmd+滚轮缩放（只读视图与编辑器同容器）：上滚放大 / 下滚缩小，
// 80%–200%、每档 10%（codeZoomClamp / parseZoomStored 复用 fx/code.js
// 单源）。机制 = .code-gutter-line / .code-hl / .code-ta 的 font-size 均
// `calc(13px * var(--code-zoom, 1))`（index.html 单源），本层只写
// #code-viewer 容器 inline 变量——重渲染不影响容器自身 style（缩放跟会话
// 不跟文件）；值持久化到 firstep.codeViewZoom；缩放时右上角浮出当前百分比
// （1.2s 淡出）。
const CODE_VIEW_ZOOM_KEY = "firstep.codeViewZoom";
const CODE_VIEW_ZOOM_STEP = 10;
const CODE_VIEW_ZOOM_ACC = 40;   // 滚轮累积阈值：高 DPI 鼠标/触控板多事件档
let codeZoomBadge = null;
let codeZoomBadgeTimer = 0;
let codeZoomAcc = 0;

function currentCodeZoomPct() {
  const view = $("code-viewer");
  const raw = parseFloat(view ? view.style.getPropertyValue("--code-zoom") : "");
  return raw > 0 ? Math.round(raw * 100) : 100;
}

// refreshCodeStatus()：底部状态栏信息区刷新（工单 code-editor-vscode-polish/01）
// ——活动标签的 Ln/Col（读 textarea 选区，readonly 同样可取）/ 语言 / 编码 /
// 缩进 / 缩放；无活动文件 → 显示「未打开文件」占位。触发点：活动标签变化
// （onActiveTabChanged）、光标/选区变化（onCursorChanged）、缩放（applyCodeZoom）、
// 初始化。行列计算走 editorCaretModelPos 单源（codeeditor 换算，折叠态为模型行/列）。
function refreshCodeStatus() {
  const bar = $("code-statusbar-info");
  if (!bar) return;
  const tab = getActiveTab();
  if (!tab) {
    bar.innerHTML = '<span class="code-statusbar-empty">未打开文件</span>';
    return;
  }
  const ta = document.querySelector("#code-viewer .code-ta");
  let line = 1;
  let col = 1;
  if (ta) {
    // 折叠态（工单 07）：状态栏显示模型行/列（视图行号与模型行号不同）——
    // editorCaretModelPos 由 codeeditor 统一换算（视图偏移 → 模型偏移）。
    const p = editorCaretModelPos();
    line = p.line;
    col = p.col;
  }
  bar.innerHTML = codeStatusHTML({
    line,
    col,
    lang: tab.lang,
    utf8: tab.utf8,
    indent: 4,
    zoomPct: currentCodeZoomPct(),
  });
}

function showCodeZoomBadge(pct) {
  if (!codeZoomBadge) {
    const view = $("code-viewer");
    const pane = view && view.closest(".code-pane-main");
    if (!pane) return;
    codeZoomBadge = document.createElement("div");
    codeZoomBadge.className = "code-zoom-badge";
    codeZoomBadge.setAttribute("aria-hidden", "true");
    pane.appendChild(codeZoomBadge);
  }
  codeZoomBadge.textContent = pct + "%";
  codeZoomBadge.classList.add("show");
  clearTimeout(codeZoomBadgeTimer);
  codeZoomBadgeTimer = setTimeout(() => codeZoomBadge.classList.remove("show"), CODE_FLASH_MS);
}

function applyCodeZoom(pct) {
  const view = $("code-viewer");
  if (!view) return;
  pct = codeZoomClamp(pct);
  view.style.setProperty("--code-zoom", String(pct / 100));
  try { localStorage.setItem(CODE_VIEW_ZOOM_KEY, String(pct)); } catch (e) {}
  showCodeZoomBadge(pct);
  codeWindowRefresh();   // 行高变化 → 重测并重画窗口（工单 08 滚动窗口化）
  refreshCodeStatus();   // 状态栏缩放百分比实时刷新（工单 01）
}

function initCodeViewZoom() {
  const view = $("code-viewer");
  if (!view) return;
  let pct = 100;
  try { pct = parseZoomStored(localStorage.getItem(CODE_VIEW_ZOOM_KEY)); } catch (e) {}
  view.style.setProperty("--code-zoom", String(pct / 100));
  view.addEventListener("wheel", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    codeZoomAcc += e.deltaY;
    if (Math.abs(codeZoomAcc) < CODE_VIEW_ZOOM_ACC) return;
    const dir = codeZoomAcc < 0 ? CODE_VIEW_ZOOM_STEP : -CODE_VIEW_ZOOM_STEP;  // 上滚放大
    codeZoomAcc = 0;
    applyCodeZoom(currentCodeZoomPct() + dir);
  }, { passive: false });
}

// ===== 树面板拖拽调宽（工单 code-viewer-tree-resize/01） =====
function codeLayoutEl() {
  return document.querySelector(".code-layout");
}

function applyTreeWidth(px, persist) {
  const layout = codeLayoutEl();
  if (!layout) return;
  const w = treeWidthClamp(px, layout.getBoundingClientRect().width);
  layout.style.setProperty("--code-tree-w", w + "px");
  if (persist) {
    try { localStorage.setItem(CODE_TREE_W_KEY, String(w)); } catch (e) { /* 静默 */ }
  }
}

function restoreTreeWidth() {
  const layout = codeLayoutEl();
  if (!layout) return;
  let raw = null;
  try { raw = localStorage.getItem(CODE_TREE_W_KEY); } catch (e) { raw = null; }
  applyTreeWidth(parseTreeWidthStored(raw, layout.getBoundingClientRect().width), false);
}

function currentTreeWidth(layout) {
  return parseInt(layout.style.getPropertyValue("--code-tree-w"), 10)
    || CODE_TREE_WIDTH_DEFAULT;
}

function initCodeTreeResize() {
  const handle = $("code-tree-resize");
  const layout = codeLayoutEl();
  if (!handle || !layout) return;
  let dragging = false;

  handle.addEventListener("pointerdown", (e) => {
    dragging = true;
    try { handle.setPointerCapture(e.pointerId); } catch (e) { /* 合成事件：忽略 */ }
    document.body.classList.add("code-resizing");
  });
  handle.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    applyTreeWidth(e.clientX - layout.getBoundingClientRect().left, false);
  });
  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove("code-resizing");
    const cur = layout.style.getPropertyValue("--code-tree-w");
    applyTreeWidth(parseInt(cur, 10) || CODE_TREE_WIDTH_DEFAULT, true);
  };
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);
  handle.addEventListener("dblclick", () => applyTreeWidth(CODE_TREE_WIDTH_DEFAULT, true));
  handle.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const cur = layout.style.getPropertyValue("--code-tree-w") || "240px";
      applyTreeWidth((parseInt(cur, 10) || CODE_TREE_WIDTH_DEFAULT)
        + (e.key === "ArrowLeft" ? -16 : 16), true);
    } else if (e.key === "Home") {
      e.preventDefault();
      applyTreeWidth(CODE_TREE_WIDTH_DEFAULT, true);
    } else if (e.key === "End") {
      e.preventDefault();
      applyTreeWidth(CODE_TREE_WIDTH_MAX, true);
    }
  });
}

// ===== 侧栏收起/展开（工单 code-viewer-editor/07）：右侧栏贴右缘 40px
// 竖向轨道（收起）↔ 300px 面板（展开）——点活动页签收起、点轨道条目展开、
// Ctrl+F 强制展开；localStorage 持久化（只进胶水层，fx 无副作用约定同
// firstep.codeTreeWidth 先例）。 =====
const CODE_SIDE_COLLAPSE_KEY = "firstep.codeSideCollapsed";  // "1" = 收起

let activeSide = "outline";

function codeSideLayout() {
  return document.querySelector(".code-layout");
}

// setCodeSideCollapsed(collapsed, persist)：单一路径——.side-collapsed 类
// 驱动 grid 列（--code-side-w 300 ↔ 40），轨道的 on 高亮跟随活动页。
function setCodeSideCollapsed(collapsed, persist) {
  const layout = codeSideLayout();
  if (!layout) return;
  layout.classList.toggle("side-collapsed", !!collapsed);
  document.querySelectorAll(".code-side-rail-btn").forEach((b) =>
    b.classList.toggle("on", b.dataset.codeSide === activeSide));
  if (persist) {
    try { localStorage.setItem(CODE_SIDE_COLLAPSE_KEY, collapsed ? "1" : "0"); } catch (e) { /* 静默 */ }
  }
}

function restoreCodeSideCollapsed() {
  let raw = null;
  try { raw = localStorage.getItem(CODE_SIDE_COLLAPSE_KEY); } catch (e) { raw = null; }
  setCodeSideCollapsed(raw === "1", false);
}

// ===== 侧栏切换（大纲 / 搜索）：按钮与 Ctrl+F 共用同一生效路径
// （评审整改：Ctrl+F 必须可见地切到「搜索」栏，否则聚焦隐藏输入框）。
// 收起态点轨道条目 = 先展开再切换；展开态点活动页签 = 收起。 =====
function setCodeSide(side) {
  activeSide = side;
  document.querySelectorAll("[data-code-side]").forEach((x) =>
    x.classList.toggle("on", x.dataset.codeSide === side));
  document.querySelectorAll("[data-code-side-panel]").forEach((p) =>
    p.classList.toggle("hidden", p.dataset.codeSidePanel !== side));
}

// syncInfoBar()：信息条空态折叠单源——三动作按钮（返回预览/编辑源码/保存）
// 全隐藏 → .empty（display:none，不占 30px 空带）。按钮可见性所有路径
// （openEditorFile/setMdMode/applySavedState/closeTab）均经 notifyActive 汇聚
// onActiveTabChanged 回调调用本函数；**初始空态（未打开目录/无活动 tab）回调
// 从未触发——init 显式调用一次**（用户反馈「中间那行黑的空隙」= 空态信息条）。
function syncInfoBar() {
  const pathBar = document.querySelector(".code-file-path");
  if (!pathBar) return;
  const anyShown = [$("code-back-preview"), $("code-edit-md"), $("btn-code-save")]
    .some((b) => b && !b.classList.contains("hidden"));
  pathBar.classList.toggle("empty", !anyShown);
}

// ===== 面包屑（工单 code-page-vscode-overhaul/05）=====
// 活动标签路径 → 分段纯件渲染；无活动标签隐藏（不占位）。目录段点击 →
// revealTreePath 定位文件树；文件段点击 → 打开文件。
function renderBreadcrumb() {
  const nav = $("code-breadcrumb");
  if (!nav) return;
  const tab = getActiveTab();
  const segs = tab ? breadcrumbSegments(tab.path) : [];
  nav.classList.toggle("hidden", !segs.length);
  nav.innerHTML = segs.length ? breadcrumbHTML(segs) : "";
}

// revealTreePath(dirPath)：逐级展开目录 details（data-dir-path，工单 05 新增）
// → 滚动到目标并临时高亮（.code-tree-reveal 动画后自动清除）。
function revealTreePath(dirPath) {
  const box = $("code-tree");
  if (!box || !dirPath) return;
  const parts = String(dirPath).split("/").filter(Boolean);
  let acc = "";
  for (const d of parts) {
    acc = acc ? acc + "/" + d : d;
    const el = box.querySelector(`details[data-dir-path="${CSS.escape(acc)}"]`);
    if (el) el.open = true;
  }
  const target = box.querySelector(`details[data-dir-path="${CSS.escape(dirPath)}"]`)
    || box.querySelector(`[data-code-file="${CSS.escape(dirPath)}"]`);
  if (!target) return;
  target.scrollIntoView({ block: "center" });
  target.classList.add("code-tree-reveal");
  setTimeout(() => {
    box.querySelectorAll(".code-tree-reveal").forEach((el) => el.classList.remove("code-tree-reveal"));
  }, 1200);
}

// ===== initCodeViewer：入口绑定（host 启动区调用） =====
export function initCodeViewer() {
  const pick = $("btn-code-pick-dir");
  if (pick) pick.addEventListener("click", async () => {
    try {
      const data = await apiPost("/api/pick-directory");
      if (data && data.path) loadCodeDir(data.path);  // 取消 = path null：静默
    } catch (e) {
      toastError(e, "选择文件夹失败");
    }
  });

  // 双向跳转桥（mainc-codeview-bridge/03）：此目录 = 生成上下文 → 回生成页
  // 步骤 8 编辑磁盘版本 main.c（点击 = 显式意图，加载动作与「从磁盘重新
  // 加载」同源；滚动用 step-nav 统一 scrollToStep(8)）。
  const gotoGen = $("btn-code-goto-generate");
  if (gotoGen) gotoGen.addEventListener("click", async () => {
    const tab = document.querySelector('nav button[data-tab="generate"]');
    if (tab) tab.click();
    scrollToStep(8);
    await loadDiskMainC();
  });

  const tree = $("code-tree");
  if (tree) tree.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-code-file]");
    if (!btn) return;
    openEditorFile(btn.dataset.codeFile);
  });

  // 侧栏切换（大纲 / 搜索）：收起态点轨道条目 = 展开并切换；展开态点活动
  // 页签 = 收起（工单 code-viewer-editor/07）。rail 按钮也带 data-code-side
  // 属性，天然命中同一分支（收起态 = 展开并切换）——不另绑独立监听
  // （评审：避免双重绑定 / 展开态程序化点击先收起再展开的抖动路径）。
  document.querySelectorAll("[data-code-side]").forEach((b) =>
    b.addEventListener("click", () => {
      const layout = codeSideLayout();
      const collapsed = !!(layout && layout.classList.contains("side-collapsed"));
      if (collapsed) {
        setCodeSide(b.dataset.codeSide);
        setCodeSideCollapsed(false, true);
        return;
      }
      if (b.dataset.codeSide === activeSide) {
        setCodeSideCollapsed(true, true);
        return;
      }
      setCodeSide(b.dataset.codeSide);
    }));

  // 显式「收起」按钮（工单 code-viewer-editor/07b）：tab 条右端常驻入口，
  // 不依赖「点活动页签收起」的隐藏捷径（用户反馈无提示太神秘）。
  document.querySelectorAll(".code-side-collapse").forEach((b) =>
    b.addEventListener("click", () => setCodeSideCollapsed(true, true)));

  // 活动标签/内容变化 → 大纲（仅路径变化时重渲——逐键输入不重画大纲）/
  // 文件内查找 / 「返回预览」/「编辑源码」/「保存」按钮可见性联动
  let lastOutlinePath = null;
  onActiveTabChanged(() => {
    const tab = getActiveTab();
    if ((tab ? tab.path : null) !== lastOutlinePath) {
      lastOutlinePath = tab ? tab.path : null;
      renderOutline();
    }
    refreshFindPanel();
    const isMd = !!(tab && tab.lang === "md");
    const btn = $("code-back-preview");
    if (btn) btn.classList.toggle("hidden", !(isMd && tab.mdMode !== "preview"));
    const editMd = $("code-edit-md");
    if (editMd) editMd.classList.toggle("hidden", !(isMd && tab.mdMode === "preview"));
    const save = $("btn-code-save");
    if (save) save.classList.toggle("hidden", !isTabSavable(tab));
    // 信息条空态折叠（工单 code-viewer-editor/07c）：三动作按钮全隐藏 →
    // .empty 不占位（用户反馈「代码第一行上面有一行啥也没有的空行」=
    // 空态信息条占位 30px）。同步点唯一 = 本回调（所有按钮可见性路径
    // openEditorFile/setMdMode/applySavedState 均经 notifyActive 汇聚）。
    syncInfoBar();
    renderBreadcrumb();   // 面包屑随活动标签/路径变化刷新（工单 05）
    refreshCodeStatus();   // 状态栏信息区随活动标签变化刷新（工单 01）
    applyEditorFind(findInput ? findInput.value || "" : "");   // 标记层随标签/内容变化重算（工单 04）
  });

  // 保存成功 → 树节点大小刷新 + 大纲重渲（服务端重算 outline 直用——
  // 路径未变，「路径去重」不会自动重画大纲，此处显式刷新）+ main.c 步骤 8
  // 联动（工单 05：此目录 = 生成上下文 → 状态行差异提示立即可见）
  // code-ide-flow/02：**仅保存**推进基线（用户动作 = 确认点；resp 无
  // content——自动重载的 disk 载荷含 content，不推进——变更集保留至
  // 「清空并确认已看」）+ 取消标签徽章（保存后磁盘 = 我的内容，冲突已决）。
  onFileSaved((tab, resp) => {
    const hit = codeFiles.find((f) => f.path === tab.path);
    if (hit && resp && typeof resp.size_bytes === "number") hit.size_bytes = resp.size_bytes;
    renderCodeTree();
    renderOutline();
    if (resp && !("content" in resp)) {
      // 仅保存（用户动作）推进：基线单条目 + 待看清单移除该文件（未打开过
      // 的 added 文件被保存 = 也确认）+ main.c 内容快照（用户确认版）
      baselineUpdateFile(codeDir, tab.path, resp.mtime_ns, resp.size_bytes, tab.content);
      clearDiskChanged(tab.path);
      if (codeTreeChanges[tab.path]) {
        delete codeTreeChanges[tab.path];
        renderCodeTree();
      }
      const had = codeDiskChanges.added.indexOf(tab.path) >= 0
        || codeDiskChanges.modified.indexOf(tab.path) >= 0;
      codeDiskChanges.added = codeDiskChanges.added.filter((p) => p !== tab.path);
      codeDiskChanges.modified = codeDiskChanges.modified.filter((p) => p !== tab.path);
      if (had) renderChangePanel();
    }
    if (isMainCPath(tab.path) && isMainCDiskDir()) {
      refreshMainCDiskState();
    }
  });

  // 大纲点击跳行（delegation）：.md 预览 / 编辑器/只读源码由 codeeditor 统一；
  // 点击同时把「当前选中」同步到被点条目（后续 Enter 再跳它）。
  const outline = $("code-outline");
  if (outline) outline.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-outline-line]");
    if (!btn) return;
    const items = Array.from(outline.querySelectorAll(".code-outline-item"));
    const i = items.indexOf(btn);
    if (i >= 0) outlineSelIdx = i;
    editJumpToLine(parseInt(btn.dataset.outlineLine, 10));
  });

  // 大纲过滤（工单 code-editor-refine/03）：输入即时重渲（选中回 0）；
  // ↑/↓ 移动「当前选中」（循环）；Enter 跳当前选中行；Esc 清空恢复全量
  // （焦点保持在过滤框，便于连续扫符号）。
  const outlineFilter = $("code-outline-filter");
  if (outlineFilter) {
    outlineFilter.addEventListener("input", () => {
      outlineSelIdx = 0;
      renderOutline();
    });
    outlineFilter.addEventListener("keydown", (e) => {
      const btns = () => document.querySelectorAll("#code-outline .code-outline-item");
      if (e.key === "Enter") {
        e.preventDefault();
        const list = btns();
        const btn = list[outlineSelIdx] || list[0];
        if (btn) editJumpToLine(parseInt(btn.dataset.outlineLine, 10));
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const list = btns();
        if (!list.length) return;
        e.preventDefault();
        outlineSelIdx = e.key === "ArrowDown"
          ? (outlineSelIdx + 1) % list.length
          : (outlineSelIdx - 1 + list.length) % list.length;
        applyOutlineSel();
      } else if (e.key === "Escape") {
        outlineFilter.value = "";
        outlineSelIdx = 0;
        renderOutline();
      }
    });
  }

  // 跨文件搜索：按钮 + Enter 提交
  const btnSearch = $("btn-code-search");
  if (btnSearch) btnSearch.addEventListener("click", () =>
    runProjectSearch($("code-search-input").value));
  const searchInput = $("code-search-input");
  if (searchInput) searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); runProjectSearch(searchInput.value); }
  });

  // 当前文件 Ctrl+F：截获浏览器查找框（仅「代码」tab 内）→ 切到「搜索」
  // 侧栏 → 聚焦输入面板即时过滤；.md 预览态先切源码（行语义需要行号）。
  const findInput = $("code-find-input");
  if (findInput) findInput.addEventListener("input", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");
    refreshFindPanel();
    applyEditorFind(findInput.value);
  });
  // 查找计数循环（工单 04）：Enter / Shift+Enter 上/下一个命中（索引循环 +
  // 当前命中高亮 + 跳转选区）；Esc 清空查询（编辑器标记层同步清除）。
  if (findInput) findInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const st = editorFindStep(e.shiftKey ? -1 : 1);
      if (st) updateFindCount(st, findInput.value);
      return;
    }
    if (e.key === "Escape") {
      findInput.value = "";
      refreshFindPanel();
      applyEditorFind("");
    }
  });
  // focusFindPanel(el)：Ctrl+F / Ctrl+H / 替换按钮共用的侧栏唤起——
  // .md 预览先切源码（行语义需要行号）、展开「搜索」侧栏并聚焦目标输入。
  function focusFindPanel(el) {
    const tab = getActiveTab();
    if (tab && tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");
    setCodeSide("search");
    setCodeSideCollapsed(false, true);   // 收起态必须展开（否则聚焦隐藏输入框）
    el.focus();
    el.select();
  }
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "f") return;
    if (!codeTabActive() || !findInput) return;
    e.preventDefault();
    focusFindPanel(findInput);
  });
  // 全部替换（工单 code-editor-utilize/03）：查找行下「全部替换」按钮 +
  // Ctrl+H 同口径唤起（仅「代码」tab、.md 预览先切源码、展开侧栏聚焦替换
  // 输入）。替换走编辑器模拟手输路径（脏点出现，Ctrl+S 落盘），不自动写盘。
  const replaceInput = $("code-replace-input");
  const replaceBtn = $("btn-code-replace-all");
  if (replaceBtn) replaceBtn.addEventListener("click", () => {
    const tab = getActiveTab();
    if (!tab) { toast("info", "请先打开一个文件再替换"); return; }
    const needle = findInput.value;
    if (!needle) { toast("info", "请先在「当前文件内查找」输入查找内容"); return; }
    if (tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");   // 与 Ctrl+F/H 同口径：预览态先切源码
    const count = replaceAllInActiveFile(needle, replaceInput ? replaceInput.value : "");
    if (count > 0) {
      toast("ok", "已替换 " + count + " 处（Ctrl+S 保存）");
      refreshFindPanel();
      applyEditorFind(needle);   // 替换后标记层按新内容重算（计数可能变，工单 04）
    } else {
      toast("info", tab.readonly ? "只读文件不允许替换" : "当前文件没有匹配");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "h") return;
    if (!codeTabActive() || !replaceInput) return;
    e.preventDefault();
    focusFindPanel(replaceInput);
  });
  // 快捷键补位（工单 code-editor-refine/02）：关闭标签 / Ctrl+B 侧栏开合。
  // 关标签主键 = Ctrl+Alt+W：Ctrl+W 是 Chrome 浏览器级保留键——keydown 根本
  // 不会投递给页面（实测：Chrome 直接关闭标签页，页面零机会 preventDefault），
  // 应用侧无法拦截；Ctrl+Alt+W 实测 Chrome 正常投递且无浏览器动作，W 同义
  // 「Close」。Ctrl+W 分支保留兜底（Firefox/Edge/嵌入环境能投递时同样关标签）。
  // 脏标签由 closeTab 内 confirmModal 处理；模态开启（.ref-files-overlay）时
  // 不并发截获（防与确认弹窗冲突）。Ctrl+B 输入框聚焦不抢键（Tab 陷阱先例：
  // 焦点在查找/过滤框内不打断输入）。
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    const key = e.key.toLowerCase();
    if (key === "w") {
      if (!codeTabActive()) return;
      e.preventDefault();   // 先防浏览器原生关页，再决定行为（模态开启也吞键）
      if (document.querySelector(".ref-files-overlay")) return;
      const activeTab = getActiveTab();
      if (activeTab) closeTab(activeTab.path);
      return;
    }
    if (key === "b") {
      if (!codeTabActive()) return;
      // 输入框豁免 = 侧栏/面板输入框（查找/过滤/替换等 INPUT 与非编辑区
      // 文本域）；编辑器主区 .code-ta 不算豁免（VSCode 同义：编辑中
      // Ctrl+B 也能切侧栏）。
      const target = e.target;
      const inPanelField = target && (target.tagName === "INPUT"
        || (target.tagName === "TEXTAREA" && !target.classList.contains("code-ta")));
      if (inPanelField) return;
      const layout = codeSideLayout();
      if (!layout) return;
      e.preventDefault();
      setCodeSideCollapsed(!layout.classList.contains("side-collapsed"), true);
      return;
    }
    if (key === "o" && e.shiftKey) {
      // 符号速达（工单 code-editor-refine/03）：展开侧栏 → 切大纲 → 聚焦
      // 过滤框全选（再打字即过滤；Ctrl+Shift+O 在过滤框内同样可重按）。
      // 不沿用 Ctrl+B 的「输入框豁免」——符号速达需要任意焦点（含查找
      // 输入框）下都能拉起到过滤框，为有意取舍（VSCode 同义）。
      if (!codeTabActive()) return;
      e.preventDefault();
      setCodeSideCollapsed(false, true);
      setCodeSide("outline");
      const f = $("code-outline-filter");
      if (f) { f.focus(); f.select(); }
    }
  });
  // 替换单个命中 / 替换并跳下一处（工单 code-page-vscode-overhaul/03）：
  // 模型层替换（折叠安全）+ 计数联动；「替换并下一处」聚焦下一命中选区。
  const replaceOneBtn = $("btn-code-replace-one");
  const replaceNextBtn = $("btn-code-replace-next");
  if (replaceOneBtn || replaceNextBtn) {
    const doReplaceOne = (jump) => {
      const tab = getActiveTab();
      if (!tab) { toast("info", "请先打开一个文件再替换"); return; }
      const needle = findInput.value;
      if (!needle) { toast("info", "请先在「当前文件内查找」输入查找内容"); return; }
      if (tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");   // 与 Ctrl+F/H 同口径：预览态先切源码
      const st = replaceOneInActiveFile(replaceInput ? replaceInput.value : "", jump);
      if (!st.replaced) {
        toast("info", tab.readonly ? "只读文件不允许替换" : "当前文件没有匹配");
        return;
      }
      toast("ok", "已替换 1 处（Ctrl+S 保存）");
      // 计数联动：替换后命中数 / 当前索引重算（不重置选区）
      updateFindCount({ total: st.total, current: st.current }, needle);
      const rc = $("code-replace-count");
      if (rc) {
        if (needle && st.total) {
          rc.classList.remove("hidden");
          rc.textContent = "将替换 " + st.total + " 处";
        } else {
          rc.classList.add("hidden");
          rc.textContent = "";
        }
      }
    };
    if (replaceOneBtn) replaceOneBtn.addEventListener("click", () => doReplaceOne(false));
    if (replaceNextBtn) replaceNextBtn.addEventListener("click", () => doReplaceOne(true));
  }
  // 初始态：无查询 = 无命中 → 替换按钮禁用（与计数同源）
  updateFindCount({ total: 0, current: -1 }, "");
  const findBox = $("code-find-results");
  if (findBox) findBox.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-find-line]");
    if (!btn) return;
    const line = parseInt(btn.dataset.findLine, 10);
    editJumpToLine(line);
    // 点击项成为当前命中（工单 code-editor-vscode-polish/04 补口）：计数与
    // 当前高亮跟随点击，不再停在 Enter 循环留下的旧索引。
    const st = editorFindSetCurrent(line);
    updateFindCount(st, findInput ? findInput.value : "");
  });
  // 搜索结果点击跳文件 + 行（delegation）；.md 预览态在 codeeditor 内先切
  // 源码（editJumpToFile）。
  const results = $("code-search-results");
  if (results) results.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-search-path]");
    if (!btn) return;
    editJumpToFile(btn.dataset.searchPath, parseInt(btn.dataset.searchLine, 10));
  });

  // 面包屑点击（delegation，工单 05）：目录段 → 定位树；文件段 → 打开。
  const crumb = $("code-breadcrumb");
  if (crumb) crumb.addEventListener("click", (e) => {
    const dirBtn = e.target.closest("[data-breadcrumb-dir]");
    if (dirBtn) { revealTreePath(dirBtn.dataset.breadcrumbDir); return; }
    const fileBtn = e.target.closest("[data-breadcrumb-file]");
    if (fileBtn) openEditorFile(fileBtn.dataset.breadcrumbFile);
  });

  // 「编辑源码」：.md 预览态 → 编辑态（可修改可保存，工单 05）
  const editMd = $("code-edit-md");
  if (editMd) editMd.addEventListener("click", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md") setMdMode(tab.path, "edit");
  });

  // 「返回预览」：.md 编辑态回渲染预览（脏点保留——内容不回滚）
  const backPreview = $("code-back-preview");
  if (backPreview) backPreview.addEventListener("click", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md") setMdMode(tab.path, "preview");
  });

  // 树面板拖拽调宽（工单 code-viewer-tree-resize/01）
  initCodeTreeResize();
  restoreTreeWidth();

  // 「磁盘变更」面板（工单 code-ide-flow/03）：条目点击跳转打开（removed 为
  // span 置灰天然不可点——委托只认 button[data-change-path]）；「清空并确认
  // 已看」→ 基线推进 + 清单清空；「收起/展开」独立于编译面板。
  const changeList = $("code-change-list");
  if (changeList) changeList.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-change-path]");
    if (btn) openEditorFile(btn.dataset.changePath);
  });
  const changeClear = $("btn-code-change-clear");
  if (changeClear) changeClear.addEventListener("click", () => clearCodeDiskChanges());
  const changeCollapse = $("btn-code-change-collapse");
  if (changeCollapse) changeCollapse.addEventListener("click", () => {
    const p = $("code-change-panel");
    if (!p) return;
    const collapsed = p.classList.toggle("collapsed");
    changeCollapse.textContent = collapsed ? "展开" : "收起";
    changeCollapse.title = collapsed ? "展开变更条目" : "收起变更条目";
  });

  // 侧栏收起态恢复（工单 code-viewer-editor/07）：localStorage 持久化
  restoreCodeSideCollapsed();

  // 信息条空态初始折叠（工单 code-viewer-editor/07e）：初始空态（未打开
  // 目录/无活动 tab）onActiveTabChanged 从未触发——显式同步一次，防 30px
  // 黑色空带残留（用户反馈「中间那行黑的空隙不需要留，直接顶满」）。
  syncInfoBar();

  // 代码字号缩放（工单 code-viewer-zoom/01）
  initCodeViewZoom();

  // 底部面板页签条（工单 code-page-vscode-overhaul/06）：单容器+页签切换
  initCodeBottomPanels();

  // 状态栏信息区（工单 code-editor-vscode-polish/01）：光标/选区变化 → 刷新；
  // 初始空态（未打开目录/无活动 tab）onActiveTabChanged 未触发过——显式刷
  // 一次（占位「未打开文件」，与 syncInfoBar 初始化同因）。
  onCursorChanged(refreshCodeStatus);
  refreshCodeStatus();

  // 快捷键帮助（工单 code-editor-shortcut-help/01）：状态栏「快捷键」按钮 →
  // 居中浮层，内容来自 fx/code-shortcuts.js 单源；关闭三路（× / 遮罩 / Esc）、
  // Tab 焦点循环、关闭后焦点还按钮——交互纪律对齐冲突弹窗（code-viewer-editor/04）。
  // 评审整改（Spec 轴 c）：scKeyHandler 模块级持有当前 onKey——重复打开先
  // detach 旧监听再 remove 旧浮层（直接 remove 会泄漏 Escape 处理器：finish
  // 因 !isConnected 提前 return，旧 onKey 永不卸载）。
  const scBtn = $("btn-code-shortcuts");
  let scKeyHandler = null;
  if (scBtn) scBtn.addEventListener("click", () => {
    if (scKeyHandler) {
      document.removeEventListener("keydown", scKeyHandler);
      scKeyHandler = null;
    }
    document.querySelectorAll(".code-shortcuts-overlay").forEach((o) => o.remove());
    const overlayEl = document.createElement("div");
    overlayEl.className = "ref-files-overlay code-shortcuts-overlay";
    overlayEl.innerHTML = '<div class="ref-files-modal confirm-modal code-shortcuts-modal">'
      + '<div class="ref-files-head"><strong>键盘快捷键</strong>'
      + '<button type="button" class="ref-files-close code-shortcuts-close"'
      + ' title="关闭" aria-label="关闭快捷键帮助">×</button></div>'
      + '<div class="code-shortcuts-body">' + shortcutHelpHTML() + "</div></div>";
    const onKey = (e) => {
      if (e.key === "Escape") { finish(); return; }
      if (e.key === "Tab") {
        const focusables = Array.from(
          overlayEl.querySelectorAll("button, [href], [tabindex]:not([tabindex='-1'])")
        ).filter((el) => !el.disabled && el.offsetParent !== null);
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    const finish = () => {
      if (!overlayEl.isConnected) return;
      document.removeEventListener("keydown", onKey);
      if (scKeyHandler === onKey) scKeyHandler = null;
      overlayEl.remove();
      if (scBtn.isConnected && typeof scBtn.focus === "function") scBtn.focus();
    };
    overlayEl.querySelector(".code-shortcuts-close").addEventListener("click", finish);
    overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) finish(); });
    scKeyHandler = onKey;
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlayEl);
    const closeBtn = overlayEl.querySelector(".code-shortcuts-close");
    if (closeBtn) closeBtn.focus();
  });
}
