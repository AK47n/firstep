# Spec：模块选择器卡片化（module-grid / C3）

## 问题陈述

第 6 步「模块清单与平台警告」目前是：下拉框（`#module-pool`）+「添加模块」按钮 + 独立
搜索框（结果另一个列表）+ 「展开依赖并检查平台」按钮。模块多时下拉看不清能力/平台状态；
搜索和下拉两套交互并存；已选模块还要在下面再列一遍。

## 方案

把「选模块」交互收敛成**卡片网格**（保留搜索框，去掉下拉与搜索结果列表）：

- 卡片 = 单个模块：`slug`（主标题）+ 短描述（截断，title 全文）+ 平台徽标
  （已验证/未验证/硬件绑定/内嵌母版，复用 `moduleBadges` 的徽标）+ 依赖提示
  （`依赖：a、b`）+ 副产物标记（有 `python_artifact` 显示小徽章）。
- 搜索框保留：输入实时过滤网格（slug + 描述 + 依赖 + 平台徽标文本匹配，规则与现状一致）；
  清空 = 显示全部可用模块。计数文案 `共 N 个可用模块` / `匹配 N 个可用模块`。
- 平台不兼容（`chosenPlatform` 不在 `m.platforms` 键中）→ 卡片**置灰** + 角标「需切换
  平台」；点击不添加（toast info 提示该平台不支持）。已选中的模块被切平台时维持现状：
  保留在清单里 + 现有平台警告继续起作用（本工单不改警告逻辑）。
- 点击卡片 = 添加该模块（走既有 `addModule`：清 expanded/warnings → 重渲染 →
  `runExpand` 自动展开，行为与现在下拉添加完全一致）。
- 已选模块不出现在网格里（与现状下拉排除已选一致）；已选清单仍在下方
  `#selected-list`（移除此/模板下拉/依赖带入展示全保留）。

## 用户故事

- 作为参赛学生，我一眼能看到所有模块的平台状态，不用一个个点开下拉/搜索对比。
- 作为参赛学生，我按关键词过滤网格后点卡片就能加模块，并自动展开依赖。
- 作为参赛学生，我切到不支持的平台时，不兼容模块仍然可见但明确置灰标注，不会被「消失」吓到。

## 实现决策

- 删除：`#module-pool`（select）、`#btn-add-module`、`#module-search-results`（独立结果框）
  及其事件绑定（btn-add-module click、module-search input→renderModuleSearch、结果框
  data-add 委托）。保留：`#module-search`（input → 重渲染网格）、`#module-count`、
  `#warnings`、`#selected-list`、`#btn-expand`。
- `renderModulePool()` 改为网格渲染器（函数名保持——调用点遍布 addModule/remove/
  启动流程，不扩爆破改）：读搜索词 → 过滤 `state.modules`（排除已选）→ 生成卡片 HTML；
  纯函数 `moduleGridHTML(modules, selectedSet, query, platform)` 自包含可测（内联 esc），
  `moduleCardHTML(m, q)` 可选合并进前者。
- 卡片点击事件：`initModuleGrid()` 在 `#module-grid` 上做一次事件委托
  （`closest("[data-add]")` 现成路径）。
- `renderModuleSearch` 删除，`addModule` / 移除处理里的 `renderModuleSearch()` 调用一并删除
  （旁边就有 `renderModulePool()`，行为一致）。
- CSS：`.module-grid`（grid，`repeat(auto-fill,minmax(180px,1fr))`，gap 8px）、
  `.module-card`（panel-2 卡片：slug 行 + 描述行 + 徽标行）、`.module-card.off`（置灰 +
  角标）、`.module-card .mk-sel`（已选态不用——已选不进网格，保留给未来）。

## 测试决策

- `tests/js/module-grid.test.mjs`：`moduleGridHTML` —— 全量渲染 / 搜索过滤命中
  （slug/描述/依赖/平台名）/ 排除已选 / 平台不兼容置灰类与角标 / 空结果文案 /
  转义（slug/描述/依赖含引号）；`moduleCardHTML` 各行（徽标/依赖/副产物）。
- 既有 JS 测试不引用 module-pool/btn-add-module（已查），无回归面。
- headless 手测：加模块（点击卡片）→ selected-list 出现 + 自动展开；切平台 → 不兼容卡
  置灰 + 点击 toast；搜索过滤即时生效。

## 范围外

- 模块清单排序/分组（按能力标签分类）——目前无能力标签数据源，不做。
- 已选模块在网格内的显示/管理（仍走下方 selected-list）。
- 平台切换时对已选模块的自动移除/替换（保持现状：保留 + 警告）。
