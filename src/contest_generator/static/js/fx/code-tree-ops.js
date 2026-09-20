// fx/code-tree-ops.js — 代码树操作纯函数（工单 code-tree-ops/01-02）
//
// 名称校验 / 受影响路径计算 / 重命名路径映射 / 确认文案——全部无副作用，
// node 单测覆盖；胶水在 ui/code-tree-ops.js（模态 + fetch + tab 联动）。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

// 单段名称规则（工单 cross-lang-mirror-c5a/01）：判据单源 = 后端
// `codeview.send_name_rules`，经 `POST /api/code/open` 载荷的 `name_rules`
// 下发（`ui/codeview.js` 每次拿到响应就调 setCodeTreeNameRules 装上）。
// 下面两个常量退化为**后端尚未下发时的启动兜底**——不再是与后端「同口径」
// 的第二份实现（此前两侧靠注释互指、零守卫：改一侧另一侧静默失效）。
// 兜底值与后端常量的一致性由 `tests/test_codeview.py::test_js_name_rules_fallback_mirrors_backend`
// 读本文件真源码对账（改任一侧即红）。
export const CODE_TREE_NAME_ILLEGAL = "/\\:*?\"<>|";
export const CODE_TREE_NAME_MAX = 120;

/** 兜底规则（= 上面两个常量）：复装 / 测试复原用。 */
export const CODE_TREE_NAME_RULES_DEFAULT = {
  illegal: CODE_TREE_NAME_ILLEGAL,
  max_len: CODE_TREE_NAME_MAX,
};

// 运行时生效的规则（装载后 = 后端下发值）。畸形下发一律忽略而不是就地清零：
// 空集合 / 0 上限会让校验形同虚设（前端放行一切、后端 400），比规则过期更坏。
let nameRules = { ...CODE_TREE_NAME_RULES_DEFAULT };

/** 装载后端下发的名称规则（畸形输入忽略并保持现值）。 */
export function setCodeTreeNameRules(rules) {
  if (!rules || typeof rules !== "object") return;
  const illegal = rules.illegal;
  const maxLen = rules.max_len;
  if (typeof illegal !== "string" || !illegal.length) return;
  if (!Number.isInteger(maxLen) || maxLen < 1) return;
  nameRules = { illegal, max_len: maxLen };
}

// treeNameValidate(name)：单段条目名称校验 → {ok, msg}（msg 中文）。
// 非空 / 非纯空白 / 首尾无空白 / ≤上限 / 不为 . 或 .. / 不含保留字符。
export function treeNameValidate(name) {
  const n = String(name == null ? "" : name);
  if (!n || !n.trim()) return { ok: false, msg: "名称不能为空" };
  if (n !== n.trim()) return { ok: false, msg: "名称首尾不能有空格" };
  if (n.length > nameRules.max_len) {
    return { ok: false, msg: "名称过长（最多 " + nameRules.max_len + " 字符）" };
  }
  if (n === "." || n === "..") return { ok: false, msg: "名称不能是 . 或 .." };
  const bad = [...nameRules.illegal].filter((c) => n.includes(c));
  if (bad.length) {
    return { ok: false, msg: "名称含非法字符：" + [...nameRules.illegal].join(" ") };
  }
  return { ok: true, msg: "" };
}

// treeOpAffected(tabPath, targetPath, isDir)：tab 路径是否受目标路径影响——
// 文件 = 精确相等；目录 = 自身或任意子路径（前缀匹配）。
export function treeOpAffected(tabPath, targetPath, isDir) {
  const t = String(tabPath == null ? "" : tabPath);
  const p = String(targetPath == null ? "" : targetPath);
  if (!p) return false;
  if (!isDir) return t === p;
  return t === p || t.startsWith(p + "/");
}

// treeRenamedPath(tabPath, oldPath, newPath)：重命名后的 tab 路径——
// 前缀命中 → 替换前缀返回新路径；未命中 → 原样返回。
export function treeRenamedPath(tabPath, oldPath, newPath) {
  const t = String(tabPath == null ? "" : tabPath);
  const oldP = String(oldPath == null ? "" : oldPath);
  const newP = String(newPath == null ? "" : newPath);
  if (!oldP) return t;
  if (t === oldP) return newP;
  if (t.startsWith(oldP + "/")) return newP + t.slice(oldP.length);
  return t;
}

