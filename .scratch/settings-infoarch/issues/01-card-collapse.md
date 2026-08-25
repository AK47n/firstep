# 01 — 设置卡整卡折叠 + 默认收起 + 状态记忆

**要做什么：** 设置页 8 张带标题的卡片（应用设置 / LLM 用量统计 / AI API / 库目录 / 工具链 / 本地模型 / 视觉通道 / 最近 LLM 工作流）支持整卡折叠：点击卡片标题或右上角 ▾ 展开/收起；工具链、本地模型、视觉通道、库目录 4 张默认收起，其余默认展开；用户手动调整的折叠状态写入 localStorage，刷新后保持（无记录时按默认集）。保存设置卡不带折叠（行动点始终可见）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 8 张卡带 `data-collapse-id`（app/usage/llm-api/libs/toolchain/local-llm/vision/recent-wf），各卡 h2 内有 `button.card-collapse`（▾）；保存设置卡不可折叠
- [x] 默认收起 4 张（libs/toolchain/local-llm/vision），`llm-api` 默认展开；页面加载首帧即为最终态（无闪烁）
- [x] 点击 h2 或 ▾ 切换折叠，title/aria-label 随状态同步（沿用 collapseBtnLabel 语义：「折叠该卡片」/「展开该卡片」）
- [x] 折叠状态存 `localStorage` 键 `firstep.settingsCollapse.v1`（JSON `{id: collapsed}`），刷新保持；解析失败按 `{}`；用户选择优先于默认集
- [x] `node --test tests/js/*.test.mjs` 全绿：新增 settings-collapse.test.mjs 抽取 parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed / applySettingsCollapseState 并断言默认集、stored 覆盖、垃圾解析容错、假件 class/aria 同步；card-collapse.test.mjs 抽取正则不受破坏
- [x] CDP 截图：设置页亮/暗 1440px 目检，默认收起 4 张卡、首屏不含工具链/库目录内容

## 审查记录（2026-xx）

**Standards 轴**（子代理 696b0382）：无硬性违规。判断项：
- Duplicated Code（中）：`initSettingsCollapse` 内 3 处「toggle→写 state→存盘→刷总开关」序列重复，btn/h2 分支直调 `syncCollapseBtn(btn,next)` 而 head 分支与主开关循环走 `applySettingsCollapseState(c,next)`，两条同步路径并存。**已修复**：三个 toggle 处理器统一收敛到 `applySettingsCollapseState`（其内含 card→`syncCollapseBtn`、section→`sectionCollapseLabel` 分派）；初始循环改为先建按钮再 `applySettingsCollapseState(c, collapsed)`，消除「按钮未建先 apply」的冗余 no-op。重构后 `node --test` 174 例全绿。
- 跨票预留（Speculative Generality，判断）：ai-billing 与总开关代码在 02/03 HTML 就位前为死代码，属 spec 明示的一次到位清单，可接受。
- Middle Man（轻）+ `sectionCollapseLabel` 与 `collapseBtnLabel` 同形：spec 已点名，接受。

**Spec 轴**（子代理 1e4e4def）：无实质缺口。要点：
- 8 卡 `data-collapse-id`、保存卡天然不可折叠、按钮由 JS 运行时创建、默认集经 `effectiveCollapsed` 落地、`initSettingsCollapse()` 在 body 末尾同步执行（首帧无闪烁）——均符合 spec。
- 提前实现总开关/计费分支属 spec 明示许可（「新增纯函数 + DOM 装配一次到位，02/03 只补 HTML/CSS」）；`btn-settings-collapse-all` 空守卫使 01 阶段完全休眠，无运行时泄漏。
- 工单措辞「默认收起 4 张」与默认集 5 项（含 `ai-billing`）的差异是 spec 单源约定，向前兼容 02，非错误。
- `recent-wf` 卡 h2 从 `.row` 提升为直接子元素：结构性必要（`.card.collapsed > *:not(h2)` 只保留直接子 h2，否则标题随整行隐藏）；展开态视觉（标题独占行、控件下沉）经 CDP 截图目检确认可接受。
