# 04 — C2 应用闭环（diff 预览确认 → 守卫 → 写盘 → 感知）

**要做什么：** AI 回复含 `<DIFF>` 块 → 应用闭环：
- 解析（工单 01 parseAiDiff）到有效 DIFF → AI 消息下方出现「预览改动」按钮
  （无块 → 无按钮）；点击 → 读盘（/api/code/file 取当前内容+base_mtime_ns）
  → **preview 请求**（/api/code/apply-diff preview=true）→ 确认模态
  （复用 confirmModal 形态但内容=diff 预览：态行 stats + hunks 渲染复用
  fx/diff.js mainDiffHTML——diff 对象用 fx maincDiffCompute(磁盘内容,
  new_content) 生成；文件路径标题）；确认/取消。
- 确认 → 写盘守卫 guardCodeTabWrite（WG 动作名新增
  WRITE_GUARD_ACTIONS.codeAiApply=「应用 AI 改动」——fx/write-guard.js
  加默认文案簇）→ apply-diff 写模式（base_mtime_ns = 读盘时值）→ 409 →
  提示「磁盘内容已变化，请重新预览」（引导重读+重预览，不静默覆盖）；
  成功 → toast + `checkCodeDiskChanges()` 立即感知（变更面板自动出现）。
- 目标文件是打开中的标签：不特殊处理（干净标签磁盘感知自动重载/脏标签徽章
  ——一期既定行为）。

**被谁阻塞：** 02（apply-diff 端点）+ 03（对话面板接收回复）。

**状态：** resolved

- [x] 验收 1：桩回复含 DIFF 块 → 「预览改动」按钮出现；无块 → 不出现。
- [x] 验收 2：预览模态显示 stats + hunks（diff 渲染可见）；取消 → 无写盘。
- [x] 验收 3：确认 → 磁盘文件 = 应用后内容（桩后端验证写路径）→ toast +
  变更面板出现（感知联动）。脏标签场景守卫弹窗（取消 → 中止）。
- [x] 验收 4：409（文件自预览后外部改过）→ 提示重预览，不覆盖。
- [x] 验收 5：node（含 write-guard 文案）+ smoke 全绿。

**结论：** 实现完成（评审整改中，见 spec.md「评审确认」段 s4）。实现要点与偏离：
- attachDiffButtons 在 renderPanel 尾部按序遍历 assistant 消息匹配 .sugg-msg.ai
  + parseAiDiff 非空 → 追加按钮（data-ai-preview=assistant 序号）——事件层委托
  body click → previewDiff。
- previewDiff：apiGet /api/code/file（取 content+mtime_ns）→ preview=true
  apply-diff（只算不写）→ maincDiffCompute(磁盘, new_content) + mainDiffHTML
  渲染确认模态（标题=「预览 AI 改动 · path」）→ guardCodeTabWrite → 写模式
  base_mtime_ns=file.mtime_ns → toast「已应用 AI 改动：path」→
  onCodeAiApplied → checkCodeDiskChanges。
- **偏离 1（守卫范围）**：guardCodeTabWrite 加 opts.anyDir——AI apply 在 IDE
  内任意目录（不限于生成上下文）脏标签都弹守卫——场景：用户改了一半未保存
  + 应用 AI 改动 → 防覆盖（smoke-06 S7 实测样本目录非上下文时不弹，修之）。
- **偏离 2（408→409 顺序）**：apply_code_diff 写模式 base_mtime_ns 校验提前到
  hunk 应用之前——外部改盘后 hunk 通常也不匹配，报 409「已被外部修改，请
  重新加载后再应用」而非 400「未匹配」（评审 s1 整改，tests
  test_apply_diff_conflict_409_priority_over_hunk_mismatch）。
- **偏离 3（toast kind）**：成功 toast uses kind "ok"（全仓库约定
  ok/error/info；初版 "success" 会渲染 .toast.success 无图标——已修）。
- **偏离 4**：守卫经动态 import（code-ai-chat ↔ code-write-guard 静态环
  code-write-guard→codeview→code-ai-chat）——顶部注释说明。
