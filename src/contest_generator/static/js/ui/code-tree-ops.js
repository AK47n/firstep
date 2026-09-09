// ui/code-tree-ops.js — 代码树操作胶水（工单 code-tree-ops/02）
//
// 树头部「新建文件 / 新建文件夹」+ 每行 ✎/🗑（重命名 / 删除）：
// 输入/确认模态复用 confirmModal（extra 输入框 [data-confirm-value]）→
// /api/code/tree/* → 成功后刷新树 + tab 联动（新建自动打开；重命名路径
// 映射；删除关闭受影响 tab——脏保护两键「保存全部并继续/取消」）。
// 纯件在 fx/code-tree-ops.js；依赖导出面：codeview.js
// （refreshCodeTreeOnly / getCodeTreeDir / getCodeTreeFiles / isMainCDiskDir）
// 与 codeeditor.js（openEditorFile / closeTab / remapOpenTabPaths /
// invalidateFileCache / dirtyTabPaths / openTabPaths / saveAllDirtyTabs）。
import { $, apiPost, toast, toastError, copyText } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import {
  treeNameValidate,
  treeOpAffected,
  treeOpTitle,
  createPromptMessage,
  renamePromptMessage,
  treeOpConfirmMessage,
  treeNamePromptHTML,
  treeCtxItems,
} from "/js/fx/code-tree-ops.js";
import { openContextMenu, closeContextMenu } from "/js/ui/context-menu.js";  // 共享浮层菜单（工单 06 创建 / 07 复用）
import {
  refreshCodeTreeOnly,
  getCodeTreeFiles,
  getCodeTreeDir,
  isMainCDiskDir,
} from "/js/ui/codeview.js";
import {
  openEditorFile,
  closeTab,
  remapOpenTabPaths,
  invalidateFileCache,
  dirtyTabPaths,
  openTabPaths,
  saveAllDirtyTabs,
  dirtySavableTabCount,
} from "/js/ui/codeeditor.js";
import { refreshMainCDiskState } from "/js/ui/generate-mainc-sync.js";  // main.c 磁盘同步：改名/删除涉及 main.c 后回步骤 8 状态
import { isMainCPath } from "/js/fx/code.js";

// guardTreeOpWrite(targetPath, isDir, actionLabel)：树操作的脏保护（工单
// code-tree-ops/02）——受影响 tab（精确或目录前缀命中）存在未保存修改时
// 两键「保存全部并继续 / 取消」；取消或保存失败 → false（操作中止）。
// 与 code-write-guard 的差异：不受「目录 = 生成上下文」限制——树操作用户
// 明确作用于当前打开目录，凡受影响脏 tab 均提示。
async function guardTreeOpWrite(targetPath, isDir, actionLabel) {
  const affected = dirtyTabPaths().filter((p) => treeOpAffected(p, targetPath, isDir));
  if (!affected.length) return true;
  const ok = await confirmModal({
    title: "代码栏有未保存修改",
    message: "『" + actionLabel + "』将影响 " + affected.length
      + " 个已打开且有未保存修改的文件——建议先保存全部，以免操作后仍需处理冲突。",
    confirmText: "保存全部并继续",
    cancelText: "取消",
  });
  if (!ok) {
    toast("info", "已取消：未保存修改保留，操作未执行");
    return false;
  }
  const saved = await saveAllDirtyTabs();
  if (!saved.ok) {
    toast("info", "有未保存修改未落盘，操作已中止");
    return false;
  }
  return true;
}

// treeCreate(kind)：新建文件 / 文件夹（kind ∈ file|dir）——输入模态
// （extra 输入框，确认值 = 字符串；空串 = 取消语义）；名称校验失败 →
// toast 中文不落盘；成功 → 刷新树（文件 → 自动打开新 tab 可编辑）。
async function treeCreate(kind) {
  const dir = getCodeTreeDir();
  if (!dir) { toast("error", "请先打开目录（选择文件夹或从最近记录进入）"); return; }
  const res = await confirmModal({
    title: treeOpTitle("create-" + kind),
    message: createPromptMessage(kind, ""),
    danger: false,
    confirmText: "创建",
    cancelText: "取消",
    extra: treeNamePromptHTML(kind, ""),
    // 就地校验（工单 code-tree-ops/02 在途盘点补口）：名称非法 → 弹窗不关闭 +
    // 错误就地显示，用户留在输入框改（此前是弹窗已关才 toast，输入丢失）。
    validate: (value) => treeNameValidate(String(value)).msg,
  });
  if (!res) return;
  const name = String(res);
  const v = treeNameValidate(name);   // 兜底（validate 已挡，防御路径）
  if (!v.ok) { toastError({ message: v.msg }, "无法创建"); return; }
  const path = name;
  try {
    const data = await apiPost("/api/code/tree/create", { dir, type: kind, path });
    invalidateFileCache(path);  // 创建前未缓存过成功态；防陈旧失败缓存命中
    await refreshCodeTreeOnly();
    if (kind === "file") {
      await openEditorFile(data.path);  // 新文件：GET /api/code/file 拿空内容 + mtime 基准
    }
    toast("ok", (kind === "file" ? "已新建文件 " : "已新建文件夹 ") + data.path);
  } catch (e) {
    toastError(e, "新建失败");
  }
}

