# 母版库管理增强（体检 / 文件树 / 快速导入 / 预览增强 + 仓库级 confirm 统一）

> 会话/系列 slug：master-library-ui-2。承接 master-library-ui（关键文件预览 +
> 表格增强 + 删除确认）后的 backlog §3 剩余候选（2026-08-19 记录、2026-08-27
> 立项）。候选 5 项全部落地，其中「母版替换入口」以**免提炼快速导入**形态
> 落地（单工程替换不需要 AI 合并语义）；单文件写侧替换评估后**不做**
> （理由见「范围外」）。实施按竖切工单逐张落地（见 issues/）。

## 问题陈述

上一轮母版库 UI 提升只开放了「关键文件」白名单 7 条：清单外的文件（stm32
母版 user/ 下其它源码、mspm0 母版其它文件）在 UI 里看不见，核对母版全貌
（「这个目录里到底有什么」「ml_libs 有多大」）必须开文件管理器。母版腐坏
（关键文件被删 / 构建产物残留 / 与元数据不符）没有一次性体检视图，只能
逐条点详情或开目录。母版更新（如官方模板升级新版 SDK）仍要走「整夹上传 →
扫描 → AI 提炼 → 报告确认」全流程——单工程替换没有合并语义，AI 提炼是
重流程。关键文件预览是纯文本 pre-wrap：模板 main.c / mspm0.syscfg 可读性差、
内容不能一键复制。仓库内破坏性动作仍剩 8 处原生 `confirm()`（含母版提炼
确认「确认并入库」），与其它栏目已统一的 `.ref-files-overlay` 确认弹窗
交互语言不一致。

## 方案

五个主轴：

1. **母版体检**：`/api/masters` 列表每条带 `health`（关键文件缺失清单 /
   工程配置文件存在性 / 构建产物残留）+ `stats`（总字节 / 文件数 / 大文件
   Top 10），一次算好；表格加健康徽章列（✓ 健康 / ⚠ 有缺失或残留），
   详情弹窗元数据段加体积统计行。
2. **文件树浏览**：详情弹窗加「全部文件」区——`GET /api/masters/{platform}/tree`
   返回平台目录下全部文件（统一噪音跳过，一次算好 size），前端渲染为递归
   可收起树（原生 `<details>/<summary>`，零 JS 收起逻辑）；点树内文件加载
   全文到既有内容箱（新内容端点：平台目录内 + 文本文件 + 大小上限，与
   关键文件白名单端点并列）；关键文件清单保留为快捷入口。
3. **预览增强**：内容箱顶部加「复制」按钮（剪贴板写入，失败 toast）；
   内容渲染加轻量语法高亮——C（.c/.h）与 XML（.syscfg/.uvprojx/.cproject）
   两类，逐 token 转义防注入，超大文件回退纯文本；纯函数可单测。
4. **母版快速导入（替换入口）**：母版卡新增「直接导入替换」——选文件夹
   整夹暂存（复用既有暂存流程）→ 平台下拉（复用既有平台选项）→ 确认弹窗
   （「将整体替换该平台旧母版」警告）→ 结构校验 + 原子替换 + 自动 git
   提交（复用既有入库编排），全程零 LLM 调用；免提炼的直接替换路径。
5. **confirm 仓库级统一**：新建共享确认弹窗工厂（Promise<boolean>，复用
   `.ref-files-overlay` 遮罩语言与 Esc/×/点遮罩取消），母版提炼确认
   （「确认并入库」）作为 pilot 接入，再迁移其余 7 处原生 `confirm()`；
   顺带把流程中的原生 `alert()` 错误提示统一为 toast。

## 用户故事

1. 作为母版库使用者，我想要表格每行有健康徽章（✓ / ⚠ + 悬停说明），以便
   一眼看出哪个平台的母版缺文件或有构建产物残留。
2. 作为母版库使用者，我想要详情弹窗可见该母版总体积、文件数与超大文件
   Top 10，以便发现母版膨胀源头（如被误放进去的大文件）。
3. 作为母版库使用者，我想要详情弹窗内以文件树浏览该平台母版的**全部**
   文件（目录可收起、噪音目录不出现），以便不开文件管理器就能核对母版全貌。
4. 作为母版库使用者，我想要点树内任意文本文件即加载全文预览（二进制 /
   过大文件给出中文说明），以便核对清单外文件内容。
