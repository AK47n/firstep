// fx/code-shortcuts.js — 代码页快捷键帮助纯函数（工单 code-editor-shortcut-help/01）
//
// 快捷键说明数据单源 + 帮助浮层 HTML。数据与渲染分离：ui 胶水层只负责
// 弹窗开合/焦点管理，条目内容全部来自本模块——不散落裸串（与 fx 约定：
// 纯展示、esc 单源取自 fx/core.js；模块约定见 fx/core.js 头部）。
import { esc } from "./core.js";

// SHORTCUT_GROUPS：分组清单——title 分组名；items = [{keys, label}]。
// keys 为键帽字符串数组（评审整改：不再用 "/" 分隔串——避免渲染期解析、
// 数组语义直接），组合键以 "+" 连接、数组各元素 = 一个键帽（替代键位各占
// 一项）；鼠标手势（"中键"/"拖拽"）一并收录——它们与快捷键同为「无界面
// 提示」的交互，用户同等需要可发现性。
export const SHORTCUT_GROUPS = [
  {
    title: "编辑",
    items: [
      { keys: ["Ctrl+S"], label: "保存当前文件" },
      { keys: ["Tab"], label: "缩进选中行（4 空格）" },
      { keys: ["Shift+Tab"], label: "反缩进选中行" },
      { keys: ["Enter"], label: "换行并自动缩进" },
      { keys: ["Ctrl+Shift+K"], label: "删除当前行（组）" },
      { keys: ["Alt+↑", "Alt+↓"], label: "上移 / 下移当前行" },
      { keys: ["Shift+Alt+↑", "Shift+Alt+↓"], label: "向上 / 向下复制当前行" },
      { keys: ["Ctrl+L"], label: "选中整行（重复按扩展）" },
      { keys: ["Ctrl+/"], label: "切换注释（C 行注释/块注释、XML）" },
      { keys: ["(", "[", "{"], label: "输入开括号自动补上闭合括号（C/XML/Markdown）" },
      { keys: ["Backspace"], label: "删除配对的空括号" },
      { keys: ["中键"], label: "点击标签关闭" },
      { keys: ["拖拽"], label: "拖动标签排序" },
    ],
  },
  {
    title: "查找",
    items: [
      { keys: ["Ctrl+F"], label: "在当前文件中查找" },
      { keys: ["Ctrl+H"], label: "在当前文件中查找并替换" },
      { keys: ["Enter", "Shift+Enter"], label: "下一个 / 上一个匹配" },
      { keys: ["Esc"], label: "清除查找" },
    ],
  },
  {
    title: "视图",
    items: [
      { keys: ["Ctrl+Shift+["], label: "折叠光标所在代码块" },
      { keys: ["Ctrl+Shift+]"], label: "展开光标所在代码块" },
      { keys: ["Ctrl+滚轮"], label: "缩放代码字号" },
    ],
  },
];

// shortcutHelpHTML()：帮助浮层内容纯件——分组标题 + 无序列表；键位键帽
// （.code-kbd，keys 数组逐项一帽，之间 .code-shortcuts-or 分隔）；标题/
// 键位/说明全部 esc（数据静态但转义纪律不放松）。调用方把返回体放进
// 弹层壳体（遮罩 + 标题栏 + 滚动体）。
export function shortcutHelpHTML() {
  return '<div class="code-shortcuts">' + SHORTCUT_GROUPS.map((g) => {
    const rows = g.items.map((it) => {
      const caps = it.keys.map((k) => `<kbd class="code-kbd">${esc(k)}</kbd>`)
        .join('<span class="code-shortcuts-or">/</span>');
      return `<li><span class="code-shortcuts-keys">${caps}</span>`
        + `<span class="code-shortcuts-label">${esc(it.label)}</span></li>`;
    }).join("");
    return `<h4 class="code-shortcuts-group">${esc(g.title)}</h4>`
      + `<ul class="code-shortcuts-list">${rows}</ul>`;
  }).join("") + "</div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { SHORTCUT_GROUPS, shortcutHelpHTML });
}