// treeRename(path, isDir)：重命名文件 / 目录——脏保护（工单 06 评审整改：
// 与删除同口径——重命名同样影响已打开 tab 路径，涉脏先存/取消）+ 输入模态
// （默认值 = 当前名称）；成功后刷新树 + 已打开 tab 路径映射（内容 / 脏点 /
// mtime 不变）。
async function treeRename(path, isDir) {
  const dir = getCodeTreeDir();
  if (!dir) { toast("error", "请先打开目录"); return; }
  if (!await guardTreeOpWrite(path, isDir, "重命名")) return;
  const currentName = path.split("/").pop() || path;
  const res = await confirmModal({
    title: treeOpTitle("rename"),
    message: renamePromptMessage(path),
    danger: false,
    confirmText: "重命名",
    cancelText: "取消",
    extra: treeNamePromptHTML("rename", currentName),
    // 就地校验（工单 code-tree-ops/02 在途盘点补口）：同新建——非法名不关闭弹窗
    validate: (value) => treeNameValidate(String(value)).msg,
  });
  if (!res) return;
  const name = String(res);
  const v = treeNameValidate(name);   // 兜底（validate 已挡，防御路径）
  if (!v.ok) { toastError({ message: v.msg }, "无法重命名"); return; }
  if (name === currentName) { toast("info", "名称未变化"); return; }
  try {
    const data = await apiPost("/api/code/tree/rename", { dir, path, new_name: name });
    invalidateFileCache(path);
    remapOpenTabPaths(path, data.path, isDir);
    await refreshCodeTreeOnly();
    if (isMainCPath(path) && isMainCDiskDir()) refreshMainCDiskState();
    toast("ok", "已重命名为 " + data.path);
  } catch (e) {
    toastError(e, "重命名失败");
  }
}

// treeDelete(path, isDir)：删除文件 / 空目录——脏保护 + 确认模态（两条都
// 通过才调删除）；成功后关闭受影响 tab（force——脏保护已统一提示过，不再
// 逐 tab 重复弹）。
async function treeDelete(path, isDir) {
  const dir = getCodeTreeDir();
  if (!dir) { toast("error", "请先打开目录"); return; }
  if (!await guardTreeOpWrite(path, isDir, "删除")) return;
  const ok = await confirmModal({
    title: treeOpTitle("delete"),
    message: treeOpConfirmMessage("delete", path, isDir),
    confirmText: "确认删除",
    cancelText: "取消",
  });
  if (!ok) return;
  try {
    await apiPost("/api/code/tree/delete", { dir, path });
    for (const p of openTabPaths()) {
      if (treeOpAffected(p, path, isDir)) await closeTab(p, { force: true });
    }
    invalidateFileCache(path);
    await refreshCodeTreeOnly();
    if (isMainCPath(path) && isMainCDiskDir()) refreshMainCDiskState();
    toast("ok", "已删除 " + path);
  } catch (e) {
    toastError(e, "删除失败");
  }
}

// ===== 文件树右键菜单（工单 code-editor-refine/06；07 复用共享组件）=====
// 菜单浮层/关闭通道 = ui/context-menu.js 共享组件（工单 07 起第二个消费者：
// 选中代码动作菜单同用）；本模块只做树行命中 → 动作分发。

// copyTreePath(path)：复制相对路径——机制 = app.js copyText 单源
// （clipboard 优先 → execCommand 保底）；成功与否的提示文案本处定。
async function copyTreePath(path) {
  const ok = await copyText(path);
  if (ok) toast("ok", "已复制相对路径 " + path);
  else toast("error", "复制失败：请手动复制（路径：" + path + "）");
}

