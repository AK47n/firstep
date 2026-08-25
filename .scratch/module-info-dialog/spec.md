# 模块详情弹窗（E8）——规格说明

## 问题陈述

模块选择网格（步骤 6）的信息密度不足：卡片只有 slug、描述截 26 字符、平台/依赖/副产物徽章缩写；`title` 提示只在悬停时可见完整描述。用户在选型时真正需要判断的信息——完整描述、每平台验证状态、文件清单、套件型号与购买链接、引脚角色声明、多实例/副产物/互斥组约束——在界面上**没有任何入口**，只能靠猜或额外问 AI。选型决策质量（平台可不可靠、硬件对不对得上、接线怎么对应）被卡片信息量卡死。

## 方案

在每张模块卡上加一个「详情」小按钮（卡片本体点击仍添加模块，主流程零扰动）。点击按钮弹出信息弹窗，一次展示该模块的全量信息（数据已在口袋：`GET /api/modules` 的 `to_dict()` 全量，**零后端改动**）：

- 标题区：slug + 完整描述
- 信息行：依赖、多实例、副产物、互斥组（缺省字段不渲染行）
- 每个平台一个区块：平台名 + 验证状态徽章（硬件绑定/已验证/未验证）+ 文件清单（空 = 实现内嵌母版）+ 备注 + 套件型号 + 购买链接（外链）+ 引脚角色声明表（角色 id、类型、默认引脚、是否必接、宏名）

弹窗复用仓库既有弹层模式：全屏遮罩（`.ref-files-overlay` 同构）+ 居中卡片 + ✕ 关闭按钮；Esc / 点遮罩 / 点 ✕ 三种方式关闭；内容区超高滚动。选型中已选模块（selected）不在网格，弹窗只服务「可用模块池」的选择决策——搜索/筛选后的网格同样有详情按钮。

## 用户故事

1. 作为选型用户，我想在模块卡上点「详情」按钮查看完整信息，以便不添加模块就能先了解它。
2. 作为选型用户，我想看到不被截断的完整描述，以便准确理解该模块功能。
3. 作为选型用户，我想看每个平台的验证状态（硬件绑定/已验证/未验证），以便判断该模块在当前平台的可靠性。
4. 作为选型用户，我想看每平台文件清单与「内嵌母版」提示，以便了解实现文件构成。
5. 作为选型用户，我想看套件型号与购买链接，以便核对硬件身份、按需采购。
6. 作为选型用户，我想看引脚角色声明表（id/类型/默认引脚/必接/宏名），以便与板级接线对照。
7. 作为选型用户，我想看依赖/多实例/副产物/互斥组信息，以便理解模块间关系与配置约束。
8. 作为选型用户，我想用 Esc / 点遮罩 / 点 ✕ 关闭弹窗，以便快速回到选择流程。
9. 作为选型用户，点击卡片本体仍添加模块，以便主流程零扰动。
10. 作为选型用户，当前平台无该模块版本时详情照常可看（附提示条），以便了解全貌后再决定是否换平台。

## 实现决策

- **数据源**：`state.modules`（`await apiGet("/api/modules")`，webapp.py:2000-2004 返回 `[m.to_dict() for m in list_modules(...)]`）。字段契约（manifest.py `ModuleManifest.to_dict`：247-258）：
  - 顶层：`slug`、`description`、`dependencies[]`、`platforms{...}`；`multi_instance{max,variant}`、`python_artifact`、`exclusive_group{id,label,role}` 缺省不落键。
  - `platforms[p]`：`files[]`、`verified`、`hardware_bound`、`notes`、`kit`、`source_url`、`pins[]`。
  - `pins[i]`（PinDeclaration.to_dict，74-82）：`id`、`type`、`label`（缺省=id）、`default`、`required`、`macros[]`。
  - `python_artifact` 两形状：旧 `{template, output}`；新 `{default, templates[{id,name,description,template,output}]}`。
