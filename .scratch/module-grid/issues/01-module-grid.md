# 工单 01：模块选择器卡片化（网格 + 搜索过滤 + 平台置灰）

Status: resolved
Slug: module-grid
依赖：无（纯前端 index.html + tests/js）

## 背景

第 6 步下拉选模块改卡片网格：搜索框实时过滤网格、平台不兼容置灰保留、
点击卡片即添加并自动展开依赖（C3，用户已确认：置灰保留 + 搜索+网格）。

## 验收标准

- [x] 删除 `#module-pool`(select) / `#btn-add-module` / `#module-search-results` 及其
      事件绑定（btn-add-module click、module-search input→renderModuleSearch、
      结果框 data-add 委托）；保留 `#module-search` / `#module-count` /
      `#warnings` / `#selected-list` / `#btn-expand`。
- [x] 新增 `#module-grid` 容器；`renderModulePool()` 改为网格渲染器（函数名保留）。
- [x] 纯函数 `moduleGridHTML(modules, selectedSet, query, platform)`（含卡片渲染，
      内联 esc）自包含可测：全量 / 搜索过滤（slug+描述+依赖+平台名）/ 排除已选 /
      平台不兼容置灰 `off` + 角标「需切换平台」/ 空结果文案 / 引号转义。
- [x] 卡片点击 = 添加（走 `addModule`：清 expanded/warnings → 重渲染 → runExpand）；
      不兼容卡点击不添加，toast info 提示。
- [x] `renderModuleSearch` 删除，`addModule` / 移除处理中的 `renderModuleSearch()`
      调用删除（旁边已有 `renderModulePool()`）。
- [x] CSS：`.module-grid`（auto-fill minmax(180px,1fr)）、`.module-card`、
      `.module-card.off`（置灰 + 角标）。
- [x] tests/js/module-grid.test.mjs 覆盖 `moduleGridHTML` 各分支；
      node --test 全绿，既有测试不回归。

## 实现说明

- 卡片复用 `moduleBadges(m)` 徽标（已验证/未验证/硬件绑定/内嵌母版），纯函数化：
  `moduleGridHTML` 内联生成徽标 HTML（data-* 属性由委托用，防重复绑）。
- 平台判据：`(m.platforms || {})[platform]` 存在 = 兼容；不存在 = 置灰。
- 计数：无搜索词 `共 N 个可用模块`，有搜索词 `匹配 N 个可用模块`（含置灰）。

## code-review 落实（双轴）

- Standards：①moduleGridHTML 内联 escHtml（自包含范式，测试不再注入全局 esc）；
  ②`.mc-plat.un`/`.mc-deps` 裸色值沿用既有 `.badge.no-master`/`.badge.dep` 形式
  （同文件先例，不新增令牌——记录为接受项）。
- Spec：①补「内嵌母版」徽标（复用 moduleBadges 判据 `!(entry.files||[]).length
  && !m.python_artifact`）；②平台短标签 STM32/MSPM0 为有意偏离（卡片宽度下
  toUpperCase 全名过长，与 recentPlatformLabel 查表口径一致）——记录于实现说明；
  ③平台切换回调补 `renderModulePool()` 刷新置灰态（spec 必需交互）。
- 验证：node --test tests/js 240 全绿；headless 探针（初始 26 卡/搜索过滤/平台置灰
  4 张与预期一致/点击添加展开/off 卡 toast 不添加）通过；截图目检网格多列布局 OK。
