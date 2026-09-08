# 待办计划（backlog）

后续可做的优化清单（2026-08-19 记录，按需立项走 workflow）。

## 1. 推荐缓存加模块库指纹校验 —— ✅ 已实现（工单 recommend-cache-fingerprint/01，2026-08-19）

**问题**：`validate_recommend` 只校验题面 / 平台 / 赛题键，**不查模块库内容**——库变了（模块增删 / description 变化）缓存照旧命中，直出旧推荐结果。实测：2026C 缓存是旧模块库时代生成的（OLED/LED 被归库外建议），库切换后缓存仍直出。

**已落地**：library_sha256 = ManifestSummary 摘要行（to_line）排序 hash；写缓存存指纹、校验比对；库变 → 缓存失效走真实推荐；旧缓存无字段保守失效（宁可重推）。

## 2. 多实例配置：AI 没猜实例时的自动兜底 —— ✅ 已实现（工单 instance-default-fallback/01，2026-08-19）

**问题**：AI 猜实例（module-multi-instance/06）依赖模型按题面数量输出 instances——题面没写数量（如 2026C"声光提示"）时模型不猜，推荐后实例卡为空，用户要手动添加。

**已落地**：命中多实例模块且 AI 没猜 → 按平台默认自动填（stm32 红黄绿 3 实例 / mspm0 单实例，与"不配置"生成等价零回归），实例卡直接可见可改。

## 3. 母版库浏览 UI 轮（master-library-ui）的剩余候选 —— ✅ 已落地（工单 master-library-ui-2/01-06，2026-08-27）

本轮范围外 / 评审发现的后续可做项（2026-08-27 以 master-library-ui-2 系列全部落地）：

- 母版库详情/浏览的其他候选（用户未选入本轮，多选枚举时排除）：**文件树浏览 / 结构健康复核 / 体积文件统计 / 母版替换入口**——全部落地：体检（health/stats 徽章 + 统计行）、文件树（/tree 端点 + 原生 details 树）、替换入口 = **免提炼快速导入**（import_master_direct + /api/masters/import，「直接导入替换」按钮）；并顺带落地预览增强（复制按钮 + C/XML 轻量高亮）与 confirm 仓库级统一（共享工厂 + 8 处迁移 + alert 归 toast）。
- 提炼确认流程「确认并入库」按钮（卡片1）原用原生 `confirm()`——已随 confirm 统一迁移共享弹窗。
- 关键文件预览的语法高亮 / 复制按钮——已落地（fx/highlight.js + masterContentHTML 复制钮）。
- **单文件写侧替换**（上传替换 pin_config.h / mspm0.syscfg 等关键文件）**评估后不做**：母版 = 生成根，关键文件在生成侧全部是模板/默认值或由渲染器现写（模板 main.c 被骨架覆盖、pin_config.h 被绑定覆写、.uvprojx 由确定性渲染器现写、mspm0.syscfg 是默认外设布局），写侧替换会破坏「母版 = 生成基线」不变量；整体替换已有路径（提炼确认可更换 + 免提炼导入）。详见 .scratch/master-library-ui-2/spec.md「范围外」。

## 4. 阶段 2 收尾评审（code-review b46f786^..HEAD，双轴 Standards + Spec）发现 —— ✅ 已落地（工单 frontend-es-modules-stage2/21-25，2026-08-27，提交 f26e1fa）

评审发现五项（2026-08-27 以 stage2 工单 21-25 全部落地：node 447/447 + pytest 2465 + diag 零 EXC + smoke 11/11；工单 22-25 状态于 245740d 补翻 resolved）：

