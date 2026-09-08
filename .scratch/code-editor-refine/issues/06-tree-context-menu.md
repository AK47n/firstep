# 06 — 文件树右键菜单

**要做什么：** 文件树行（文件/目录）右键弹上下文菜单：打开（文件开 tab；目录收起/展开定位）/ 复制相对路径 / 重命名 / 删除；Esc、点击空白、滚动关闭；复制相对路径 = 相对当前工程根的路径（navigator.clipboard，保底 execCommand，失败 toast 提示）；重命名/删除复用既有 tree-ops 动作与脏保护（guardTreeOpWrite、tab 联动）；菜单浮层深浅主题一致；不新增后端。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## 实现要点

- 树容器加 contextmenu 委托（与悬浮按钮委托同处 ui/code-tree-ops.js）；菜单定位防视口溢出；至少支持 Esc 关闭（键盘导航可选）。
- 「复制相对路径」纯前端字符串拼（树行数据已含相对路径），不走后端；clipboard 失败降级 document.execCommand 于隐藏 textarea。
- 与悬浮 ✎/🗑 共存（右键仅是另一入口）；删除目录沿用后端「仅空目录」限制。

## 实现决策备注（双轴评审后回写，workflow.md step 4）

- **共享组件范围**：菜单浮层为 code-tree-ops.js 私有组件（openCtxMenu/closeCtxMenu 未 export——当前无第二消费者；后续需复用再扩导出面）。
- **复制机制单源化（Standards Duplicated Code 整改）**：全仓库第 7 份同型「clipboard → execCommand 兜底」实现收敛为 app.js `copyText(text)`（app.js 规则 4「新共享件优先落本文件」+ 规则 1「不 import ui/*」）；迁移点：toast 复制按钮 / 最近记录 / 核对表 / 手稿复制 / 输出目录 / 烧录命令 / main.c 工具栏 / 母版 / PDF / 树右键，各点提示文案保留原样；原差异（execCommand 优先、clipboard-only、失败静默）统一为 clipboard 优先+兜底（改进：如输出目录/烧录命令原本无兜底，现补上）。
- **重命名脏保护补全（Spec (a)2 整改）**：既有 treeRename 从不调 guardTreeOpWrite（仅删除有）——右键重命名与悬浮同路径沿用该缺口；工单字面「重命名/删除…脏保护」要求两者同口径，故 treeRename 前置 guardTreeOpWrite(path, isDir, "重命名")（悬浮按钮同步受益：涉脏先「保存全部并继续/取消」）。
- **菜单内右键**：菜单自身 contextmenu preventDefault——不叠浏览器原生菜单（评审 (c)2）。
- **视口兜底**：treeCtxClamp 钳 8px 边距 + CSS .code-ctx-menu max-height: calc(100vh - 16px)/overflow-y:auto（评审 (c)1 注释与实现一致化）。
- **空白处右键**：不拦浏览器原生菜单（仅关闭自定义菜单）——工单仅要求「点击外部关闭」，属合理边界。

## 验收 checklist

- [x] 文件/目录行右键出菜单四项可用：文件「打开」开 tab；「复制相对路径」剪贴板内容为 `dir/file.c` 形态；重命名/删除行为与悬浮按钮一致（含受影响 tab 联动）。
- [x] Esc/点击外部/滚动关闭菜单；连续右键菜单跟随目标；深色主题样式与既有浮层一致（token 同族；亮色随 token）。
- [x] 脏保护：删除/重命名涉及脏 tab 时弹确认（与悬浮一致——重命名 guard 本工单补全）。
- [x] CDP 冒烟 smoke-06 19/19（右键 → 复制 → 剪贴板断言；重命名/删除/脏保护；日志 smoke-06.log 存证）；单测 treeCtxItems/treeCtxMenuHTML/treeCtxClamp 3 组；全量 1227 pass。