5. 作为母版库使用者，我想要关键文件清单与文件树并存（清单 = 快捷入口，
   树 = 全貌），以便两者互补不互相替代。
6. 作为母版库使用者，我想要预览内容可一键复制、C/XML 有轻量语法高亮，
   以便拿模板 main.c / syscfg 去比对时更省力。
7. 作为母版库使用者，我想要「直接导入替换」：选一个母版目录就能免 AI
   提炼、经确认弹窗后结构校验并原子替换该平台旧母版，以便官方模板升级
   时不必走提炼全流程。
8. 作为全工具使用者，我想要所有破坏性确认（删除 / 回滚 / 覆盖 / 提炼入库）
   统一走确认弹窗而非原生窗，以便交互语言一致、警示信息更完整。

## 实现决策

### 后端（母版库域层，master_store 单源）

- 新增 `MasterHealth`（ok / missing_key_files / config_file_ok /
  artifact_dirs）与 `MasterStats`（total_size_bytes / file_count /
  big_files，big_files = 按大小排序 Top 10 且 >256KB 阈值常量）+ 域函数
  `master_health(masters_dir, platform)` / `master_stats(masters_dir, platform)`：
  体积与文件数统计走统一噪音跳过（iter_project_files 口径——与浏览/校验
  口径一致，构建产物目录不计入）；构建产物残留检测与入库时
  analyze_structure 同口径（顶层目录名）。
- 新增 `TreeFileInfo`（path / size_bytes）+ `master_tree_files(masters_dir,
  platform)`：平台目录下全部文件（iter_project_files，统一噪音跳过、排序
  确定性），文件数与体积由 stats 同口径，不重复遍历（两函数可共吃一次遍历
  或各自独立——实现期以其一为准，另一为薄委托）。
- 新增 `read_master_tree_file(masters_dir, platform, rel_path)`：路径安全
  （库内自持判定：父目录解析必须落在平台母版目录内，任意层级 `..` 拒绝）、
  二进制（NUL 字节）拒绝、超过 1MB（常量 TREE_FILE_MAX_PREVIEW_BYTES）
  拒绝——三类均 400 中文；读取 utf-8 errors="replace"（仓库读文本惯例）。
- 新增 `import_master_direct(masters_dir, platform, source_dir)`：免提炼
  入库——复用 import_master（结构校验 + 临时目录 + 原子替换 + 备份回滚 +
  autocommit），sources = [源目录名]；平台名校验与 import_master 相同。
- API：`GET /api/masters` 条目增 `health` / `stats` 两字段；新增
  `GET /api/masters/{platform}/tree`、`GET /api/masters/{platform}/tree/{path:path}`、
  `POST /api/masters/import`（body：platform + project_dir，project_dir 与
  现有 scan 同风险面——服务器本地绝对路径，暂存目录或用户显式路径均可）。
- 既有端点零改动：`GET /api/masters/{platform}/files/{path:path}` 白名单墙
  语义不动；DELETE 不动。

### 前端（纯函数下沉 fx，DOM 层转发）

- fx/master.js 增：`masterHealthBadgeHTML(h)`（✓/⚠ + title 说明）、
  `masterStatsHTML(s)`（统计行富文本）、`masterTreeNodeHTML(nodes)` /
  `buildMasterTree(files)`（递归 details/summary 树，文件行 data 属性交
  事件层）、`masterTreeFileURL(platform, path)`（与 masterFileURL 同拼法）。
- 新 fx/highlight.js：`highlightC(text)` / `highlightXml(text)`（先切 token
  后逐段转义再拼 HTML，杜绝注入；关键字/注释/字符串/预处理/数字/标签/
  属性/引号值分类着色）；语言判定 `languageOf(path)`（.c/.h → C；
  .syscfg/.uvprojx/.cproject/.xml → XML；其余纯文本）；超 128KB 回退纯文本
  （常量 HIGHLIGHT_MAX_BYTES）。
- 内容箱渲染统一走 `masterContentHTML`（复制按钮 + 高亮内容 + 加载三态），
  关键文件与树文件共用同一渲染与 memo（key = platform/path 不变）。
- 快速导入 UI：母版卡「直接导入替换」按钮 → 选文件夹（webkitdirectory，
  复用既有暂存流程）→ 平台下拉（复用既有平台选项渲染）→ 确认弹窗 →
  POST /api/masters/import → toast + 刷新母版库列表；确认弹窗即共享
  confirm 工厂的 pilot。