- **发现 1（🔴 硬，Spec/CONTEXT 违背）：ui 模块环 generate-core ↔ generate-readiness** —— ✅ 落地（工单 21）：`desktopTopicOutputEnabled` 从 core 归位 readiness 簇（判据输入语义归位），core / steps → readiness 恢复单向；新增 `tests/js/ui-cycle.test.mjs` 静态环检测守卫。原成因：工单 20 补迁 btn-generate 监听器（core:35 import readinessState）+ 工单 19 readiness 簇反向 import core 的 desktopTopicOutputEnabled（readiness.js:21）——互为双向，违反「ui 模块间允许单向静态 import」。
- **发现 2（文档漂移）：spec.md:92 结构钉表陈旧** —— ✅ 落地（工单 22）：stage2 spec.md 钉表改 `ui/generate-recommend.js`（附注「工单 12 重指向：cut 方案复核后非 generate-steps」——step-done-refs.test.mjs:13 实际重指向 A 簇，markStepDone(2) / syncStep4( 调用点均在 generate-recommend）。
- **发现 3（判断项，近硬）：host 残留跨 tab DOM 渲染** —— ✅ 落地（工单 23）：`renderNewPlatformOptions` 导出归 ui/master.js（L676），index.html 启动 IIFE 只留调用（L2635）；IIFE 内其余渲染均已委托簇函数。
- **发现 4（Duplicated Code，判断项）** —— ✅ 落地（工单 24/25）：generate-steps.js 两按钮重复监听器提 `bindClearDraftButton(btnId)` 共享；generate-mainc.js 滚动三同步提 `syncPanels(ta)`（syncMainCHighlight 与 scroll 监听器共用）。
- **发现 5（Mysterious Name，弱，判断项）** —— ✅ 落地（工单 24）：`genOverviewWarn(n)` → `genOverviewWarn(stepNo)`；`overviewPlanNow(doneArr)` 经核语义尚可未改。

## 5. 模块库全链路审计（2026-09-08，93 模块 / 86 stm32 条 / 84 mspm0 条）—— 🔶 部分落地

用户问「与模块库环环相扣的每一步有没有出错风险」。审计脚本在 `.scratch/library-audit/`（`audit.py` 全库不变量 / `sim_preselect.py` 真实题面预筛模拟 / `cut_analysis.py` 相关但被砍统计 / `reachability.py` / `gate_sweep.py` 逐模块门禁），全部只读可复跑。

**结论：机械面干净，问题在「库长大了、推荐链路的视野没跟上」。** 干净侧证据：全量 pytest 3838 passed；93 模块 manifest 全可加载；依赖无悬空无成环；平台声明文件全在；无孤儿源文件；默认脚全部在板定义内且能力匹配；373 个 pin_config.h 宏双向对齐零缺失；62 个 syscfg 实例与 INSTANCE_CONSUMERS 一致；**170 个「模块×平台」组合逐一跑生成门禁全过**（含依赖闭包）。

### 5.1 🔴 P0：推荐候选预筛把库砍掉一半，失败静默 —— ✅ 已落地（工单 preselect-recall-visibility/01-02 + preselect-visibility/01-02，2026-09-08）

- **已落地（2026-09-08，工单 preselect-recall-visibility/01-02，提交 8065fbfd）**：判据取源归位——库内合法性改取平台全量（`TopicContext.library_summaries` / `PreselectResult.library_summaries` / `known_summaries` 可选入参），模型推荐「子集外但库内」的模块不再被判成幻觉中断推荐；多实例能力清单与默认实例兜底同源；库指纹取源改全量；覆盖率守卫落盘（`tests/test_preselect_coverage.py`，6 组真实题面 × 平台）。
- **可见性已修（2026-09-08，工单 preselect-visibility/01-02，提交 0f19a513 / 4950d98b）**：根因是**行太长**而非预算太小——完整行含套件段（占摘要字节 23.5%，带淘宝/天猫采购链接噪声），全库 stm32 86598B / mspm0 78668B 装不进 `MODULE_SUMMARY_BYTES=40000`，预筛按排序截断到 33–41 条。一级清单行改瘦身形态（`ManifestSummary.lean_copy`：slug + 有界首句 100 字符 + 依赖 + 多实例/副产物/互斥标记）后 **28071B / 28062B——全库可装、截断消失**；6 组真实题面 86/86、84/84 全部可见（`probe_guard_cases.py`），覆盖率守卫摘 xfail 转常规。复测探针 `.scratch/library-audit/probe_lean_variants.py`。
- **历史现状记录（修复前）**：`budget.py` `MODULE_SUMMARY_BYTES=40000`，摘要段 stm32 86.6KB / mspm0 78.8KB（197%–217%）；20 份真实赛题每次只送进 32–42 条 / 84–86 条；12 个模块（stm32 侧）20 份题面里一次都没进过提示词。
- **最刺眼一例（2024H 智能小车，修复前）**：可见 34 条全是传感器/显示件，**motor/pid/servo/xunji/step_motor/key/led 一条都看不见**；模型凭常识写出 `motor` 会被判幻觉且 `kind=client` 不重试——正确召回被当硬失败（该行为已由 8065fbfd 修复，可见性由 0f19a513/4950d98b 修复）。
- **根因三叠加（修复前）**：① `PERIPHERAL_TERMS` 无「小车/电机/循迹」；② 词表行级兜底给命中行全部 `lib_modules` 各 +1（感知传感器行 49 方案 → 40+ 传感器白得 1 分）；③ 46 条并列 1 分、40 条 0 分，预算只装 34 条，tie-break 是 slug 字典序。
- **守卫**：`tests/test_preselect_coverage.py`（6 组真实题面关键模块可见 + 全库可见不变量）、`tests/test_manifest.py::test_lean_summary_lines_fit_preselect_budget_for_real_library`（全库瘦身行 ≤ 预算 −5KB）。

### 5.2 🟠 P1：beep 模块声明 0 引脚，代码却直接驱动 BUZZER_GPIO/PIN —— ✅ 已落地（工单 beep-pin-declaration/01，2026-09-08，提交 96e739d9）

`library/modules/beep/code/beep_stm32.c:10` 用 `BUZZER_GPIO/BUZZER_PIN`（宏归属 `config` 模块，beep 未声明 pins 也未声明依赖）。后果：绑定界面没有蜂鸣器脚、默认布局白名单看不见它、门禁不报冲突——**实测 `beep` + `jq8900` 同吃 PA15 门禁静默通过**。全库扫下来唯一一处（`debug_uart` 也驱动 LED/BUZZER，但声明了 `config` 依赖，链是通的）。修法：补 `pins` 一条（`gpio_out`，`macros=["BUZZER_GPIO","BUZZER_PIN"]`，默认 PA15）+ 加结构测试「模块 .c 用到的 pin_config.h 引脚宏必须被本模块或其依赖声明」。

### 5.3 🟠 P1：20 个模块无选购方案挂接（wordlist lib_modules）—— ✅ 已落地（工单 library-hookup-and-invariants/01，2026-09-08，提交 6ca1139d）

后果：买件指引不标「库内已有」；预筛少一条 lib_boost 加分路径。真正该补：`servo`（舵机）、`step_motor`、`oled`、`ml_mpu6050`、`led`/`beep`/`led_beep`（声光提示器件行 0 方案）、`key`。其余（adc/delay/filter/uart/config/debug_uart/digit_uart/imu_uart/zigbee_*）为内部件可不挂。

**已落地**：8 个器件 slug 全部挂接（声光提示器件组补 3 方案、执行机构 +1 方案并给舵机方案挂 servo、显示模块 +1 方案、感知传感器 +2 方案）；两向守卫进测试（器件必挂 / 内部件不许挂）；审计 `[词表] 未被任何选购方案引用的模块` 20 → 12（剩余全是内部件）。配套：默认词表完整 wire 8259 → 8849，`WORDLIST_PROMPT_BYTES` 8500 → 9200（mspm0 最坏形态余量 727B → 378B，已记账；后续加内容应先瘦身）。

### 5.4 🟡 P2 三条

- **硬件身份字段 46/170 平台条目为空**（核心件为主：motor/pid/servo/oled/led/key…）—— 🟡 **部分落地（2026-09-08，工单 identity-fields/01-04）**：判据归位单源 + 内部件/协议切片显式豁免 + 能核实出处的真器件回填 + 剩余待补落清单。缺口 46 → **13**（且 13 条全部在工单 04 待补表里逐条有据），明细：
  - **判据单源**（01）：`library.MODULE_KIND`（DEVICE / INTERNAL / PROTOCOL，未登记 = 器件，逐条中文理由 `MODULE_KIND_REASONS`）+ `module_kind` / `requires_identity` / `device_slugs` 等判据函数；词表守卫（`tests/test_wordlist.py` 删手写名单）、参考关联豁免、身份字段守卫三处引用同一处，`tests/test_library_invariants.py` 与 `tests/test_skeleton_mapping_coverage.py` 加不矛盾断言。**修正三处漂移**：`zigbee_link` 判器件（原参考豁免理由写「协议切片」）、`huidu` 判内部件、词表把 `coord_detect`（K230 帧解析切片）从 K230 方案移出（只挂 `k230`）。
  - **豁免落地 + 双向守卫**（02）：内部件 10 + 协议切片 3（24 个平台条目）身份字段必须为空、器件必须齐字段——`test_device_modules_declare_identity_fields` / `test_internal_and_protocol_modules_have_no_identity_fields`；红证用临时副本注入实测（给 `delay` 填 kit → 红；清空 `motor` kit → 红，证据记工单 02 Comments）；audit `[身份]` 行改报「真器件缺口」并与测试同源取判据。
  - **回填**（03）：9 条 / 6 slug 按可核实出处回填（motor·xunji·pid·servo ← 库内同硬件条目；oled·k230 ← wiki 手册页 / 庐山派板页），URL 全部 HEAD 200 实测，零编造。附带修正 `tests/test_lckfb_attribution.py` 的判据缺陷（原按 `source_url` 反推「wiki 派生」，把原生移植驱动的硬件出处页误判成源码缺来源标注；改取代码事实 = 头部来源块）。
  - **剩余 13 条 / 7 slug 待补**（04，`beep` / `ir_beam` / `key` / `led` / `led_beep` / `step_motor` / `zigbee_link`）：立创 wiki 模块手册索引里没有对应器件页（`probe_backlog_sources.py` 可复现），逐条依据与后续核法见工单 04；待补清单同时钉在 `tests/test_library_invariants.py::IDENTITY_BACKLOG`（strict-xfail 用例，补齐即 XPASS 判失败、逼摘标记）。
  - **未做**：`led` / `key` 的「板载资源是否用入门教程页作 source_url」口径待定（工单 04 记录）；5.5 四条遗留本轮不动。
- **骨架「模块→参考例程」映射只覆盖 18/93**（`reference_library.py` `MODULE_PERIPHERAL_TERMS`）—— ✅ 已落地（2026-09-08，工单 preselect-visibility/03-05，提交 1b8c9a35 / 459b0cde）：判据归位为「每模块至少一个词项命中参考条目标题」（按模块算）+ 全库模块必须映射或显式豁免（`MODULE_REFERENCE_EXEMPT`，14 条内部件/协议切片）；参考库补 19 条器件条目（5 条救活 6 个死映射 + 14 条器件类别合集，素材 = lckfb 手册原文 / 库内代码切片），`PERIPHERAL_TERMS` 补 17 个器件类别词，映射 18 → 79 条；`tests/test_skeleton_mapping_coverage.py` 两条 xfail 全部转绿（93 模块全覆盖）。复测探针 `probe_term_effect.py` / `probe_unmapped.py`。
- **批次快检脚本没进 CI** —— ✅ 已落地（工单 library-hookup-and-invariants/02，2026-09-08，提交 6ca1139d）：21 个 sweep 脚本里「对全库永远成立」的 7 条搬进 `tests/test_library_invariants.py`（slug 与目录名一致 / 声明文件存在 / 条目文件无重复 / 依赖不悬空 / 依赖无环 / 词表引用存在 / 模块有简介），红证用临时副本注入破坏实测四类全红；批次快照值不进测试（历史快照会失效）。

### 5.5 已知遗留（CONTEXT 自记，本次复核仍在）

mq4-9 描述措辞未统一；77 条目全部未上板真机验证；oled 词表方案级缺口；A 类 3 页 mspm0-only 例外。