- **纯函数抽取（可单测 seam）**：`moduleInfoHTML(module, platform)` → HTML 字符串。自包含内联 `escHtml`（同 `moduleGridHTML` 2773 行先例，不依赖全局 esc）；`platform` 参数 = 当前所选平台，仅用于「当前平台无版本」提示条（为空则不提示）。
- **弹窗 DOM**：动态创建（`showPinMenu` 3809-3868 先例）：`document.createElement("div")` → className `module-info-overlay` → appendChild 到 body；点击 ✕ / 点遮罩（`e.target === overlay`）/ Esc（keydown，`overlay` remove 时清理监听）关闭；重复打开先 remove 旧弹窗再建（替换语义）。不做 focus trap（ref-files/pin-menu 先例皆无）。
- **入口**：`moduleGridHTML` 的 `mc-head` 内 slug 之后加 `<button class="mc-info" data-info="<slug>" title="查看模块详情">详情</button>`（`off` 卡同样渲染——信息展示不受平台限制）；`initModuleGrid` click 委托加分支：`ev.target.closest(".mc-info")` 命中 → `openModuleInfo(slug)` 并 return，否则走原卡片添加逻辑。按钮在卡内需 `stopPropagation` 或委托先判——委托先判即可（同一监听器内 return，无第二个处理者）。`off` 卡的「需切换平台」提示逻辑不受影响。
- **样式**：新建 `.module-info-overlay`（fixed inset 0 遮罩 rgba(0,0,0,.6) + flex 居中 + z-index 50，同 `.ref-files-overlay` 509-511）+ `.module-info-modal`（max-width 760px、max-height 80vh、flex column、`.ref-files-modal` 同构 512-515）+ `.module-info-*`（head/close/body/区块/表格）；`.mc-info` 按钮样式（小号、accent 色、卡头右侧）。不动既有 `.ref-files-*` 类（低风险）。关闭按钮复用 `.ref-files-close` 类可行（同类名已跨 pin-menu 复用先例），但弹窗结构类一律 `.module-info-*` 前缀。
- **内容渲染规则**：
  - 标题：slug（mono）+ 完整描述。
  - 信息行（缺省不渲染）：依赖（顿号 join）、多实例（「可配置 <max> 个实例，按 <variant> 区分」）、副产物（旧形状 `template → output`；新形状 `default` 模板 + 每模板 name/description + `template → output` 行）、互斥组（label + role + 「同组互斥」字眼，可用 EXCLUSIVE_GROUP_TAG 语义「同组互斥」）。
  - 平台区块（`platforms` 键序）：平台标签（`moduleGridPlatformLabel` 语义）+ 状态徽章（hardware_bound → 硬件绑定 / verified → 已验证 / 否则未验证，同 `moduleGridStatusText` 2751-2756 语义）+ 文件清单（files 空 → 「实现内嵌母版（随母版进工程，不复制文件）」；非空 → 每文件一行 mono）+ notes（非空）+ kit（非空）+ source_url（非空 → `<a href target="_blank" rel="noopener">购买链接</a>`）+ 引脚声明表（pins 非空 → 表：角色 id/label、类型、默认引脚、必接标记（required）、宏名（macros 顿号 join，空不显示））。
  - off 提示：`platform` 非空且 `!(module.platforms || {})[platform]` → 头部下方提示条「当前平台 <label> 无此模块版本」。
- **图标/按钮文案**：按钮文字「详情」（不用图标，与现有按钮文案风格一致）。

## 测试决策

- **只测外部行为**：HTML 渲染结果（纯函数）与打开/关闭交互（headless 冒烟）。
- **单测 seam**：`tests/js/module-info-dialog.test.mjs`（node:test + 正则抽取先例：`tests/js/compile-error-jump.test.mjs`）——测 `moduleInfoHTML`：
  1. 全量字段渲染（描述/依赖/多实例/互斥组/每平台区块/文件清单/notes/kit/source_url 链接/pins 表/必接标签/宏名）。
  2. esc 转义（`<`、`&`、引号注入描述与字段）。
  3. 缺省字段不渲染行（无依赖/无多实例/无副产物/无互斥组）。
  4. 空 platforms / 空文件清单（内嵌母版文案）/ 空 pins（不渲染表）。
  5. 副产物两形状（旧 template/output 与新 default/templates）。
  6. off 提示（platform 参数命中无版本 vs 不传 platform 不提示；命中不 off 不提示）。
  7. 状态徽章三态（hardware_bound / verified / 两者皆无）。
- **headless 冒烟**：`.scratch/module-info-dialog/smoke.mjs`（CDP + webapp 8000，先例 `.scratch/compile-error-jump/smoke.mjs`；冒烟脚本内置 `Page.reload`——改 index.html 后内存 JS 是旧的，必须先 reload）：
  1. 点卡片本体 → selectedSlugs 增加且无弹窗（主流程回归）。
  2. 点「详情」按钮 → 弹窗出现、标题/描述/平台区块断言。
  3. Esc 关闭；重开 → 点遮罩关闭；重开 → 点 ✕ 关闭。
  4. 重复点同一模块详情 → 弹窗替换（无残留叠加）。
  5. off 卡（如所选平台不支持）详情可打开并含提示条。
- **回归**：pytest 全量绿（基线 2349）——后端零改动，纯回归确认；全量 `tests/js` 绿（基线 248）。
- **无需新增 pytest**（无后端行为变化）。

## 范围外

- 弹窗内添加/移除模块（详情是只读信息，添加仍在卡片本体）。
- 卡片 hover 浮现信息（入口已有按钮，不做悬停交互）。
- focus trap / ARIA `role="dialog"` 增强（先例 ref-files/pin-menu 皆无，保持一致性；如需无障碍增强另开工单）。
- 平台信息在弹窗内折叠（内容 max-height 滚动即可）。
- 弹窗拖拽/尺寸调整。
- 改动后端（零后端是本特性的核心卖点之一）。