- 新 ui/confirm.js：`confirmModal({title, message, danger}) -> Promise<boolean>`
  共享工厂（遮罩 / 双钮 / Esc / × / 点遮罩取消，Promise resolve 布尔）；
  fx/overlay.js 提供 `overlayConfirmHTML({title, message, danger})` 纯件。
  迁移 8 处：母版提炼确认（pilot）/ 桌面同名工程覆盖 / 修复回滚 / 修订
  深化回滚 / 模块删除 / 模块平台文件移除 / 参考条目删除 / 赛题删除；
  同步审计并迁移原生 `alert()` 错误提示为既有 toast。

### 模式变更 / 架构决策

- 不引入新依赖；无新错误类（复用 MasterError，已登记 400 中文；未登记
  异常 = 真 bug → 500 不变量不变）。
- 文件树内容端点打开「平台母版目录内任意文本文件」读面——以路径安全 +
  二进制拒绝 + 大小上限三重复约束收窄，与参考文件库 read_fulltext 的
  安全语义对偶；白名单端点（关键文件）语义不变，两条路线并存。
- 母版快速导入走既有入库编排（结构校验 + 原子替换 + 备份回滚 + autocommit），
  零新写侧原语——写侧安全不新增。
- CONTEXT.md「母版」词条补本轮语义：health / stats / 文件树 / 树文件内容
  端点 / 免提炼导入 / confirm 统一（共享工厂）。

## 测试决策

- 后端主 seam = pytest：test_master_store.py 增 health / stats / tree /
  tree 文件读取（三类 400：穿越 / 二进制 / 超限）/ import_direct（成功替换
  旧母版 + 结构校验失败不动盘 + 平台非法）用例（tmp_path，不碰真实库）；
  test_webapp.py 增列表 health/stats 字段断言 + tree / tree 文件 200/400 +
  import 200/400。
- 前端主 seam = tests/js node:test 纯函数单测（extract 范式）：新增
  master-ext-browser.test.mjs（树构建 + 树 HTML + 健康徽章 + 统计行 +
  树 URL 拼装）、highlight.test.mjs（C/XML token 化正确性 + 注入转义 +
  超限回退 + languageOf）、overlay-confirm.test.mjs（确认弹窗 HTML 纯件）。
  既有 master-browser.test.mjs 不破。
- 交互层延续 CDP 冒烟范式（对偶 master-library-ui/smoke.mjs）：详情弹窗树
  展开 / 点树文件加载 / 复制 / 快速导入确认弹窗（不真导）/ 提炼确认弹窗
  （不真调）；冒烟清单保持全绿。
- 全量回归：pytest 全量 + tests/js 全量保持绿；母版 tab 实扫（stm32 /
  mspm0 两条母版的 health 实况与树文件数）。

## 范围外

- **单文件写侧替换**（上传替换 pin_config.h / mspm0.syscfg 等关键文件）——
  评估后不做：母版=生成根，关键文件在生成侧全部是模板/默认值或由渲染器
  现写（模板 main.c 被骨架覆盖、pin_config.h 被绑定覆写、.uvprojx 由
  确定性渲染器现写、mspm0.syscfg 是默认外设布局），单文件写侧替换会
  破坏「母版 = 生成基线」不变量；整体替换已有路径（提炼确认可更换 +
  本轮免提炼导入）。如需定向修改请走生成侧绑定/渲染能力。
- 文件下载 / 编辑；树文件搜索 / 过滤；批量操作；深色主题专项。
- 提炼卡既有流程改造（本轮只换确认弹窗，不动扫描/提炼/报告）。
- 模块库/参考库/赛题库的 confirm 迁移若涉及交互重设计（如批量删除），
  超出本轮（本轮只做 1:1 等价迁移）。

## 补充说明

- 母版库是 git 版本化库根（库写动作自动提交）：免提炼导入 / 任何库写入
  都自动进 git，git 历史即回滚兜底。
- 语法高亮是纯展示（不解释代码、不生成 DOM 引用），只对文本做 token 级
  着色，不改变后端契约（content 原样返回）。
- 冒烟验证不真删 / 不真导（零写库），验收以弹出层出现 + 后端拒绝路径
  的 400 中文为准。
- 所有文案中文；spec / 工单 / 提交信息 / CHANGELOG 遵循仓库语言规范；
  新增 .ps1 按约定 UTF-8 with BOM。
