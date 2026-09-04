# 04 — 滚动同步 + 折叠组合 + 交互矩阵回归

**要做什么：** 滚动时窗口切换（rAF 节流 + 行区间比较，不逐帧重装）与折叠态
窗口文本（模型→视图→窗口三层映射）打通；随后跑完整交互矩阵：缩放 × 折叠 ×
主题三层对齐 12 格、跳转/查找/保存/撤销/复制粘贴冒烟、双主题截图、node +
pytest 全量——确认视口化对既有能力零回退。

**被谁阻塞：** 02、03。

**状态：** resolved

## Answer（04 实施 + 双轴评审整改后）

**交付（滚动 rAF 节流 + 折叠三层组合 + 矩阵回归）：**

- **滚动 rAF 节流**：scroll → requestAnimationFrame 合并（一次 rAF 处理突发
  滚动的终态窗口；「仅窗口行区间变化才重装」判定保留在 taWindowSync——同窗
  零 DOM，节流只合并事件不吞正确性）；ResizeObserver 不节流（低频且需精确
  窗口）；快速滚动直达目标窗口；textarea 无内部滚动条（CSS overflow:hidden，
  探针①断言）。探针①：30 次突发滚动终态窗口 = 模型切片、textarea top 与
  spacer 同值。
- **折叠 + 窗口三层组合**（模型→视图→窗口）：
  - `taWindowApply/taWindowSync` 移除 `viewModel` 早退——折叠态同样窗口化：
    winCache.lines = 视图行数组，窗口文本 = 视图切片（占位行按既有折叠渲染
    语义在窗口内呈现），absStart = 视图偏移；三环映射链自然成立。
  - 输入闭环：折叠窗口化 input/粘贴经 `windowEditToView → windowEditToModel
    (segs)`（01 纯件，触碰占位→展开/整块覆盖经 codeFoldMapEdit 原样承接）；
    `codeFoldMapEdit` 全量路径仅作无窗口防御兜底。
  - **程序化编辑保持 07 全视图语义**（评审整改）：editSource 折叠窗口化返回
    **视图全文 + 视图选区**（不是窗口切片）——Alt+↑↓ 移动/复制行、Ctrl+A
    全选、Tab/注释等不能把窗口边界当文档边界；applyEdit 折叠分支
    codeFoldMapEdit 视图→模型回写 + syncTail 统一窗口落位。
  - 光标/选区全链路视图坐标适配：syncTail 模型→视图换算（组合中不重装、
    防打断候选窗）；refreshFoldView/rebaseModelContent 统一 taWindowApply 按
    视图偏移落位；insertIntoActiveFile 选区经 editorSelectionModel 单源；
    Ctrl+L 修正回 taSetRange（视图坐标）。
  - 顺带修复：折叠窗口化 no-change（IME 取消）不再把光标拉回视图顶
    （codeFoldMapEdit identical 分支 caret 恒 0——syncTail 改持当前模型光标）；
    三处「失配重建」兜底收口为 `rebuildWindowKeepCaret()`；
    compositionstart/end 加 target 守卫。
- **对齐矩阵 12 格全绿**：probe-04 ③（100/150/200% × 折叠开/关 × 浅/深主题）
  每格先断言「折叠开关真实生效」（foldReal 与期望一致——评审整改：此前
  setCell 光标不在折叠区内、且 key 持有 renderPane 重建前的旧 textarea 引用，
  fold=true 6 格假绿）；三层 top 1:1 对齐 + 当前行 gutter/hl 对齐 12/12。
  双主题截图存档：shot-04-fold-dark.png（折叠态滚至占位行、窗口含「… N 行」，
  断言后捕获）、shot-04-light.png（首屏）。
- **交互冒烟全绿**：probe-04 ④ 逐键 5.5ms（≤25ms）、跳行 4500/查找渲染、
  真实保存（磁盘=模型、脏点清除）、150 行粘贴回写+撤销、AI 插入
  （insertIntoActiveFile，补 03 清单第 3 项）撤销/重做。
- **回归**：probe-03（跨窗口/折叠态撤销、粘贴、栈隔离）40/40；
  node --test "tests/js/*.test.mjs" 全量 **1295 绿**；pytest 全量 **3159 绿**
  （后端零改动）。

**双轴评审整改（04）：**
- Standards 轴：注释失实更新；失配兜底 3 份重复 → `rebuildWindowKeepCaret`；
  双端点换算重复 → insertIntoActiveFile/refreshFoldView 复用单源；折叠
  no-change 光标拉回视图顶 + 组合中直接重装 → syncTail 统一承担落位；
  命名（caret0→caretM、oldView→oldViewCaret）；探针矩阵假绿 + 折叠态截图
  滚到占位行 + 「折叠开关真实生效」断言。
- Spec 轴：**折叠态程序化编辑 = 窗口级 ≠ 07 全视图级**（moveLine/copyLine
  窗口首/末行静默失效、Ctrl+A 只选窗口）→ 改为视图全文 + codeFoldMapEdit
  回写（实测 Alt+↑ 在窗口顶行可移动、撤销可回）；顺带修出真实 bug：
  applyEdit 折叠分支引用未声明 `tab`（ReferenceError，程序化编辑静默失效）；
  探针 setCell 持有 renderPane 重建前旧 textarea 引用（key 不冒泡到
  document）→ 每次 key 重新 querySelector。探针幂等性：全程全新 headless
  实例跑（样本盘文件被真实保存改写，实例复用会串状态）。
- 附带验证：折叠+窗口态 Enter 程序化编辑（行数 +1、撤销回——行号漂移类
  编辑按 codeFoldMerge 签名语义丢折叠区，与 02 折叠路径同源，非本工单回归）。

**移交给后续：** 无（工单 01–04 全结案；对齐矩阵、滚动/输入/撤销/粘贴/
保存/跳转/查找/程序化编辑冒烟全绿）。

- [x] 滚动同步：scroll → rAF 节流 → 仅窗口行区间变化时重装文本 + 光标窗口内
      定位；快速滚动直达目标窗口；textarea 自身无内部滚动条。
- [x] 折叠组合：折叠时窗口文本 = 视图文本切片（01 三层映射）；占位行语义、
      折叠开合、触碰占位展开与现状一致；折叠态光标行号/跳行/当前行不回退。
- [x] 对齐矩阵 12 格全绿（100/150/200% × 折叠开/关 × 深浅主题，probe-align
      不变）；双主题截图（首屏/滚动中部/折叠态）对比存档。
- [x] CDP 冒烟：逐键/滚动采样、跳转、查找、保存、撤销/重做、复制粘贴
      全绿；node --test 全量绿；pytest 全量绿（后端零改动）。
- [x] 收尾：spec/工单/提交信息中文；CHANGELOG 中文自动补录。
