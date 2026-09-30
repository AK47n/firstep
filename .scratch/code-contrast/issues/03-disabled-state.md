# 03 — 禁用态：灰底灰字、去掉 opacity（有余力才做）

**要做什么：** 全站最低的那两处（人眼复核实测 hwcheck「带进生成页」**2.66**、
master「AI 提炼报告」**2.06**）不再靠"整体变淡"表达不可点——改成**灰底灰字**：
文字走 `--muted`、底走 `--panel-2`、描边走 `--border`，去掉 `opacity`。
做完之后禁用按钮的文字对比度是**可现算、可守卫**的，而不是"看它压在谁身上"。

**被谁阻塞：** 01（判据面共用腿⑧ 的族表；禁用态的格子走同一个函数）。

**状态：** ready-for-agent

- [ ] **去掉三处 opacity**：`button:disabled { opacity: .45 }`、
      `textarea:disabled, input:disabled, select:disabled { opacity: .6 }`，
      以及组件级那几处覆盖（`.master-file-btn:disabled .55` / `.code-statusbar button:disabled .55` /
      `#btn-code-ai-send:disabled .5` / `.wait-cancel:disabled .6` / `.code-change-item.disabled .65` /
      `.platform-card.disabled .5`）。
- [ ] **统一口径**：`background: var(--panel-2)` + `color: var(--muted)` + `border-color: var(--border)`；
      `box-shadow: none`（去掉主按钮的外光/呼吸动画）；主 / 危险 / 幽灵三类形态一视同仁
      （禁用时不再保留各自的语义色）。`cursor: not-allowed` 保留。
- [ ] **判据进腿⑧ 的族面**（不新起腿）：加两格——「`--muted` × `--panel-2`」与
      「`--muted` × `--panel`」（禁用控件可能坐在两种底上），两主题各算一遍，`text` 档 4.5。
- [ ] **结构判据**：页面上不许再出现 `opacity` 形式的禁用态——`css_rules` 里选择器含 `:disabled`
      或 `.disabled` 且声明体含 `opacity:` 即红（理由写进文案：禁用态要能被现算）。
- [ ] **渲染面证据**：`probe-07-rendered-sweep.mjs` 的**禁用桶实测是空的**（那些按钮坐在带渐变的
      容器里，被现有"祖先渐变跳过"规则滤掉）——本单要么把该桶改成"祖先渐变也收"，
      要么另立一支小探针专门量禁用控件；**不许把"扫描看不见"当成"已达标"**。
- [ ] **合成红证**：① 把 `opacity: .45` 放回去 → 结构判据红；② 把 `--muted` 换成更浅的值 →
      族面红；③ `.disabled` 类选择器带 opacity → 红。
- [ ] **读数**：禁用按钮的实测比值（真元素/真像素），与旧读数 2.66 / 2.06 对照。
- [ ] **门禁**：前端门禁全绿；全量 pytest 全绿；**浏览器门禁单独跑**（改了 `index.html` 样式块）。

## 备注

- 本单是**有余力才做**的部分（用户拍板口径已给："灰底灰字、去掉 opacity"）；若 01/02 的收口
  已经很紧，可以整单推迟到下一轮，但**口径已定**，别重新发明。
- `.platform-card.disabled` 是"不可选的卡片"不是按钮，形态上保留 `--panel-2` 底即可，
  文字同样走 `--muted`。