// runCtxAction(action, path, isDir, row)：右键菜单动作分发——打开（文件开
// tab / 目录展开收起 + 定位）、复制、重命名、删除（后两者与悬浮按钮共用
// TREE_OP_DISPATCH 同一函数路径：模态/脏保护/tab 联动全一致）。
const TREE_OP_DISPATCH = { rename: treeRename, delete: treeDelete };

async function runCtxAction(action, path, isDir, row) {
  if (action === "open") {
    if (isDir) {
      const d = row.querySelector("details[data-dir-path]");
      if (d) d.open = !d.open;
      row.scrollIntoView({ block: "nearest" });
      return;
    }
    await openEditorFile(path);
  } else if (action === "copy") {
    await copyTreePath(path);
  } else {
    const fn = TREE_OP_DISPATCH[action];
    if (fn) await fn(path, isDir);
  }
}

// bindTreeCtxMenu()：树容器 contextmenu 委托——命中行（目录/文件）→ 阻止
// 浏览器默认菜单并打开自定义菜单（连续右键 = 关闭旧 -> 跟随新光标重开；
// 关闭/滚动/Esc 由共享组件处理）；空白处右键不拦（浏览器菜单保留）。
function bindTreeCtxMenu(tree) {
  tree.addEventListener("contextmenu", (e) => {
    const row = e.target.closest(".code-tree-dir, .code-tree-file");
    if (!row) { closeContextMenu(); return; }
    e.preventDefault();
    const isDir = row.classList.contains("code-tree-dir");
    const el = isDir
      ? row.querySelector("details[data-dir-path]")
      : row.querySelector("[data-code-file]");
    const path = el ? (el.dataset.dirPath || el.dataset.codeFile || "") : "";
    if (!path) return;
    const items = treeCtxItems(isDir).map((it) => ({
      label: it.label,
      danger: it.danger,
      run: () => runCtxAction(it.action, path, isDir, row),
    }));
    openContextMenu(items, e.clientX, e.clientY);
  });
}

// initCodeTreeOps()：入口绑定——树头部新建按钮 + 树内 ✎/🗑 事件委托
// （委托挂在 #code-tree，与 codeview 的 [data-code-file] 监听并存互不冲突：
// 操作按钮不在文件按钮内部，各自 closest 只命中自己）+ 右键菜单。
export function initCodeTreeOps() {
  const tree = $("code-tree");
  if (tree) tree.addEventListener("click", async (e) => {
    const op = e.target.closest("[data-tree-op]");
    if (!op) return;
    e.stopPropagation();
    const task = op.dataset.treeOp;
    const path = op.dataset.treePath || "";
    const isDir = op.dataset.treeKind === "dir";
    if (task === "rename") await treeRename(path, isDir);
    else if (task === "delete") await treeDelete(path, isDir);
  });
  if (tree) bindTreeCtxMenu(tree);
  const newFile = $("btn-code-tree-new-file");
  if (newFile) newFile.addEventListener("click", async () => {
    if (!getCodeTreeDir()) { toast("error", "请先打开目录（选择文件夹或从最近记录进入）"); return; }
    await treeCreate("file");
  });
  const newDir = $("btn-code-tree-new-dir");
  if (newDir) newDir.addEventListener("click", async () => {
    if (!getCodeTreeDir()) { toast("error", "请先打开目录（选择文件夹或从最近记录进入）"); return; }
    await treeCreate("dir");
  });
}

// ===== 保存全部（工单 code-tree-ops/03）：状态栏按钮 + Ctrl+Shift+S =====
// 复用 saveAllDirtyTabs 单源（与编译前自动保存同一循环）；无脏 → toast 中文
// 反馈（避免「点了没反应」）；409 冲突既有三键模态兜底。
async function saveAllFromBar() {
  const before = dirtySavableTabCount();
  const res = await saveAllDirtyTabs(true);   // 手工保存全部（工单 10：自动编译判据——用户显式动作）
  if (!res.ok) return;  // 取消/失败：冲突模态或 toast 已提示
  toast("ok", before ? "已保存全部 " + before + " 个文件" : "没有未保存的修改");
}

export function initCodeSaveAll() {
  const btn = $("btn-code-save-all");
  if (btn) btn.addEventListener("click", saveAllFromBar);
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || !e.shiftKey || e.key.toLowerCase() !== "s") return;
    const codeTab = document.getElementById("tab-code");
    if (!codeTab || !codeTab.classList.contains("active")) return;  // 仅代码栏内拦截
    e.preventDefault();
    saveAllFromBar();
  });
}
