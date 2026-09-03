# 02 — 打开即窗口文本三明治 + 手打输入回写（非折叠单文件端到端）

**要做什么：** 6000 行 .c 打开后 textarea 变成「视口高 + 窗口 ~56 行文本」，
手打输入能正确回写模型（保存、跳行、光标行列、脏点全部可用）；打开实时
计时 ≤80ms（从 ~253ms）；视觉零回归（首屏与现在一字不差）。本切片先通
非折叠单文件路径，折叠态保持现状（折叠时仍走视图文本全量，不组合窗口）。

**被谁阻塞：** 01（窗口文本纯件）。

**状态：** resolved

- [x] 打开路径：textarea 高度 = 视口高、内容 = 窗口文本（01 纯件构建）、
       光标/选区窗口内定位；高亮/标记/行号仍窗口化渲染（现状）；滚动条
       = 虚拟高度（spacer）不动。
- [x] 输入回写：input 事件 → 01 映射 → 模型更新（非结构增量、结构全量折叠
       重算，沿用既有判定）；光标/状态栏/脏点照常。
- [x] 结构编辑（Enter/删换行/括号等）与跨越窗口的编辑：先按光标切窗口 →
       重装 → 再映射；返回/Home/End/PageUp 边界正确。
- [x] IME 保护：compositionstart/end 既有守卫沿用，组合中不重装窗口。
- [x] 一致性校验兜底：失配 → 以模型重建窗口文本（不静默错位）。
- [x] CDP 探针：打开 ≤80ms（probe-open 口径）、逐键 ≤25ms 不回退、
       首屏/滚动中部截图对比、保存/跳行/查找可用。

## Answer

**交付（02 实施 + 双轴 code-review 整改后）：**

- **窗口化打开**：`codeEditorHTML` 新增 `opts.taValue`（textarea 不再内嵌
  108KB 全文，标记层零开销）；renderPane 后 `taWindowApply(0)` 装「视口高 +
  窗口文本」——textarea top = 窗口起点×行高、向下延伸盖满视口（overscan 上缘
  连续变化），与高亮/行号/标记层逐行对齐；滚动条虚拟高度不动。
- **输入回写**：input → `windowEditToView/windowEditToModel`（01 映射，绝对段
  直换模型）→ 共享尾段 `syncTail`（标记状态先行 + 行级增量/全量渲染 + 窗口
  重装 + 光标落位 + 脏点/状态栏）；含 Enter/Tab/行操作/注释/括号等程序化编辑
  ——applyEdit 窗口化态改**模型级**（notes 明确 02 与 03 需同期切换，否则
  Enter/替换路径必破；快照栈仍窗口级过渡 = 03 全域化）。
- **滚动同步**：scroll（同步，无 rAF——04 工单细化节流）→ winRender +
  taWindowSync（行区间变化才重装文本；同窗只挪覆盖高度；光标滚出窗口钳到
  窗口边缘，输入永不落不可见处）。
- **光标/选区映射**：新增 `windowPosFromView/windowPosToView` 纯件 + 单测；
  `foldCaretModelPos/taCaretViewPos/editorSelectionModel/editorSelectionView/
  editorViewText` 统一换算（状态栏/AI 选区/跳行/查找全经单源）。code-ai-chat
  选区上下文改模型级切片（textarea 窗口文本不能直接 slice）。
- **一致性校验**：`windowTextMatchesModel` 接线（内容未变但窗口文本与模型
  推导不符 → 以模型重建）；映射失败（窗口/行起点表不同步）→ 重建，不静默
  错位。IME 组合中不重装（taWinDirty 标记），compositionend 后以
  `follow=false` 重装——组合期间用户已滚动则视口不被拉回。

**评审整改（双轴）：** ①Speculative Generality/死接口整改——`windowPosToView`
  全面接入（taCaretViewPos/taWindowSync/editSource/insertIntoActiveFile/
  editorSelectionView），消除 5 处手写同形换算；②Duplicated Code——提取
  `taApplyWindowStyle` 统一窗口几何；③Mysterious Name——`editBase` → `editSource`；
  ④注释校正（rAF 节流移交 04 的说明）；⑤Spec 轴——一致性校验纯件接线 +
  IME 组合中滚动后 compositionend 不拉回视口（`follow=false`）。

**实测：**
- node --test tests/js 全量 1289 绿（含新增 windowPos 往返/越界、taValue 单测）。
- pytest 全量 3159 绿（后端零改动）。
- CDP 探针 `.scratch/editor-textarea-viewport/probe-02.mjs` 18/18 绿：纯前端
  重开 renderMs 20ms（≤80ms；fetch 67ms 后端预算外单列）、逐键 input 8ms
  （≤25ms）、textarea 窗口 1.4KB（全文 177KB）、首行打字/Enter 结构回写、
  滚动窗口文本 = 模型切片、跳行 3000/查找命中、首屏与滚动中部截图
  （shot-02-first.png / shot-02-mid.png）存档。

**移交给后续工单：**
- 03：撤销/重做全域化（快照栈模型级 + 手打入栈）——02 未动撤销语义
  （拼接期间原生栈局部有效，窗口中文本替换即断）。
- 04：滚动 rAF 节流、折叠三层组合、对齐矩阵 12 格。