// treeOpKind(path, files)：目标路径是否为目录（files = /api/code/open 清单
// 含 is_dir 条目时直接查；无 is_dir 条目时以「存在子文件」前缀判定兜底——
// 空目录在清单中有 is_dir: True，两种形态都覆盖）。
export function treeOpIsDir(path, files) {
  const p = String(path == null ? "" : path);
  if (!p) return false;
  for (const f of files || []) {
    if (String(f.path) === p) return !!f.is_dir;
  }
  const prefix = p + "/";
  return (files || []).some((f) => String(f.path).startsWith(prefix));
}

// treeOpTitle(action)：模态标题（action ∈ create-file/create-dir/
// rename/delete）。
export function treeOpTitle(action) {
  return {
    "create-file": "新建文件",
    "create-dir": "新建文件夹",
    rename: "重命名",
    delete: "删除确认",
  }[action] || "树操作";
}

// createPromptMessage(kind, parentPath)：新建输入模态说明（parentPath =
// 当前目标目录相对路径；本期 UI 固定为工程根 ''，参数留作子目录支持）。
export function createPromptMessage(kind, parentPath) {
  const where = parentPath ? "目录「" + parentPath + "」下" : "工程根目录";
  return kind === "dir"
    ? "在" + where + "新建文件夹。输入名称："
    : "在" + where + "新建文件。输入名称：";
}

// renamePromptMessage(path)：重命名输入模态说明（默认值 = 当前名称）。
export function renamePromptMessage(path) {
  return "将「" + path + "」重命名为：";
}

// treeOpConfirmMessage(action, path, isDir)：删除确认文案——文件直接删；
// 目录提示「仅空目录可删（非空目录会被拒绝）」。
export function treeOpConfirmMessage(action, path, isDir) {
  if (action !== "delete") return "";
  return isDir
    ? "将删除目录「" + path + "」及其中所有文件（目录仅空目录可删）。"
    : "将删除文件「" + path + "」。此操作不可撤销。";
}

// treeNamePromptHTML(kind, value)：输入模态 extra HTML——单行文本框
// [data-confirm-value]（confirmModal 确认时解析其 value，空串 = 取消语义）。
export function treeNamePromptHTML(kind, value) {
  return `<input type="text" class="code-tree-name-input" data-confirm-value
    value="${esc(value || "")}" placeholder="名称"
    autocomplete="off" spellcheck="false">`;
}

// ---- 浮层菜单（工单 code-editor-refine/06；07 共享泛化）----

// treeCtxItems(isDir)：右键菜单项（打开 / 复制相对路径 / 重命名 / 删除）——
// 与悬浮 ✎/🗑 同动作语义（复用 treeRename/treeDelete 与脏保护）；「打开」
// 文件开 tab、目录展开/收起 + 定位（label 按形态区分）。菜单浮层渲染/定位
// 钳制 = ui/context-menu.js + fx/overlay.js menuClamp（06 的 treeCtxMenuHTML/
// treeCtxClamp 随 07 共享泛化移除）。
export function treeCtxItems(isDir) {
  return [
    { action: "open", label: isDir ? "展开 / 收起" : "打开" },
    { action: "copy", label: "复制相对路径" },
    { action: "rename", label: "重命名…" },
    { action: "delete", label: "删除…", danger: true },
  ];
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    treeNameValidate,
    treeOpAffected,
    treeRenamedPath,
    treeOpIsDir,
    treeOpTitle,
    createPromptMessage,
    renamePromptMessage,
    treeOpConfirmMessage,
    treeNamePromptHTML,
    treeCtxItems,
    setCodeTreeNameRules,
    CODE_TREE_NAME_ILLEGAL,
    CODE_TREE_NAME_MAX,
    CODE_TREE_NAME_RULES_DEFAULT,
  });
}
