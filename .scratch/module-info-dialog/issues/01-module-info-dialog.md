# 01 — 模块详情弹窗（详情按钮 + 全量信息弹窗）

**要做什么：** 模块选择网格每张卡片显示「详情」按钮；点击弹出全量信息弹窗（完整描述/依赖/多实例/副产物/互斥组 + 每平台区块：验证状态/文件清单/备注/套件/购买链接/引脚声明表）；Esc/点遮罩/点 ✕ 均关闭；点击卡片本体仍添加模块（主流程回归）；off 卡详情可看（附「当前平台无此模块版本」提示条）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收记录（提交信息见 git log「工单 module-info-dialog/01」）

- 实现：moduleGridHTML 卡片 mc-head 加「详情」按钮（data-info=slug）；initModuleGrid 委托先判 .mc-info → openModuleInfo（卡片本体仍 addModule）；moduleInfoHTML 纯函数（自包含内联 esc + moduleGridPlatformLabel/moduleGridStatusText 单源复用）；openModuleInfo 动态创建弹窗（同 showPinMenu 模式：Esc/遮罩/✕ 关闭、remove 清理 keydown、重复打开替换）；.module-info-* 样式（复用 .ref-files-overlay 模式不动既有类）。
- 测试：tests/js/module-info-dialog.test.mjs 10 项绿（全量/esc/缺省隐藏/两形状副产物/空 platform 与空 pins/off 三态/徽章三态）；全量 tests/js 258 绿（248 基线 + 10 新增）。
- headless 冒烟 17 项全 PASS（真实模块库 26 卡、off 卡 4 张）：卡片添加回归/详情打开/三种关闭/替换/off 提示条。
- 全量 pytest 2349 绿（后端零改动）。

- [x] `moduleGridHTML` 卡片 `mc-head` 渲染「详情」按钮（`data-info`=slug）；`initModuleGrid` 委托先判 `.mc-info` → 打开弹窗，卡片本体点击仍走 `addModule`
- [x] 纯函数 `moduleInfoHTML(module, platform)` 渲染全量信息（自包含内联 esc）；空字段不渲染；副产物两形状（旧 `template/output`、新 `default/templates`）；pins 表（id/label/type/default/required 必接/macros）；source_url 外链（`target="_blank" rel="noopener"`）；off 提示条
- [x] 弹窗动态创建（同 `showPinMenu` 模式：appendChild body + Esc/遮罩/✕ 关闭 + remove 清理 keydown）；重复打开替换旧弹窗
- [x] `.module-info-*` 样式（遮罩+居中卡 max-width 760/max-height 80vh+内容滚动；不动 `.ref-files-*` 既有类）
- [x] `tests/js/module-info-dialog.test.mjs` 单测（全量/esc/缺省隐藏/两形状副本/空平台与空 pins/off 三态/徽章三态）
- [x] headless 冒烟 `.scratch/module-info-dialog/smoke.mjs` 全 PASS（卡片本体添加回归 + 详情打开 + 三种关闭 + 替换 + off 卡）
- [x] 全量 pytest 绿（2349）与全量 `tests/js` 绿（258）
- [x] 中文提交信息（CHANGELOG 由 post-commit hook 自动补录）
