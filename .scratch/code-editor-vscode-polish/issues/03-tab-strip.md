# 03 — 标签条增强

**要做什么：** 多文件标签条补齐 VSCode 式交互：中键关闭、拖拽排序、激活自动滚入视野；关闭钮悬停区与徽章样式统一。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

**实现笔记：**

- 交付：中键关闭（非活动关、活动不关、磁盘徽章/关闭钮中键保持显式语义、脏标签仍走 confirmModal）；拖拽排序（HTML5 DnD：dragstart 记路径 + dragging 半透明、dragover 按命中 tab 中线判 before/after + 2px accent 插入位线、drop 调 moveTab 纯件、空白区 = 追加末尾）；激活标签 scrollIntoView(inline nearest)（renderTabs 重建后现查元素）；关闭钮 hover 区加大（padding 3px 6px）与磁盘/只读徽章 padding 统一（2px 6px）。
- 纯件：fx/codeeditor.js `moveTab(tabs, fromPath, toPath, place)`（新数组/无操作路径原引用；before/after/空 toPath 追加/目标不存在还原原位）；codeTabStripHTML 标签加 draggable="true"。
- 评审处置：Spec 轴 3 项（空白区落位断链、dragstart 未排除关闭钮/徽章、关闭钮与徽章样式统一）全部落实；Standards 轴同两点 + moveTab 注释矛盾已改；Fowler 判断项（closest ×4、拖拽三变量数据簇、if(strip) ×3）留待后续（属风格偏好，不阻断）。
- 测试：moveTab 3 组单测；node --test 全量绿；smoke-03.mjs 8/8（含空白区追加末尾与关闭钮 dragstart 守卫）；既有 code-viewer-editor smoke-02 20/20 回归通过。

- [ ] 鼠标中键（button 1）点击标签关闭该标签；作用中（活动）标签不因中键关闭（VSCode 行为）
- [ ] 按住标签可拖拽排序：拖动中显示插入位指示（虚线或高亮缝），松手落位；拖动不触发普通激活；关闭钮 / 徽章区域按下不启动拖动
- [ ] 标签顺序仅会话内有效（不持久化）；关闭 / 重命名 / 目录切换后顺序保持正确（tree rename 的 remap 与关闭右邻逻辑不受影响）
- [ ] 激活标签横向溢出被截断时自动 scrollIntoView（inline nearest）；新打开 / Ctrl+Tab（若有）/ 点击激活均触发
- [ ] 关闭钮 hover 区扩大（paddding + 圆角底色），脏点 / 磁盘变更徽章 / 只读标间距统一
- [ ] 上限 10 个标签、脏确认关闭、磁盘徽章点击弹三选等既有行为全部保持（回归）
- [ ] tests/js：标签排序纯件（拖拽落位顺序、活动标签不可拖走首尾边界、无副作用返回新数组）单测
- [ ] CDP 冒烟：中键关标签、拖拽排序（可模拟 dragstart/drop 事件）、活动标签 scrollIntoView 被调用

**补充：** 排序纯件放 fx（moveTab / tabIndexOf 等），事件（auxclick / dragstart / dragover / drop / scrollIntoView）在 ui 胶水；HTML5 DnD 用 dataTransfer 传路径，不用拖影（拖影由浏览器默认）。
