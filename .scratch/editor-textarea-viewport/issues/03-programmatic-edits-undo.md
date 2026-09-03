# 03 — 程序化编辑与撤销全域化（applyEdit 模型级 + 快照栈接管）

**要做什么：** 缩进/注释/行操作/查找替换/AI 插入等程序化编辑不再依赖
execCommand 原生撤销（其语义绑定「textarea=全量文本」），统一改为
「模型级编辑 + 窗口重装 + 模型快照栈撤销/重做」；撤销/重做在窗口切换、
折叠、程序化编辑后语义正确（与现在可感知行为等价）。

**被谁阻塞：** 02（窗口文本三明治已上线，程序化路径必须同期切换）。

**状态：** resolved

## Answer（03 实施 + Standards 轴评审整改后）

**交付（撤销栈全域化）：**

- **模型级快照**：新增 `fx/undo-stack.js` 纯件（undoPush/undoStep/redoStep/
  UNDO_LIMIT=200——栈状态机零 DOM，node 单测 6 用例）；快照 =
  {value, selStart, selEnd}（**模型全文 + 模型选区**），与窗口文本无关——
  跨窗口/折叠态语义由「模型为唯一事实源」保证。栈语义 = 编辑前快照；
  新编辑清空 redo；上限 200（大文档全量快照为先例，风险已知可控）。
- **applyEdit 模型级**：窗口化态写模型 + 窗口重装 + 快照入栈；
  **execCommand / nativeUndo 路径整体删除**（原生栈只认「textarea=全量文本」
  旧语义，视口化后窗口内/跨窗口必错乱——03 明确放弃；折叠/全量兜底改直赋值 +
  syncEditorAfterInput 折叠映射回写，快照由 sync 变更入口统一入栈）。
- **手打入栈**：beforeinput（编辑前值/选区仍为旧态）捕获模型快照；
  input 真实变更入口统一入栈（窗口化/折叠/全量三分支）；
  组合输入 = 一次组合一步撤销（compositionstart 捕获、组合中不重复入栈、
  compositionend 收尾并入同一撤销步）；无 beforeinput 的合成输入兜底捕获。
- **Ctrl+Z/Y/Shift+Z**：编辑器内一律拦截走模型快照栈（原「nativeUndo 可用时
  交浏览器」不再成立）；snapshotUndo 弹栈并**恢复模型选区**（selStart..selEnd
  映射回视图/窗口，与既有「撤销恢复选区」语义一致）→ rebaseModelContent 重建
  （折叠区按签名保留）→ 标签条脏点/状态栏/查找词括号标记刷新。
- **跨窗口/折叠语义**：窗口 A 编辑 → 滚动到窗口 B 编辑 → 连续撤销/重做，
  模型级恢复（探针③）；折叠态手打/replaceAll 撤销（探针④，折叠保留）；
  换/关 tab、切目录、磁盘重载 → resetUndoStack（快照模型级，跨 tabs 必错，
  与原生栈随 textarea 重建清空对齐）。
- **程序化路径全覆盖**：Tab/Shift+Tab/Enter/行操作/注释/括号/AI 插入
  （insertIntoActiveFile）/查找替换单个与全部——折叠态 replaceAll/replaceOne
  补上快照（原「沿袭缺口」）；复制/粘贴走 input 自然回写窗口段 → 模型，
  超长（150 行）粘贴映射正确 + 撤销（探针⑤，不静默丢内容）。
- **顺带修复**：Ctrl+Shift+[/]（折叠快捷键）此前被括号自动闭合劫持、在光标
  处插入 "[]"——bracket 分支加 `!ctrlKey && !metaKey && !altKey` 修饰键守卫
  （否则 04 折叠矩阵必然失败；探针④断言「折叠未插入 []」）。

**Standards 轴评审整改：** ①撤销恢复从「只回光标」改为**恢复模型选区**
（selEnd 不再死字段，与旧全量态「撤销恢复选区」等价）；②手打入栈状态机
consumeInputSnapshot → **pushTypingSnapshot** + 抽出 **clearTypingSnapshot**
（4 处重复清空收口）；③resetUndoStack 四处调用注释去重；④测试删 snap()/
S() 双工厂与死三目；⑤probe-03 尾逗号去除。

**实测：**
- node --test "tests/js/*.test.mjs" 全量 **1295 绿**（新增 undo-stack 6 用例）。
- pytest 全量 **3159 绿**（后端零改动）。
- CDP 探针 `.scratch/editor-textarea-viewport/probe-03.mjs` **40/40 绿**：
  ①程序化路径（Tab/Enter/删行/注释/替换单个与全部）撤销→重做；
  ②手打（trusted 输入）撤销→重做；手打+程序化混合逆序撤销；
  ③跨窗口（窗口 A 打 X → 窗口 B 打 Y → 连续撤销 X/Y + 重做）；
  ④折叠态（Ctrl+Shift+[ 不被劫持、手打/替换撤销、折叠保留）；
  ⑤超长粘贴 150 行回写 + 撤销；⑥换 tab 撤销栈隔离（不错撤）。

**移交给 04：** 折叠 + 窗口三层组合（02 折叠保持「textarea = 视图全量」，
本工单仅保证折叠态快照语义；04 打通窗口化折叠）、滚动 rAF 节流、对齐矩阵。

- [x] applyEdit 改模型级：变更计算基于模型全文（既有纯件不变），写模型 +
      窗口重装（光标映射落位）；不再走 execCommand insertText。
- [x] 快照栈全域：程序化编辑 + 手打输入统一入栈（大文档直赋值 + 快照栈
      既有先例全域化）；Ctrl+Z/Y 语义回归（含跨窗口、折叠态）。
- [x] 行操作/注释切换/查找替换/AI 插入/插入到光标各路径回归（CDP 冒烟
      抽查 + 对应既有单测全绿）。
- [x] 复制/粘贴：input 事件自然回写窗口段 → 模型；粘贴跨窗口/超长 → 校验
      回退重建（不静默丢内容）。
- [x] node 全量 + CDP 冒烟抽样全绿。
