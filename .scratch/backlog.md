# 待办计划（backlog）

后续可做的优化清单（2026-08-19 记录，按需立项走 workflow）。

> **台账现状（2026-09-24 全盘复核）**：各节要么已落地、要么已落到工单并 resolved——**没有「代码可做」
> 的净待办**。当前悬着的只有三类：① **人为阻塞**：§5.4 剩 6 slug / 11 条硬件身份字段等用户给
> 「实际买过那件实物」的链接（工单 `identity-fields/06`，同时是挂账单 `real-acceptance/01` 的 D1）；
> ② **已拍板维持现状**（不算待办）：§7 的 B 候选与「容量当约束」；③ **已记但未开单**：§20（CCS 工程名
> 写死 `mspm0_project`，要改得先拍板「改 `.project` 名会不会碰坏 CCS build config 自引用」+ 一次真机实测）。
> 另：§5.5 里「mq4-9 描述措辞未统一」「77 条目全部未上板真机验证」两条**未被该节 ✅ 段明说收口**，
> 本轮如实标出（前者是措辞问题、后者是真机面，都不阻塞发版）。本轮同时按工单实况改正了两处陈旧标记：
> §6.5 的 `full-download/07` 行（已 resolved）与 §7 标题（A 已落地）。
>
> **台账现状（2026-09-27，`backlog-closeout` 批收口后）**：可做的净待办**再度清零**——
> §25 的「记而不修」（界面体量）与 §5.5 的「mq4-9 措辞」两条已落地；§24 那两条"明确没修"
> 一条已修、一条核实后**开了新单**（`backlog-closeout/05`，库更新路径的元数据裸写）。
> 现在悬着的是四类，**逐条写清"为什么不是待办"**（免得下一轮又当新发现重开）：
> ① **人为阻塞**：§5.4 的 6 slug / 11 条身份字段（要用户给实物链接）、§5.5 的「77 条目未上板」
> 与 `hwcheck-acceptance/05` / `hwcheck-hardening/08`（要真板子）——机器代不了；
> ② **明确划走的边界**：跨进程并发（单进程应用）、强杀残留清扫、母版"目录换入 × 删 meta"窄缝
> （已承认残留）——`record-write-hardening` spec 的「范围外」，本批不翻案；
> ③ **尺子不是功能**：§15 的 C7（73 个私有符号公开化，量"测试还翻不翻墙"的进展）；
> ④ **有条件才能做**：§20 候选①（生成工程赛题级重命名，要一次 CCS 真机实测）、
> `tools/update-app.py` 的同款临时名（要先把结构守卫的扫描面扩到 `tools/`）。
> **本批自己产生的两条新账**（都是"要另开单"的性质）：`backlog-closeout/05`（元数据原子写）
> 与 §26 记的库层预热口径（改库内容要跟两平台编译矩阵）。

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
  - **剩余 13 条 / 7 slug 待补**（04，`beep` / `ir_beam` / `key` / `led` / `led_beep` / `step_motor` / `zigbee_link`）：立创 wiki 模块手册索引里没有对应器件页（`probe_backlog_sources.py` 可复现），逐条依据与后续核法见工单 04；待补清单同时钉在 `tests/test_library_invariants.py::IDENTITY_BACKLOG`（strict-xfail 用例，补齐即 XPASS 判失败、逼摘标记）；`zigbee_link` 已补后剩 6 slug / 11 条，**人工取源队列 = 工单 `identity-fields/06`（ready-for-human）**。
  - **未做**：`led` / `key` 的「板载资源是否用入门教程页作 source_url」口径待定（工单 04 记录）；5.5 四条遗留本轮不动。
  - **2026-09-19 第三轮复核（发 v1.2.2 时顺带做的）**：工单 `identity-fields/06` 的 6 slug / 11 条
    仍**取不到可核实出处**——本轮又实测一轮 Web（立创商城 / 厂商页 / 内容站），命中的仍是
    元件级商品页、资料站转载或 B 站视频，按工单 04「裁决一」三条都不算。**本轮显式记为
    「不阻塞 v1.2.2 发版」**（全文与逐条排除理由见 `.scratch/identity-fields/issues/06-*.md`
    的 Comments 与 `.scratch/release-v1.2.2/spec.md` 的「范围外」）。这 6 条卡在
    「要的是**用户实际买过的那件实物**的链接」这一步，机器代不了。
- **骨架「模块→参考例程」映射只覆盖 18/93**（`reference_library.py` `MODULE_PERIPHERAL_TERMS`）—— ✅ 已落地（2026-09-08，工单 preselect-visibility/03-05，提交 1b8c9a35 / 459b0cde）：判据归位为「每模块至少一个词项命中参考条目标题」（按模块算）+ 全库模块必须映射或显式豁免（`MODULE_REFERENCE_EXEMPT`，14 条内部件/协议切片）；参考库补 19 条器件条目（5 条救活 6 个死映射 + 14 条器件类别合集，素材 = lckfb 手册原文 / 库内代码切片），`PERIPHERAL_TERMS` 补 17 个器件类别词，映射 18 → 79 条；`tests/test_skeleton_mapping_coverage.py` 两条 xfail 全部转绿（93 模块全覆盖）。复测探针 `probe_term_effect.py` / `probe_unmapped.py`。
- **批次快检脚本没进 CI** —— ✅ 已落地（工单 library-hookup-and-invariants/02，2026-09-08，提交 6ca1139d）：21 个 sweep 脚本里「对全库永远成立」的 7 条搬进 `tests/test_library_invariants.py`（slug 与目录名一致 / 声明文件存在 / 条目文件无重复 / 依赖不悬空 / 依赖无环 / 词表引用存在 / 模块有简介），红证用临时副本注入破坏实测四类全红；批次快照值不进测试（历史快照会失效）。

### 5.5 已知遗留（CONTEXT 自记，本次复核仍在）

mq4-9 描述措辞未统一；77 条目全部未上板真机验证；oled 词表方案级缺口；A 类 3 页 mspm0-only 例外 —— ✅ **已收口（2026-09-09）**：例外成立（stm32 侧由 pid/us016 承接），不再算待办；单平台例外清单 + 逐条理由单源 = `tests/test_library_invariants.py::SINGLE_PLATFORM_REASONS`（新增单平台模块即红、承接者须真有 stm32 条目也机检）；README 原本指向的 `.scratch/materials-wiki/dkx-map.tsv` 未随仓库保存（映射轮次工作产物）→ 引用改指 `dkx-map-summary.md` + 重生成配方，三个读表脚本补缺失提示。

> **两条尾巴的现状（2026-09-27，`backlog-closeout` 批复核）：**
> - ~~**mq4-9 描述措辞未统一**~~ → **✅ 已收口**（工单 `backlog-closeout/02`）：九条 MQ 系方案 note 收成
>   同一套口径（补「正向映射」、预热口径统一）；顺带把「预热 3-5 分钟」这个**手册里没有的数字**
>   退回有据措辞（评审自读盘发现那数字的出处是 `ms1100.md`，与 MQ 系同批入库疑串台）。
>   新守卫 `tests/test_wordlist.py::test_default_wordlist_mq_family_notes_*`（两条不变量）。
>   **仍在的账**：库层（`library/modules/mq*/**` 的 manifest/code 注释）还写着两组不同口径，
>   要改得跟一次两平台编译矩阵——见 §26。
> - **77 条目全部未上板真机验证** → **维持挂账**（要真板子，机器代不了；与 §5 的真机面同一条）。

## 6. 真机验收第十六轮（2026-09-10）验出/记下的待修项 —— ✅ 全部落地（02–11 十一张工单均 resolved，2026-09-18 复核）

**入口（含每单的新会话提示词 + 优先级 + 依赖）**：`.scratch/real-acceptance/issues/00-待修清单-新会话入口.md`。
本轮把挂账单 A–E 组里能跑的都跑了（45/50 勾完，详见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十六轮」），
过程里验出 4 条真问题 + 2 条口径/工具项，各自成单；后续又开出 08 / 09 / 10 / 11 四单（均落地）：

| 工单 | 级别 | 一句话 |
|---|---|---|
| `real-acceptance/02` | 🔴 | gmake/tiarmclang/SysConfig 报错解析缺口：真机 exit=2、SysConfig 报 7 条引脚冲突，产品读成 **0 错 0 警**，修复链当「未定位到可修复文件」白跑一轮——**真机编译验收的判读底座** |
| `real-acceptance/03` | 🟠 | 推荐域拒绝（`SelectionError`）被吞成「查 key / 查余额」通用话术且 `kind=client` 免重试：本轮 14 轮真实推荐 **9 轮**栽在此，真实理由都是「oled 不支持多实例」这类一轮能自愈的手滑 |
| `real-acceptance/04` | ✅ | ~~推荐层互斥组未收敛：同组两成员同时推荐（`zigbee_uart` + `zigbee_link`），到生成门禁才 400；提示词已写「只推荐一个」，解析层缺校验~~ **已落地（resolved）**：解析层确定性收敛（零额度）——`build_module_selection` 按 `ManifestSummary.exclusive_group` 投影「组 → 候选成员」，同组多成员只留模型清单首个，其余剔出顶层 `modules` 并记进 `dropped_exclusive_members`（需求层不改写 = 模型证据保留）；载荷契约 `exclusive_groups[].recommended` 收紧为**组内 ≤1** + 新增 `candidates` / `dropped` 可见字段（前端标「同组互斥·未选中」，点组卡即换选）；`run_recommendation` 出卡前兜底 + `--reuse-recommend` 旧载荷补刀（`converge_recommendation_payload` 幂等，缓存不改写）；生成侧 `HARD_EXCLUSIVE_PAIRS` 门禁**不动**。真机 2026C/stm32 **不带 `--drop` 跑绿**（UV4 0 错 0 警） |
| `real-acceptance/05` | ✅ | ~~请求预算账本失真~~ **已落地（resolved）**：账本与实测对齐 + 尺寸断言口径。根因是三种记账病（账本的数来自修复侧被误引用 / select 2KB 与 fix-clarify-skeleton 10KB 两套余量魔数 / 最坏形态漏算预筛注记且合成结构测试比真实库小 34KB）；做法：段级账本可执行（Σ段 + JSON 壳 = 实发，逐字节对账）+ 统一余量单源 `budget.REQUEST_RESERVE_BYTES=2048` + 全文段重分配 25600→23400 + 修掉 `_fit_segment_wire` 标注超预算（段级预算此前不是实发上界）+ 贴边/拒发留段级 breakdown。实测 mspm0 128405B/619B → **125638B/5434B**；真机 2021F/stm32 4 轮收敛终态 done 无「请求体过大」 |
| `real-acceptance/06` | ✅ | ~~CCS 三件套跨安装目录混搭（编译器 ccs2050 + SDK/SysConfig ccs2051）实测可用，但环境体检不说明来源根~~ **已落地（resolved）**：体检补「三件逐件独立探测 / 可能跨目录」说明行 + 逐件安装根（`ccs_tools_status` 新增 `root`）+ 设置页三行提示；**探测行为未改——2026-09-18 拍板「维持现状」**（「同根优先」与「认顶层独立安装」两条都不做，见第 7 节末「拍板结果」） |
| `real-acceptance/07` | ✅ | ~~浏览器真机验收四坑固化~~ **已落地（resolved）**：`.scratch/browser-harness.mjs` 两助手（`expandCard` / `pollUntil`，零依赖、假 page 可测）+ 挂账单 01「B 组统一前置 · 姿势清单」；B24 脚本改用它真机复跑 **19/19 全绿** |
| `real-acceptance/09` | ✅ | ~~推荐失败被报成「AI 服务拒绝了本次请求（API key / 余额）」~~ **已落地（resolved）**：真因是**输出侧本地判决被塞进 `kind=client`**（观测面 `http_status=200` / `parse_status=parse_error` / `attempts=1`；余额实测 21.57 CNY、最小调用 200）。做法：新增 `ERROR_KIND_OUTPUT` 分流 + 三处「借 client」抛出点改归 output + 新增 `OUTPUT_TRUNCATION_HINT` 单源判据（截断/超长确定失败免重试，畸形照 parse 快重试）+ 文案改「这次返回的内容无法使用…不是登录凭据或账户问题」。与 `03`（域拒绝）同源病：本地判决错报成上游拒绝 |

**不做（已裁决）**：SysConfig 外设引脚冲突的「生成期门禁」不单独立项——本轮把它作为 `real-acceptance/02`
的附件事实记录（门禁现有检查面覆盖不到 SysConfig 语义级 `associatedPins` 冲突，且修复方向未定），
等 02 落地后再看是否需要独立门禁单。
**已更新（2026-09-17）**：上一条的「等 02 落地后再看」已到期并做掉——生成期引脚冲突门禁 +
「一键配置真能解默认撞脚」两单落地（`.scratch/pin-conflict-gate/`，均 resolved）。

**小尾巴收口（2026-09-18）**：本节标题长期停在「6 张工单待做」而 02–11 早已全部 resolved
（台账不实，本轮修）；同时把 `real-acceptance/09` 的复现探针从两份「runpy 套一层」的副本
（锚点版 + 抓包版，后者第三个锚点随 05 尾巴改缩进**永久失效**、每次跑静默丢一路取证）合并进
`.scratch/recommend-domain-reject/probe-16-recommend-live.py --capture-raw`，并给探针补
UTF-8 stdout（原锚点版是崩在 GBK 编码上的）。第 7 节的两道候选已拍板（A 已落地 → 工单 `pin-capacity/01` / B 维持现状），
见本节末「拍板结果」。

## 6.5 完整包 / 发版打包线（2026-09-13 开单，同日补登台账）

这两单是 09-13 发 v1.1.0/v1.1.1 时开的，**先前没登记进本台账**（第 6 节与
`.scratch/tracker-audit/2026-09-09-在途盘点.md` 都停在 09-12），导致每轮盘点会漏看——
本轮补登。真机挂账单里的同源进度见 `.scratch/real-acceptance/issues/01` 的 G 组。

| 工单 | 级别 | 现状 |
|---|---|---|
| `full-download/07` | 真机项 | **✅ resolved（2026-09-24 收口）**——原文留档：v1.1.0/v1.1.1 发版 + 沙箱「模拟用户机」演练已勾（G1 前两步），剩 G1 后三步极端场景。**收口依据**：该单自述「唯一剩下的是真发一次 Release」，而该动作已由挂账单 `real-acceptance/01` 的 **G1 三段**在 2026-09-13 / 09-18 做掉（v1.1.0 / v1.1.1 真发布 + 沙箱演练 + 三项极端场景：弱网取消 10/10、断线重试 12/12、校验失败 11/13 → 已修转绿），此后又连发 v1.2.0 / v1.2.1 / v1.2.2；7 个 checkbox 已按在盘证据逐条补勾 |
| `full-download/08` | 🔴 真隐患 | **✅ 已落地（resolved，2026-09-13）**：两个打包器字节口径不一致（`git archive` 的 `core.autocrlf` 转换 vs 读工作树）——v1.1.0 实测 3474 个共有文件里 **926 个字节不同、内容差异 0**（v1.1.1 为 929 个，本轮用新判据在真实发版包上复核）。修法：把 `git archive` 钉 `-c core.autocrlf=false`（实测 `.gitattributes` 的 `-text` 压不住它），新增 `src/contest_generator/pack_update.py` 打包核心 + 14 例跨包守卫；真实仓库复跑 **共有文件 3480 个、字节差异 = 0**。附带修掉空 `removed.txt` 被 `gh` 拒收（`HTTP 400`）的老坑 |

## 7. 选中集引脚容量预警 —— ✅ 已收口（A 已落地 2026-09-18 / B 已拍板维持现状）

**问题**：母版默认布局把板子排针 IO 铺满（mspm0 31 / stm32 32），默认脚按「同选概率最低者
重叠」。选中模块一多，落点需求就超过板上可用脚 → **这个选中集在这块板上物理不可实现**，
用户无论怎么点「自动配置」都编不过（不是算法没解，是脚不够）。

**取证（只读探针 `.scratch/pin-capacity/probe-01-measure.py`，零额度、不烧调用）**：14 个真机
推荐集（第十六~二十二轮 done 载荷 + 2 份生产缓存），对当前库/板核算 → `verify-01-measure.txt`：

- **8/14（57%）不可解**（解完仍有 conflict 组）：mspm0 5 样本里 3 个（未解 3/4/5 组）；
  stm32 9 样本里 5 个（未解 1~9 组，最狠 2021F 15 模块剩 9 组）；
- **分离性干净**：`Σ角色落点 ≤ 板上可用 IO` 的 6 个样本**全部可解（未解组 0）**；
  `落点 > 可用 IO` 的 8 个样本**全部有未解组**（合计 31 组）——本样本上 14/14 预测正确；
- **平台语义要分开读**：mspm0 同脚多实例 = SysConfig 硬拒绝（**编不过**，现由门禁拦下）；
  stm32 默认撞脚按 ADR 0010 是**提示语义**（编译能过、运行期接线坏，引脚卡只标 ⚠）。

**两道候选（都未立项，等真机现场或用户拍板）**：

| 候选 | 内容 | 需要什么才动 |
|---|---|---|
| A. 门禁容量诊断 | 门禁命中时把「改绑或去掉冲突模块」升级为可操作数字：「落点 42 > 可用 31 脚、空闲脚已用尽，至少要去掉/替换 N 个模块」；判据复用现成两件（solver 剩余组 + 落点数 vs 可用 IO），前端零改动 | **✅ 已落地（工单 pin-capacity/01，2026-09-18）**：`pin_capacity.py` 域模块 + 门禁数字段；只升文案不增拦截、前端零改动；真机 2026H 文案带 13/42/31/27/7 组/剩 3 组/至少去掉 3 |
| B. 口径复议 | ① stm32 默认撞脚是否从「提示」升级为「拦」（ADR 0010 复议：编译能过但接线错）；② 推荐/选择侧是否把容量当约束（像互斥组那样，别一次选满 15 个模块） | **❌ 维持现状（2026-09-18 拍板）**：① 不升级为硬拦（ADR 0010 不动，硬拦会改掉「编译能过」的现状）；② 「容量当约束」另立条目、不动推荐链路，等 A 的真机现场说话 |

**注意命名**：本仓库的「预算」已被 `budget.py` 占用（LLM **请求体**字节预算）——真要立单
请叫「引脚容量」之类，别用裸「预算」。

**用法边界**：落点数只是**上界**（合法共享会省脚），故这条线适合做**预警**；硬拦必须用真实
可解性判定（`auto_assign_bindings(resolve_default_conflicts=True)` 的剩余组，即 pin-conflict-gate/02）。

**拍板结果（2026-09-18，用户拍板；同时段还有四处留档，全文见
`tracker-audit/2026-09-09-在途盘点.md` 末「待拍板项的拍板结果与留档」）**：

- **A 放行 → ✅ 已落地（工单 `pin-capacity/01`，2026-09-18）**：门禁命中时补可操作数字（落点 /
  可用脚 / 至少去掉几个模块），**只升文案不增拦截**，前端零改动（域模块 `pin_capacity.py` +
  门禁数字段；真机 2026H 文案带 13/42/31/27 组/剩 3 组/至少去掉 3）。立单命名用了「引脚容量」。
- **B 维持现状**：stm32 默认撞脚**不**升级为硬拦（ADR 0010 不动）；「容量当约束」另立条目、
  不动推荐链路，等 A 的真机现场说话。
- **其余：D1 六个器件的 `kit` + `source_url` 仍等用户给链接**（未拍「永久不补」→
  `MODULE_KIND` 不动）。

## 8. 沙箱真机演练第二梯队 B1–B5 开出来的三张单（2026-09-18；三张全部已修 **且已随 v1.2.2 发到用户手上** 2026-09-19）

演练本体（spec + 五张工单 + 脚本 + 原始证据）在 `.scratch/sandbox-drill/` 与
`.scratch/verify-gate-drills/`；下面是**演练暴露的真缺陷/待决策项**，都已开单，别漏看：

> **2026-09-19 收口（两段，第二段是当天下午的 v1.2.2 发版）**：
> ① 三张单全部落地，当时**没有发版**——`update-orphan-files` 的修复在打包器与删除清单里，
> 要真机 drill-01 判据成立就得换线上资产，拍板留给下一个版本号；
> ② **当天下午发了 v1.2.2 把它们带上**（工单 `.scratch/release-v1.2.2/01-05`）。真机
> `drill-01` 复跑：沙箱真 v1.1.1 → 走产品端点升到 1.2.2，**判红 0 / 卡住 0 / PASS**，
> `not_in_official` 1482 → **6**（那 6 条经决定性实验证明是更新器那一步 pip 现写的
> `egg-info`，不是包内容），「官方缺失 0 / 内容不同 0」两条全绿。
> 顺手做掉的第四条：`src/contest_generator.egg-info/**` 摘出产品文件（两个包都不再发）。

| 工单 | 级别 | 一句话 | 证据 |
|---|---|---|---|
| ~~`update-restart-stale-service/01`~~ ✅ **已修（2026-09-19）** | ~~🔴 用户可见~~ → **🟠 卫生**（射程更正） | **从旧版点「一键更新」：文件全换成新版，但跑着的服务还是旧版**（发起更新的那一代没传停服端口 → 旧进程没被停 → 启动器判 `already_running` 只开浏览器）。**射程更正**：更新器的默认端口与普通用户的端口都是 8000，**默认端口的人不受影响**——只有端口 ≠ 8000（沙箱 / 同机双实例）才中招，且只有**小发版**那条路缺 `--port`；原文「那批老用户都会中招」是推断过头。**修法**：启动器加版本一致性判据（新 CLI `tools/launcher-stale.py` + 谓词 `update.is_stale_service`；非 `stale` 一律走原路），顺手补上「起服务前先建数据目录」。**修复随 v1.2.1 资产重发出去**（同 tag 换资产），真机 drill 复跑 `restarted_by_updater=true` / `served=1.2.1` | `verify-gate-drills/verify-01-upgrade.{txt,json}`（最新一轮）+ `-b1-failed.*`（原失败证据）+ `.scratch/update-restart-stale-service/`（spec / 工单 / 探针 / 判据强度 9/9） |
| ~~`update-orphan-files/01`~~ ✅ **已修（2026-09-19，根因更正）** | 🟠 卫生 | 原判「删除清单只覆盖上一版 → 落后两版留下 **1483** 个孤儿」**与实测不符**：重新量（`.scratch/update-orphan-files/measure-sets.py`）后，那 1481 个 `library/revise-backups/**` 是**本轮小发版包自己写进去的**（沙箱里 mtime 全是解包那一刻，且就在 `firstep-update-v1.2.1.zip` 的条目表里），另 1 个是 `*.exe`；两者都是**完整包刻意排除、小发版包照发**。真根因 = 「哪些文件算产品文件」被实现了两遍且已漂移（小发版多发了 1481 个本机库备份 + 漏发了 `00-START-HERE.txt`——v1.1.1 的用户走小发版升级永远拿不到它）。**修法**：判据单源（`full_pack.product_file_reason` / `is_product_file`，两个打包器共用）+ `library/revise-backups/**` 移出 git 索引 + 删除清单改**累计口径**（`cumulative_removed`，跳版升级也清得掉）。**本轮不发版**（真机 drill-01 要下到修好的包，留给下一个版本号），验收 = 静态守卫 + 判据强度探针 6/6 + 本机离线演练 | `.scratch/update-orphan-files/`（spec / 四张工单 / 量具 / 离线演练 / 探针）+ `verify-01-upgrade-aftercare.txt`（原构成一节） |
| ~~`update-content-mismatch-retry-cap/01`~~ ✅ **已修（2026-09-19）** | 🟡 决策单 → **已拍板选 1** | 持久「内容与清单不符」→ 永远 downloading + 每轮整卷重下（spec 第 122 行明文如此，**不是实现 bug**）；真机量出 150 秒 6 次重试、台账起始偏移全 0、约 45 GB/小时量级。**拍板**：同一卷**连续 5 次**内容不符 → 转终态 `failed`，中文说清「重下不会有变化」（网络类失败仍无上限）。真机复跑：30.6 秒收敛、`terminal_reached=true`、`retry_count=4` | `.scratch/update-content-mismatch-retry-cap/`（spec / 决策单 / 实施单 / 探针 3/3 / `verify-real-machine*`） |
| ~~`update-verify-failure-leftovers/01`~~ ✅ **已修（2026-09-19）** | 🟡 卫生（可自愈） | **不可重试**的校验失败（清单 size 与对端总长矛盾）终态 `failed` + 中文话术都对，但 `updates/full/` 里留下**整卷半成品**（实测 3,961,701 B）+ 边车，与 spec 第 147 行「校验失败一并删除」不符；线上完整包场景 = 失败后白占 ~765 MB。**修法**：任务层共享原语的异常路径按分类单源区分——不可重试的 verify 清掉半成品与边车，网络/取消/可重试照旧留断点。真机复跑：`verify-size` 两条判据都成立、`cut-retry` 12 条全成立 | `.scratch/update-verify-failure-leftovers/`（spec / 两张工单 / 探针 3/3 / `verify-real-machine*`）+ `verify-02-degraded.{txt,json}` 的 `verify-size` 一节 |



## 9. 硬件检测（module-hwcheck）收尾时撞出来的两条既有缺陷（2026-09-20，已开单）

工单 `module-hwcheck/09` 补 pilot 配方 + 跑真编译矩阵时撞出来。配方侧本身全过：
**17 格校验通过；17 格 + 2 格全选里 16 种形态真编译 0 error / 0 warning，
3 格「生成前拦下」**（`mspm0 adc` / `mspm0 xunji` / `mspm0 全选`）。两条都不是配方的问题：

- **检测页遇到默认脚冲突没有出口**：mspm0 上「调试串口 + OLED」是检测页的默认形态，
  而母版里 `OLED_SPI_RES = PA22 = DEBUG_UART RX` —— **mspm0 任何器件（含"一件都不选"）
  在默认双通道下生成必 400**，而检测页没有引脚配置入口（400 的出路文案指向赛题页的
  「自动配置」）。赛题链路同一条冲突有出口（`/api/bindings/auto` 会把它移到 PA24，
  读数在 `.scratch/module-hwcheck/probe-09-contest-parity.txt`）。
- **`ADC12_0.adcPin7`（PA22）角色未登记**：选 adc / us016 / mq2 这类共读 MEM 的件时，
  只要开任一输出通道就 400（那颗脚只有选 flame 时才有主人，冲突求解器解不开）；
  两个通道都关则能生成但逐件小节按设计不渲染 —— 这几格到不了板（xunji 也因 HUIDU
  的 P2/P3 撞同样两个通道而中招）。

细节、验收清单与候选修法：`.scratch/hwcheck-pin-conflict-exit/issues/01-default-pin-conflict-no-exit.md`
（矩阵读数：`.scratch/module-hwcheck/probe-09-compile-matrix.txt`）。

## 10. 前端装载清单去化石（2026-09-20，工单 frontend-import-fossils/01 已落地）

一次架构评审（improve-codebase-architecture）把「页面装载清单」挑出来：页面唯一
`<script type="module">` 的 import 清单是两轮模块化（纯函数迁 fx/、tab 迁 ui/）留下的**冻结
产物**——69 条 import / 337 个名字里 **259 个宿主正文一次都没用过**，删改其中任一导出即整页
`SyntaxError`（2026-09-12 真机现场，服务端全 200）。本轮把清单缩到 78 个真在用的具名 +
5 条纯装载，并新增守卫 `tests/js/import-usage-guard.test.mjs`（判据单源
`tests/js/import-usage.mjs`）钉住"页面不许导入它不使用的名字"。

本轮**没做**的四件（各自另立，别当已做）：

- ~~**把接线搬出 HTML**（`js/boot.js` + 给 import 时接线的 ui 模块补显式 `init()`）~~ ✅
  **已落地**（工单 `frontend-boot-module/01-05`，2026-09-21，见本节末）：装载根搬进
  `static/js/boot.js`，index.html 只剩一条装载标签；11 个"靠被加载才接线"的模块各得显式
  `init*()`（求值期零接线进闸门）；`static-import-guard` 与 `fx-guard` 的 337 行名字登记表
  **已退化成结构不变量**（index.html 零定义 / boot 零顶层定义 / 每个 fx/ui 模块从 boot 可达），
  导出存在性改由**全图 import↔export 对账**兜住。
- ~~**`tests/browser/` 接进闸门**~~ ✅ **已落地**（工单 `ui-dom-contract-gate/01` + `03`，2026-09-20，
  见第 13 节）：先修绿再接手——**旧读数「6 绿 3 红」本身也不实**，HEAD 实测是 14 绿 7 红
  （4 条夹具自杀的连锁假红 + 3 条真红全非产品缺陷）；现在 prepush 与 CI 各有一支与前端门禁
  并列的浏览器门禁，四个 spec / 26 条用例一条命令跑完（≈78s）。**落点又随装载根搬家补了一条
  `static/js/boot.js`**（工单 frontend-boot-module/02）。
- **删 index.html 里的迁移墓碑注释**（"已迁至 …"那一大段，数百行）——历史记录，本轮按 spec
  原样保留。**它们现在住在 `static/js/boot.js`**（随宿主块整块搬过去，逐字未动）。
- **`ui/delivery.js` 的 window 挂桥**（`Object.assign(window, {...})`）与 app.js 规则 3
  "不挂 window 桥"相抵——既有事实，本轮只记账不改（工单 03 把它挪进了 `initDelivery()`，
  语义不变：仍在上线前装好）。

**本节挂账结清记录（工单 frontend-boot-module，2026-09-21）**：`01` 判据单源 + 红证（base 钉
`b52022f1`、自校验选错即失败、11 条强度自检）；`02` 装载根搬家（机械判定 7/7：块逐字搬运、
index.html 零 import、555 个 id 不变）；`03/04` 11 个模块显式 `init()`（求值期接线 96 → 0，
冒烟记账 434 条多重集与改前逐条相同）；`05` 守卫退化 + 不变量进闸门 + 账本。
证据与探针在 `.scratch/frontend-boot-module/`（spec、5 张工单、红证 `red-proof.txt`、
搬家复算 `verify-move.txt`、冒烟 `smoke-*.txt`、普查 `survey-*.txt`）。

**退化时如实记账的两条代价** —— ✅ **两条都已结清**（工单 `export-surface-guard/01-03`，2026-09-21）：

- ~~**类型维度**~~：旧 `DOMAINS` 表 469 个名字里 28 个带 `typeof` 断言（如 `resetPinState: "fn"`），
  新判据只看"有没有被 import / 有没有定义"，**不管类型**。
  → **fn 轴已收回**：判据 T（`tests/js/boot-contract.mjs` 单源，守卫
  `tests/js/export-surface-guard.test.mjs`）——被调用的导入名必须解析成函数形态，跟随再导出链与
  函数别名链，解不开按违规算。**仍不守**：常量的**值**形态（number/string/object，那 28 条断言的
  另一半）——无法从用法派生，只能靠名单或生成式快照，与"拆掉名字表"的方向相抵，故明确不做。
- ~~**死导出清点**~~：全图零引用的导出改名或删除不再变红——评审点出 7 个：
  `CCS_PIECE_NAMES` / `maincScrollToRange` / `codeEditorHighlight` / `HWCHECK_VERDICT_FALLBACK` /
  `BUY_DECISIONS_KEY` / `SETTINGS_DEFAULT_COLLAPSED` / `wfNum`（更该做的是**清点后删掉**它们，
  而不是再养一张表）。
  → **判据 D 已立并清点完毕**：每条导出必须被一条 import 边消费（消费者 = 页面图 ∪ tests/js ∪
  tests/browser；口径是**哪条导出**），111 处清成 **0**（110 处摘 `export` ＋ 1 条零引用函数
  整条删）。**实测推翻了挂账时的假设**，两条更正：① **体量不是 7 而是 111**（评审那 7 个用的是
  "全仓零引用"这个更松的口径）；② 那 7 个**不是死代码**，是"活的定义 ＋ 多余的 `export`"
  （被本模块内部或 window 探针桥用着）——真正该整条删的只有 1 个
  （`ui/generate-recommend.js::groupChoiceGap()`）。
  证据：`.scratch/export-surface-guard/`（spec、3 张工单、红证 `red-proof.txt`、清点
  `verify-sweep.txt` / `diff-proof.txt`、普查 `survey-*.txt`）。

**本轮暴露、另立的新候选（别当已做）**：

- **零调用私有死函数**：`ui/generate-fix.js::runCompileOnce` 摘掉 `export` 后全仓只剩定义行
  1 处引用（工单 02 §⑨-2 实测）。按 spec 口径它不在判据 D 的清单里（**从来就零消费者**——判据 D
  管的是"导出没人用"，不是"函数没人调"），本轮只摘关键字、**不删定义**。同类可用
  `probe-14-topic-pin.mjs` 的做法再查 `ui/hwcheck.js` 一侧。**未立项。**
- **9 处清点前就已死的模块级 import**（`WRITE_GUARD_ACTIONS` ×4、`resourcesOverviewHTML`、
  `readinessRowHTML`、`getMainCDiskDir`、`isTabSavable`、`resourcesToolbarHTML`）：
  `tests/js/import-usage.mjs` 的取数面**只有 `boot.js`**，所以"零未使用具名"这条判据对**模块级**
  没有证明力（工单 02 §②-3 记账）。 → ✅ **已结清**（工单 `module-import-usage/01-03`，2026-09-21），
  但**读数按实测更正了三处**：

  - **真实体量是 12 处，不是 17/18**。旧口径（`unusedImports`：正文只剥整行 `//`、按**源名**查）
    报 17 处 = **12 处真死 ＋ 5 处别名误报**。上面点名的 9 处里 **4 处 `WRITE_GUARD_ACTIONS` 是误报**
    （`import { WRITE_GUARD_ACTIONS as WG }`，正文写的是 `WG.fix` / `WG.revise` / `WG.task` / `WG.params`，
    **全都在用**；实测按同一错误口径是 **5** 处），真死的只有 5 处；另 **7 处**（`languageOf` /
    `downloadedPercent` / `getCodeTreeFiles` / `$` / `aggregateSelection` / `toastError` /
    `pdfDupRemainText`）**不在上面那 9 处的点名清单里** —— 注意口径：它们**不是"旧口径看不见"**
    （实测 `C − A = 0`：旧口径同样报出它们，只是工单没点名）。
  - **口径修对了**：「被使用」= 本地名出现在**代码**里（注释 / 字符串 / 正则 / 模板串**文本段**
    里的同名词不算；**模板表达式**里的算——naive 掩码会把它误判成死的，实测 33 处假红），
    再导出清单算消费，裸装载永远合法。掩码件扩了"模板表达式感知"模式
    （`boot-contract.mjs::maskNonCode`；`maskCommentsAndStrings` 语义一字不变）。
  - **判据面从装载根扩到全部 132 个模块并进闸门**（`tests/js/import-usage-guard.test.mjs`，
    前端门禁 1688 → **1691**）；12 处死 import 一次清掉（11 摘名 ＋ 1 整条删），
    另 **1 处级联**（`fx/core.js:115` 摘 `export ` 前缀）——**新发现**：一条死 import 会给判据 D
    当**假消费者**（`fx/core.js::downloadedPercent` 的唯一消费者就是本轮摘掉的那条死 import，
    不级联则判据 D 从 0 变 1）。
  - 证据：`.scratch/module-import-usage/`（spec、3 张工单、合成红证 25/25 `synthetic-red-proof.txt`、
    真红证 `red-proof.txt`（base 钉 `f1c9e1c7`，自校验有牙齿）、字节级重放 `verify-removal.txt`、
    diff 归因 `diff-proof.txt`（归不了因 0 处 / 尾换行不一致 0 个）、闸门强度 `guard-strength.txt`）。

评审同时发现的**同向候选**（都在前端）：ui 层（17,996 行 / 515 监听器）只有 2 个
测试文件 import 它，没有测试缝——✅ **已落地**（第 13 节，两层守卫 + 真浏览器行为契约）。
六条跨语言镜像里 `CODE_TREE_NAME_ILLEGAL`（文件名非法字符）与 `pinShareClass`（同脚多角色）
两条**已补上**（见第 12 节）。

## 11. webapp 收口（2026-09-20，同一份架构评审的候选 C2；工单 webapp-consolidation/01–02 已落地）

评审报告（**副本已入库**：`.scratch/ui-dom-contract-gate/architecture-review-20260920-1745.html`
——早先这里引的是 `%TEMP%` 路径，临时目录会被清，2026-09-20 改指入库副本）的复审结论「该做的只有两件半」里，
第 1 件就是本条（第 2 件是上面的第 10 节）：

- **检测页装配回域**（01）：硬件检测页的四段装配（约 483 行）从 `webapp.create_app` 搬回
  `hwcheck_board`（`hwcheck_view` / `HwCheckView` / `read_master_syscfg`）与 `hwcheck_recipe`
  （`load_library_recipes` / `sections_payload`），接口从 `AppContext` 收成显式路径 + 配置对象；
  结构钉 `tests/test_hwcheck_assembly_home.py` 钉住 webapp 的 hwcheck 族 import 面。
- **LLM 工作流观测一处**（02）：25 处手写的「预算 + 收集器 + 派发 + 结算」收成 `webapp.LLMRun`
  一个缝；守卫与红证在 `tests/test_llm_run.py`。
- 两单都**没做 route 分册**（评审同一段里也建议不做）：`tests/test_webapp.py` 那条按源码文本钉
  recommend 路由形状的 AST 守卫会把它判红，先改守卫形状才谈分册。评审的其余项：**C4 已落地**
  （见第 15 节）、**C6 已落地**（工单 `webapp-state-into-ctx/01–04`，2026-09-22，见第 17 节）、
  **C7（73 个私有符号公开化）仍挂账、未立项**——C7 只是**验收尺**（拿它量"测试不再翻墙"的
  进展），不是待办功能，别当任务排期。

## 12. C5a 两条裸镜像补上（2026-09-20，同一份架构评审的候选 C5a「2.5」；工单 cross-lang-mirror-c5a/01–02 已落地）

复审结论排在「两件半」之后的那半件。两条镜像各走仓库已有的一个成功先例，不新增第三套做法：

- **01 文件名校验规则 → 后端下发模型**（先例 `/api/bindings/matrix`）：非法字符集与长度上限的
  判据单源留在 `codeview`，经 `POST /api/code/open` 载荷 `name_rules` 下发；前端
  `treeNameValidate` 按运行时装载值判定，源码常量退化为启动兜底，由
  `tests/test_codeview.py::test_js_name_rules_fallback_mirrors_backend` 读 JS 真源码对账。
  **顺带补了两个 tdd 红证挖出来的既存缺口**：`create_code_entry` 此前完全不校验名称
  （超长名静默建出病态文件、含 `* ? " < > |` 的名字把 OSError 抛成 500），且补口必须逐段做
  （中间段是目录名，同样直达 mkdir）。
- **02 同脚多角色分类 → 生成对拍 fixture**（先例 `test_group_choice_mirror.py`）：场景表单一出处
  在 `tests/test_pin_share_mirror.py`（14 条，真实库内 slug + 真实板），期望值由后端
  `_shared_groups` 现算成 `tests/js/pin-share-mirror.fixture.json`，JS 侧复算 `pinShareClass`
  逐场景比对（只对账 kind）。**同时修掉一处已在误导用户的漂移**：后端 `_role_resource_keys`
  一直把 `adc` 归入「同一 ADC 实例 = 同一路模拟信号」（adc/us016/mq2 等共读 ADC12_0 的
  MEM0=PA24），前端漏了这一支 → 判 conflict 并在角色行提示「建议改线」，而那根脚由 syscfg
  单落点决定、改了就是另一条通路。

两条都在**闸门内**变红（pytest 面 + 前端 `node --test` 面，均已进 prepush 与 CI 的子集/整套）。

## 13. C5 卡的剩余部分：ui 层测试缝 + browser 用例接闸门（2026-09-20，工单 ui-dom-contract-gate/01–05 已落地）

同一份架构评审（`%TEMP%\architecture-review-20260920-1745.html`，副本已随工单入库
`.scratch/ui-dom-contract-gate/`）的 C5 卡里，除了上面第 12 节那两条裸镜像，剩下的两件：

- **ui 层第一次有了测试缝**（工单 02/04）。缝的位置 = **DOM**：模块绑哪些选择器、绑上之后用户
  做一个动作会看到什么。**两层守卫**——① 静态健全性（`tests/js/ui-dom-contract.mjs` + 用例，
  零依赖进前端门禁）：ui 里写死的 id 必须在页面真会出现的声明集合里（实测基线：声明 592 /
  ui 引用 510 / **差集 0**），每个 ui 模块必须从 index.html 沿 import 图到得了、被 import 的
  `init*` 必须有调用点；② 行为契约（`tests/browser/ui-contract.spec.mjs`，真页面 + 真后端）：
  本轮 5 条 / 3 个模块（guide 子页签四态、step-state 折叠 + 记忆落盘 + 刷新生效、welcome
  compact 行动路径 / 「不再显示」持久化 / 冷启动读记忆）。
  两条判据各带红证（静态那层：判据纯函数 + 内存注入 7/7；行为那层：真源码注入 + 逐字节复原 4/4）。
- **browser 用例接进闸门**（工单 01/03）。先修绿：HEAD 上实测是 **14 绿 7 红**（不是文档记的
  6 绿 3 红），7 条红里 4 条是夹具让服务中途自杀的连锁假红、3 条真红**全不是产品缺陷**
  （一条断言过期、一条抢跑、一条样本器件已被配方覆盖）。修法：夹具**不再设 `FIRSTEP_LAUNCHER`**、
  端口改成**每个 spec 各向内核要一个空闲端口**（原固定 8791 在三个 spec 顺序跑时必然自踩）、
  用例级隔离。然后接闸门：`tools/prepush.py` 新增与前端门禁**并列**的浏览器门禁，CI 新增
  `browser-suite` job。现在四个 spec / **26 条**用例一条命令跑完（≈78s），改动落在
  `tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/app.js` 时自动跑。

**仍然挂账的三条（各自另立，别当已做）**：

- **`index.html` 与 ui 的 id 耦合「改造」**：本轮只把它变成**可测的事实**（第一层守卫），
  **没动标记结构**。真要去掉那 555 个 id 级别的耦合，是另一件事（工单 frontend-boot-module
  也没动它：装载根搬家只挪 JS，555 个 id 一个没变）。
- ~~**把接线搬出 HTML（`js/boot.js` + 给 import 时接线的 ui 模块补显式 `init()`）**~~ ✅
  **已落地**（工单 `frontend-boot-module/01-05`，2026-09-21，见第 10 节末）：装载根 =
  `static/js/boot.js`，11 个模块显式 `init*()`，"求值期零接线"进闸门，两张名字登记表退化成
  结构不变量 + 全图对账。
- ~~**产品侧「F5 重载慢过 1.5 秒会被应用自己关掉」的竞态**~~ ✅ **已落地**（工单
  `launcher-exit-race/01-05`，2026-09-21～22，见第 16 节）：三层修法 = ① 登记（`register`）提前到
  `index.html` head 的内联脚本（**模块图之前**；放 `boot.js` 没用——ESM 静态 import 会先把整张
  图取完才求值）；② 文档实例令牌 `epoch = performance.timeOrigin`——旧文档迟到的告别**不许**
  注销新文档的登记；③ 退出调度显式化（布防 / 撤防 / 到点取走，三件事同锁）。
  `_EXIT_GRACE = 1.5` **保持原值**（它现在覆盖的是"旧告别 → 新页面自报家门"的到达抖动，
  毫秒级，不再覆盖模块图装载）。判据三处：产品侧 pytest（乱序 / 重复 bye / 宽限内 register
  撤销 / 多标签语义）、结构判据（`tests/js/boot-contract.mjs` 判据⑥ + 守卫
  `tab-register-guard.test.mjs`）、真浏览器 `tests/browser/launcher-reload.spec.mjs`
  （启动器模式：连续 8 次 reload 服务始终活着 / 拖慢模块图仍活着 / 最后一个页面离开服务自己停）。
  现场探针读数：修复前 10 轮第 4 轮命中自杀（`probe-00-order-before.txt`）→ 修复后 10/10 全程
  活着（`-after.txt`）；浏览器 spec 在修复前那一代（`eae57b43` worktree）上 **3 条全红**。

另：C5 卡里「`ui/delivery.js` 的 window 挂桥」与「ui 模块 import 环」两条，前者第 10 节已记账、
后者已有 `tests/js/ui-cycle.test.mjs` 守着，本轮未动。

## 14. PDF 资料库真重复复核与回收（2026-09-20，证据补入库）

用户要求「看看 PDF 资料库是不是真的重复，真的重复就删」。结论：应用标出的 **15 组「疑似重复」
全部是真重复**——全量 SHA256 复算逐字节相同、**0 组假阳性**；按应用自身的回收语义删掉每组冗余
的一份（**不真删**，移入 `sources/.trash-pdf/<日期>/`）→ 回收 **15 个文件 / 10.85 MiB**，
库内 PDF **97 → 82**，且**内容层面零重复**（82 个文件 = 82 种唯一内容）。结论同时印证
2026-09-13 那次实测：应用判据在这份真实库上零漏报、零误报。

- 证据：`.scratch/pdf-dup-verify/`（`report.md` 复核报告 + `probe-01-verify.py` / `.txt`
  全量哈希复核 + `probe-02-apply.py` 回收执行），回收实况 = `sources/.trash-pdf/2026-09-20/`
  15 个文件（该目录与 `sources/materials/` 都在 `.gitignore` 里，不入包也不入库）。
- 本条的**判据边界**：应用侧仍按「同名（大小写不敏感）+ 同大小 + >0 字节」判疑似重复
  （纯客户端、不读内容 hash）——本次复核证明它在这份库上够用，**不代表**换成"改名的重复"
  也抓得住（复核里另做了全库内容分组，那种情况本库为 0 组）。

## 15. C4 发布通道公共件收回 update.py（2026-09-20，工单 release-channel-dedupe/01 已落地）

同一份架构评审的 C4（第 11 节把它记作"仍挂账"）。三条更新通道（小发版 / 完整包 / 资料库）
的**载荷形状与中文文案各写各的**（差异是真的），但机制被抄了多份：`_asset_url` 两份逐字相同、
找"版本最大的 release"两份、版本比较降级兜底 **5 处**、HTTP 面两份，且**完整包模块直接 import
资料库模块的私有名**（跨功能私有依赖——两侧其实早就是同一个模块，只是没人把缝画出来）。
错误码 `network` / `no-release` / `bad-manifest` 也是两份——而它们是**线上契约**
（前端两个更新面板按这些字符串分支）。

**已落地**：机制（列表端点 / 取资产地址 / 找最新 release / 版本比较降级 / 四个错误码 /
`materials-` 前缀字面量）收进 `update.py`；`full_update` 不再 import `materials_update`；
`_fetch_releases` / `_fetch_text` 保留为**一行委托壳**（端点的缺省注入缝，既有端点用例 patch 它们）。
新结构钉 `tests/test_release_channel_home.py`（机制与字面量单源 + 错误码同一性 + 前端按码分支的
字面量对账 + 合成红证），真红证 `.scratch/release-channel-dedupe/probe-01-pin-red-proof.py`
（HEAD 版喂进同一套判据 → 6 条违规 / 当前树 0 条）。三条通道载荷形状实测不变（11 / 8 / 7 键）。
评审抓到一条真回归并已修：降级兜底**不能 normalize**（会把非法版本号下的判定方向翻掉，
实证 `("1.0-Release","1.0-beta")`），已补回归用例。

**仍然挂账的（评审候选里最后一条）**：

- ~~**C6 进程级状态进 `AppContext`**~~ ✅ **已落地**（工单 `webapp-state-into-ctx/01–04`，
  2026-09-22，见第 17 节）：`_running_task_execs` / `_MATERIALS_LAST_CHECK` / `_materials_task`
  搬进 `AppContext`、模块级 `global` 清零、测试改在**自己构造的 ctx** 上注入与断言，
  并新增结构钉 + 真红证。**只换归属、语义未变**。
- **C7 私有符号公开化**（评审里的"73 个私有符号被测试翻墙"，`llm` 19 / `generator` 15）：
  当**验收尺**用，未立项——**它是尺子不是功能**（量"测试还翻不翻墙"的进展；`llm` 那簇是
  冻结区，价值有限）。

## 16. 启动器模式下 F5 会把应用自己关掉（2026-09-21～22，工单 launcher-exit-race/01–05 已落地）

第 13 节那条候选结清。**现场**：启动器模式（`FIRSTEP_LAUNCHER=1`，双击 `start-app.vbs` 的
正常路径）下按 F5 —— 旧页面的 `pagehide` 先发 `POST /api/tabs/bye` → 注册表空 → 服务端起
`_EXIT_GRACE = 1.5` 秒宽限 → 新页面的 `POST /api/tabs/register` 要等 `index.html`（4,668 行）
＋ 132 个模块装载完才发（它住在 `app.js` 里）→ 宽限内没到 → 后台线程 `os._exit(0)` →
**应用把自己的服务关了**，用户看到死页面。本机重测：**10 轮 reload 里第 4 轮命中**
（`.scratch/launcher-exit-race/probe-00-order-before.txt`，服务 exit 0、`page.reload` 抛
`ERR_CONNECTION_REFUSED`）。

**三层修法**（每层挡一个已实测 / 可确定性复现的失败模式）：

1. **登记提前到模块图之前**：`index.html` head 那段已有的内联脚本里 `fetch("/api/tabs/register")`
   —— 它在装载标签之前执行，模块图连**取**都还没开始。窗口从"HTML + 模块图装载"（实测
   0.42–1.5s⁺ 的尾长）降到毫秒级。**放 `boot.js` 没用**（ESM 静态 import 会先把整张图取完
   才求值）；另开一条 `<script src>` 会撞 fx-guard「脚本块恰好两处」。
2. **文档实例令牌 `epoch = performance.timeOrigin`**：`register` / `bye` 都带。旧实现只靠
   "宽限内复查空集"兜住"register 晚到"，兜不住**顺序反过来**（迟到的 `bye` 把刚登记的新页面
   注销掉 ⇒ 秒级竞态原地复现）。同一文档里 epoch 恒定、跨文档必不同 ⇒ 客户端不用存、
   不可能两侧漂移；告别带的 epoch 对不上就忽略。顺带修掉"复制标签页（sessionStorage 被
   复制 ⇒ 两个文档同一个 tab_id）里，关掉一个就把服务停了"。
3. **退出调度显式化**：`TabRegistry.arm_exit()` 布防（多标签同时关 / 重复与迟到的 bye
   **只布防一次**）／`register()` 撤防／`exit_if_due(exit_fn)` 到点**取走布防并在同一把锁里**
   执行退出。"决定退出"与"register 能被受理"因此有确定的先后——**不存在"register 回了 200
   但服务还是没了"**。

`_EXIT_GRACE = 1.5` **保持原值、没新增任何时间常量**：它现在覆盖的只是"旧告别 → 新页面
自报家门"的到达抖动。**关掉浏览器那条路径的延迟不变**（实测最后一个页面离开 → 服务自己停
**1.53–1.65 秒**；`probe-02-close-page.txt` 记 1638ms）。

**判据三处**（既有缝，不新造）：产品侧 pytest **4 → 15 条**（起点 = `eae57b43` 的 4 条
`test_tabs*`，本特性新增 11 条：乱序不注销 / epoch 一致照旧退 / 缺省向后兼容 / 同 id 两实例 /
类型校验 / 重复 bye 只调度一次 / 宽限内 register 撤销 / 撤防后再关重新布防 / 还有标签在开不布防 …）；
结构判据 `tests/js/boot-contract.mjs` **判据⑥** + 守卫 `tests/js/tab-register-guard.test.mjs`
（11 条，含"端点字样只在注释里""令牌只在别处的同名字段里"这些假绿反例）；真浏览器
`tests/browser/launcher-reload.spec.mjs`（**开启动器模式**的夹具上：连续 8 次 reload 服务
始终活着、把 `boot.js` 拖到宽限之外仍活着、最后一个页面离开服务自己停）。

**红证**：现场探针 `probe-00-order-before/after.txt`（第 4 轮命中 → 10/10 全程活着）；
结构判据 `probe-01-red-proof.mjs`（base 显式钉 `eae57b43` + base 自校验）；
浏览器 spec 放进 `eae57b43` 的 worktree 跑 → **3 条全红**（`probe-04-browser-red-proof.txt`），
其中 B 单独跑的红证把服务端日志的"bye → 没有 register → exit 0"钉在
`probe-04-b-only-server.log` 里。

**同轮记下的两条相邻洞（本轮不修，另立）**：① `bfcache`——`pagehide(event.persisted === true)`
（进 bfcache）时也发 bye，而 `pageshow` 不重新登记 ⇒ "离开又 1.5 秒内后退回来"会看到死页面
（修法：`pageshow` 补一次登记）；② 浏览器门禁**模拟不了真关窗口**：`page.close()` 走 CDP 关
目标、`pagehide`/信标都不跑（实测 `probe-02-close-page.txt`），故用例 C 用"真导航离开"验
同一条产品不变量。

## 17. C6 三处进程级状态进 AppContext（2026-09-22，工单 webapp-state-into-ctx/01–04 已落地）

第 11 节与第 15 节末「仍挂账」的 C6 结清。**问题**：`webapp` 把三样会话态挂在模块级
（任务执行注册表 / 资料库 check 缓存 / 进行中的资料库下载任务）→ 同一个进程里两个 app 实例
**共用**同一份状态（用例里「每个用例建一个 AppContext」的隔离只在纸面上成立），测试只能跨缝
import 私有名 + 一个 autouse 夹具事后清扫，`global` 语句 3 处。

**做法（只换归属、不换判据）**：三样搬进 `AppContext`（`running_task_execs` /
`materials_last_check` / `materials_task`——三个**公开**字段；锁私有 `_materials_task_lock`，
形状照既有的 `pending_generations` / `_generation_lock`：缝外的状态公开、缝内的互斥件私有），
端点与 helper 全经 `context.*`；随搬家补
`_materials_task_lock`（「查在跑 → 建 / 取消任务」两段 check-then-act 原子化，**语句次序逐字
留在原位**——判定次序也是判据）；`create_app()` 与 uvicorn 入口 `contest_generator.webapp:app`
**照旧**（评审提过的「import 模块不再顺带建 app」不在本条范围）。

**判据三处**：① 既有端点用例断言零改动（只改「取状态的姿势」：`tests/test_task_progress.py`
的夹具拆 `tasks_context` + `tasks_client`、`tests/test_materials_task.py` 的 `_client()` 返回
`(client, ctx)` 且 autouse 清扫夹具删除）；② 两条新行为判据「两个 app 实例互不可见」；
③ 结构钉 `tests/test_webapp_state_home.py`（判据纯函数 + 每条腿各有合成红证）。

**红证与读数**：`.scratch/webapp-state-into-ctx/`（spec、4 张工单、`probe-00-sharing.py` 的
前后对读 `verify-00-sharing-{before,after}.txt`；真红证 `probe-01-pin-red-proof.py`（base
**显式钉** `5c9fc8b0`，不写 HEAD）→ `red-proof.txt`：base **6 条 / 4 类**、当前树 0 条；
判据强度 `probe-02-guard-strength.py` → `guard-strength.txt`：**13/13** 条腿 stub 后变红）。
全量 `python -m pytest -n auto -q` **5070 passed + 1 skipped**。

**顺带记账**：本轮量到的两条**工具事实**（PowerShell `>` 写 UTF-16LE；`git show <rev>:<path>`
要 POSIX 正斜杠）记在 `docs/agents/local-environment.md` 的本轮会话段里——那条属于"这台机器 +
此刻"，不在这里重抄一份。

**剩余**：C7 只是验收尺（见第 15 节），未立项。**（2026-09-22 补记：C6 的另一条尾巴——
完整包链路的模块级会话态——见 §18，已结清。）**

## 18. 完整包链路的会话态进 AppContext（C6 的尾巴结清；2026-09-22，工单 full-update-state-into-ctx/01–04 已落地）

C6（§17）只收了 `webapp` 那三样，spec 的「不做」段与第 17 节当时都记着**完整包那一路的模块级
会话态另议**——就是这一节。

**问题**：`full_task.py` 把「最近一次 check 结果」（= apply 的分卷白名单来源）与「进行中的下载
任务」挂在模块级，外面包着四个 accessor（`get_full_task` / `set_full_task` / `last_check` /
`set_last_check`）。三层同款症状：同一个进程里两个 app 实例**共用**一份 check 缓存与同一个任务槽
（用例里「每个用例建一个 AppContext」的隔离只在纸面上成立）；测试只能跨缝改 `ft._FULL_TASK` /
`ft._LAST_CHECK` + 两份 autouse 清扫夹具；`full_task.py` 那一处 `global` 是**全 `src/` 仅剩的
最后一处**。另有一条**用户可见的真竞态**：apply 的「查在跑 → 建任务 → 占槽」是 check-then-act，
中间夹着要读磁盘断点快照的任务构造，两个并发 apply 能同时过关——第二个静默顶掉第一个的槽位
（那个任务还在跑却查不到 / 取消不了），两个线程还往同一个 `updates/full/` 与同一份快照里写；
前端 `startDownload` 与重试按钮都没有防重（两个标签页即可触发）。

**做法（只换归属 + 补一把锁，判据与文案一字不改）**：两样状态搬进 `AppContext`
（`full_last_check` / `full_task`，形状照 `materials_last_check` / `materials_task`：缝外的状态
公开、缝内的互斥件私有），四个 accessor **整条退场**（不留兼容别名），四个端点与
`_full_apply_complete` 全经 `context.*`；check 结果仍是**先 `clear()` 再 `update()`** 的就地写
（与资料库那半的裸 `update` 不是一回事，统一即改语义）；后台线程仍在**任务完成那一刻**读 check。
随搬家补 `_full_task_lock`：apply 的「查在跑 → 建任务 → 占槽 → **起线程**」与 cancel 的
「查在跑 → 取消 + 快照」两段原子化（起线程那条**比资料库那半宽一句**：占槽后、`run()` 置
downloading 前任务仍是 IDLE，那一跳会被第二个请求读到；`Thread.start()` 本身等到新线程跑起来才
返回，缝从「整段构造（读快照）」缩到「线程调度一跳」——**是收紧不是硬保证**，spec 已按修订追认；
资料库那半留着同一条缝，本轮不动）。`create_app()` 与 uvicorn 入口照旧。

**判据三处**：① 既有端点用例断言零改动（只改「取状态的姿势」：`_client()` 返回 `(client, ctx)`、
`_seed_check()` 写自建 ctx、两份 autouse 清扫夹具删除）；② 三条新行为判据——「两个 app 实例互不
可见」两条（分卷白名单：B 走兜底自查 400；任务槽：B 不被拒 200 且不动 A 的槽位）＋「并发 apply
只放一个任务进闸」一条（同一个 app 的一个 client ＋ 两个线程，事件把第一个卡在临界区里再放第二个：
修前第二个 200 且建出两个任务 → 修后 400）；③ 结构钉扩面
（`tests/test_webapp_state_home.py` 规则参数化跑两条腿 + 新增 `src/` 全域「`global` 语句 = 0」腿）。

**红证与读数**：`.scratch/full-update-state-into-ctx/`（spec、4 张工单、前后对读
`probe-00-sharing.py` → `verify-00-sharing-{before,after}.txt`（模块级缝 → B 认白名单 200 /
B 跟着拒 400；ctx 缝 → B 400 / B 200）；真红证 `probe-01-pin-red-proof.py`（base **显式钉**
`c6040566`）→ `red-proof.txt`：base **7 条 / 4 类**、当前树 0 条，另给 `src/` 全域腿两份真读数
（base `full_task.py:73` → 当前无）；判据强度读数 `guard-strength.txt`：**17/17** 条腿 stub 后
变红 + 逐字节复原 —— ⚠ **那支探针本体住在 `.scratch/webapp-state-into-ctx/probe-02-guard-strength.py`**
（它是**整个守卫文件**的自检，两支工单目录共用；工单 03 已把这份「归属错位」如实记账）；
C6 红证探针复跑读数 `c6-pin-probe-recheck.txt`）。
全量 `python -m pytest -n auto -q` **5081 passed + 1 skipped**；前端门禁 **1702 passed / 0 fail**
（本轮前端零字节改动）。

**顺带记账**：本轮量到的**工具事实**（本机控制台 GBK 让探针报告里的 `✗`/`✅` 在 print 上抛
UnicodeEncodeError、连带丢掉证据文件；base 版源码清单要从 base 取而不是当前树）记在
`docs/agents/local-environment.md` 的本轮会话段里——那条属于"这台机器 + 此刻"，不在这里重抄。

**剩余**：架构评审的候选**到此全部结清**（C2 §11 / C5a §12 / C5 剩余 §13 / C4 §15 / C6 §17 +
本条）。C7「73 个私有符号被测试翻墙」仍只是**验收尺**、未立项（见第 15 节）。

## 19. 启动器模式：bfcache 后退回来看到死页面（2026-09-24 立单）

`launcher-exit-race` 账本「未顺手做」段记的**相邻洞①**。此前它只在 §16 与那张工单的账本里
**记了一句"另立"**，全库却没有对应工单——本轮盘点发现，补立：

- **工单**：`.scratch/bfcache-return-register/issues/01-pageshow-register.md`（`ready-for-agent`）+ 同目录 `spec.md`。
- **一句话根因**：`pagehide` 不判 `event.persisted` 照发告别 ⇒ **进 bfcache 也算"离开"**、服务 1.5 秒后自停；
  后退回来时文档从 bfcache 恢复**不执行任何脚本**、全仓又没有 `pageshow` 监听 ⇒ 没人补登记 ⇒ 死页面。
- **形态是两个、都要修**：宽限内回来（补登记能救）/ 晚于宽限回来（服务已退出，任何补登记都救不回来，
  只能给中文可见态）。
- **推荐修法**：保留告别 + `pageshow(persisted)` 用同一 `tab_id` + 同一 epoch 补登记（服务端零改动）；
  **不要**单独用"bfcache 就不发告别"——冻结文档不会再发 `pagehide`，服务会永不自停、留下常驻进程。
- **未复现如实记**：立单那轮只读代码取证（file:line 见工单 Comments），红证配方与「headless 走不走 bfcache 待实测」
  都写在工单里。

**✅ 同日落地（2026-09-24，工单 `01-pageshow-register` resolved）**：

- **红证先做**：真 bfcache 需要 **`ignoreDefaultArgs: ["--disable-back-forward-cache"]` + `channel: "chromium"`**
  ——playwright **默认**就传那条 flag（`playwright-core/lib/coreBundle.js:34858`），所以门禁里 `goBack`
  只会得到整页重载（**假绿**）。四组 launch 配置的读数在 `.scratch/bfcache-return-register/probe-00-bfcache-red.{txt,json}`
  （base 钉 `f3578691`）：只有摘 flag 且用完整 chromium / 有头窗口那两组真走 bfcache，并且**复现成立**
  （`persisted=true` → 后退后 0 次新 register → 宽限后 `exitCode=0`(~1.6s) → 页面请求 `FETCH_FAIL`）。
- **修法（服务端零改动，前端 3 个文件）**：`index.html` head 内联脚本补 `pageshow(persisted)` 补登记
  （payload 与初载逐字同源）+ 失败广播 `service-stopped`；新增 `ui/service-stopped.js` 给中文可见态与
  「每 2 秒探活 → 服务回来自动重载一次」；`boot.js` 具名 import + `initServiceStopped()`。
- **口径改一处**：原验收写"至多一次自动重试"→ 改成"补登记只发一次、不重试；恢复靠探活 + 自动重载一次"
  （理由：晚于宽限时服务已退出，重试必然失败；真正的恢复来源是用户重启启动器）。工单里有完整口径段。
- **判据三处**：`boot-contract.mjs` 新增**判据 ⑦**（`restoreRegisterProblems`）+ 守卫 12 条（23/23）；
  浏览器 `launcher-reload.spec.mjs` 新增用例 D / E。读数（整改后那一版）：前端门禁 **1780 passed**、
  浏览器门禁 **40 passed / 0 fail**、全量 pytest **5356 passed + 1 skipped / 166s**。
- **双轴评审（`code-review`，跑在未提交的工作树上）改了 9 条**（共 11 条：9 改 / 1 有意保留 / 1 非违规），
  其中三条值得记：① **失败要留可回读的落地态**——只广播一次性事件不够，"模块图装载途中被冻结再恢复"
  这条时序里 ui 层还没装载、事件会丢，所以内联脚本同时写 `documentElement.dataset.serviceStopped = "1"`、
  ui 模块装载时回读（判据 ⑦ 新增子条款 ⑤）；② 失败判据从 `!r.ok` **收窄到网络错或 5xx**（4xx 是我方
  载荷问题，不是服务停了）；③ `endpointCalls` 改为**委托** `stringArgCallSites`，把同型抽取器收敛回一份
  （评审点的"最该修一条"）。保留的一条 = 闸门里不放真 bfcache（理由见工单与 spec「落地回填」第 2 条）。
  整改后复跑：守卫 **23 passed**、前端门禁 **1780 passed / 0 fail**、浏览器门禁 **40 passed / 0 fail**
  （整支首跑撞过两次已记档偶发，单跑该 spec 5/5 三次）、全量 pytest **5356 passed + 1 skipped**）。
- **顺带一条工具事实**：改文本别用 PowerShell 文本往返（`Get-Content -Raw` → `Set-Content -Encoding utf8`）
  ——会把 UTF-8 中文按 GBK 解码再写回（乱码），**GBK 硬配对还会吞掉行尾换行符**（本轮把探针文件搞坏过一次，
  已用编辑工具复原）。见 `docs/agents/local-environment.md` 本轮会话段。

**同日顺带的两件收口（与本轮盘点做的）**：

- `full-download/07`（真机演练）**标签没跟 → 已翻 resolved**：它自述"唯一剩下的是真发一次 Release"，
  而该动作已由挂账单 `real-acceptance/01` 的 **G1 三段**在 2026-09-13 / 09-18 做掉（v1.1.0 / v1.1.1 真发布 +
  沙箱模拟用户机 + 三项极端场景），此后又连发 v1.2.0 / v1.2.1 / v1.2.2；7 个 checkbox 本轮按在盘证据逐条补勾。
- 仓库根 `%SystemDrive%` 残留目录（`gitignore` 里的变量没展开产物）已删——2026-09-09 盘点记为"0 文件、
  等你点头删"，本轮实测里已有 3 个 Windows 缓存文件，一并清掉。


## 20. CCS 工程名写死 `mspm0_project`，同 workspace 两份必冲突（2026-09-24 记，未开单）

**来源**：真机验收第十八轮（A5/A7）现场踩到。完整描述与账户见
`.scratch/real-acceptance/issues/01-real-machine-acceptance.md` 的「A 组附带」段（观察项 **O-2**）
与 `docs/agents/local-environment.md` §2.4。

**现象**：`library/masters/mspm0/.project` 里 `<name>mspm0_project</name>` 是**写死的**，生成侧没有
改名机制（CCS 侧也没有工程改名入口）→ **任何两份 mspm0 生成工程都叫同一个名字** → 导入同一个
CCS workspace 时第二份被拒（同一 workspace 内工程名必须唯一）。

**射程**：真实用户的常见动作就会踩——「同一道题再生成一次」或「两道题各生成一份 mspm0 工程」，
只要两份放进同一个 CCS workspace 就撞。本轮验收之所以没撞上，只是因为 A5/A7 被各自放进了独立
workspace（那是绕开 CCS 工程模型的副产品，不是有意设计）。

**候选修法（未拍板，故未开单）**：

① 生成时按**题号 / 目录名**改写 `.project` 的 `<name>`（如 `2026H_Auto_Car_MSPM0`）——最贴合用户
   预期，但要动 `ccs.py` 写侧，且须一并处理 `.cproject` 与 `targetConfigs/*.ccxml` 里的自引用
   （需一次真机实测确认不会碰坏 build config）；
② 只改生成工程的**目录名**、不动 `.project`——**不管用**，CCS 认的是 `.project` 里的名字；
③ 维持现状 + 在导入说明 / 生成工程 README 里写明「两份 mspm0 工程请用不同 workspace」——零风险，
   但把问题留给用户。

**为什么先记不开单**：这条正是 `architecture-deepening-v5/08` 在「明确不动的（边界，勿越）」段里
**已明确划走**的那一项——那段原文列的是「SYSCFG_DL_init 骨架注入 / **生成工程赛题级重命名** /
母版 .syscfg 地猛星化 → 均留后续工单」。也就是说它不是新发现，而是那条**已知延后项**终于以
「用户看得见的症状」露了头。要拍板，先得回答「改 `.project` 名会不会碰坏 CCS 的 build config 自引用」。

**✅ 2026-09-24 拍板走 ② 并当场落地**（不改生成器的工程元数据；① 留给以后带真机实测单独做）：

- `src/contest_generator/readme.py` 的 `QUICK_START_STEPS["mspm0"]`：原来那句「用 CCS 打开工程：
  `File → Open Project 选择工程目录`」**按字面做 `Build Project` 是灰的**（CCS Theia 只把工作区的
  **子目录**认成工程）——本轮 A5/A7 就卡在这里。已换成实测姿势（先把工程目录放进一个工作区文件夹、
  再 `File → Open Folder` 打开那个文件夹），并补一条 `⚠`：工程名固定 `mspm0_project`、**两份 mspm0
  工程别放进同一个工作区**。
- 同一句错话术在 `DIRECTORY_STRUCTURE["mspm0"]` 的 `.ccsproject` 行还有一份 → 一并改。
- 守卫改为**反证式**：`tests/test_readme.py::test_render_readme_quick_start_mspm0` 断言渲染结果含
  「工作区文件夹」与 `File → Open Folder`，且**不含**旧话术 `File → Open Project`，并钉住
  `mspm0_project` 与「同一个工作区」。这条反证当场就抓到第二处残留（DIRECTORY_STRUCTURE）。
- 读数：`tests/test_readme.py` **42 passed**；全量 `python -m pytest -n auto -q` **5356 passed + 1 skipped**。
- **未动**：应用内「打开工程」按钮的 tooltip（`static/js/fx/delivery.js` 写「mspm0 打开文件夹
  （CCS 手动导入）」）——属前端面，留到需要时再改。

**仍未做**：候选 ①（生成时按题号/目录名改写 `.project` 的 `<name>`）——要动 `ccs.py` 写侧并处理
`.cproject` / `targetConfigs/*.ccxml` 自引用，得配一次 CCS 真机实测才敢拍（它也是
`architecture-deepening-v5/08`「明确不动」段划走的「生成工程赛题级重命名」）。**本项至此不算待办。**

## 21. `debug_uart × stm32` 的读数行超出板上行缓冲（2026-09-25 记，未开单）

**来源**：工单 `hwcheck-specialize/04`（批次 B：bh1750/bmp180/ms5611）落地时，为核对本批六格的
读数行宽而做的一次自查——顺手把**整份配方文件**都量了一遍，撞出这一条。读数与算式见
`.scratch/hwcheck-specialize/probe-compile-matrix-04.txt` 同目录的工单落地记录。

**现象**：板上报告缓冲是 `hwcheck_line[128]`（`src/contest_generator/hwcheck.py` 渲染的
`static char hwcheck_line[128]`，超长**静默截断**——溢出保护是刻意的，宁可截一行也不踩内存）。
一条读数行 = `  <表达式> = <值> <单位>`。`debug_uart × stm32` 那条的表达式是
`gpio_get(DEBUG_UART_RX_GPIO, DEBUG_UART_RX_Pin)`，加上那段长说明，**约 247 字节** ⇒ 超出的
部分在板上被丢掉，而中文一字 3 字节，**截在字中间就是半个乱码**——学生看到的是"读数那行尾巴花了"，
不是一条能自查的报错。同一量法下 `xunji × mspm0` 是 117 字节（贴着上限但没超）。

**为什么记而不在本单修**：它是 v1 pilot 的配方内容，而 `hwcheck-specialize/04` 射程只有批次 B
六格；spec 明说已 resolved 的两块**只允许被动适配**，不借这批改它们的内容。工单 04 立的新守卫
`test_expansion_read_lines_fit_the_device_line_buffer` **只覆盖 `EXPANSION`**（扩张格），
刻意不吃 pilot——所以这条账不会被那条守卫悄悄判绿。

**出路**（要修时）：把 `debug_uart × stm32` 那条 `unit` 写短（细节挪进 `note`，note 是页面文本、
不进板上的行缓冲），再考虑把守卫的射程从 `EXPANSION` 扩到全量配方。代价：会动到 pilot 配方，
得单独一张工单 + 一次两平台编译矩阵复跑。

> ✅ **已收口（2026-09-26，工单 `hwcheck-hardening/04`）**：按上面那条出路做了，而且**不止 1 条**——
> 逐格重量（按 03 落地的"值优先"格式 + 12 位数值最坏算）实测 **5 条**超 128 字节：
> `debug_uart × stm32` 249B、`adc × mspm0` 162B、`beep × stm32` 156B、`adc × stm32` 149B、
> `adc × mspm0` 149B；长说明全部挪进该格平台说明的倒数第二条（末条留给「未上板」），行上留短量纲
> （110B / 87B / 74B / 93B / 82B）。新守卫 `test_every_real_read_line_fits_the_device_line_buffer`
> **吃全量配方**（地板 165 条），既有那条扩张格守卫保留不缩小；反证 `probe-04-red.py`（塞回长量纲 → 红）。
> 两平台真编译矩阵复跑 6 格全 PASS（`probe-04-compile-matrix.txt`）。

## 22. 复测字符池的容量天花板：把库里专精件勾满必撞（2026-09-25 记，部分已修，未开单）

**来源**：工单 `hwcheck-specialize/07`（批次 E：ads1115/pca9685/dht11/ds18b20）落地时的
每批纪律——"新件 + 既有件"的组合要穷举一遍（批次 D 踩过同类坑）。量具与读数 =
`.scratch/hwcheck-specialize/probe-console-combos.py` / `probe-console-combos.txt`。

**现象（实测，两个平台同款）**：命令字符池一共 **31 个**（字母数字扣掉保留字 `r/y/g/o/b/?`），
而库里专精件已经有 **23 个（stm32）/ 26 个（mspm0）**。把**全部专精件一次勾上**必然分不出字符，
构建期 400，点名的是当趟第一个排不上号的件（本批落地时是 `tcs34725`）——学生看到的是一句
"去掉几件 / 换字符"，没有别的出路。天花板附近的实况（同一支探针，固定种子）：
`|S| <= 6` **全子集穷举**（14.5 万 / 31.4 万组）已经能全绿、规模 7~14 的抽样也全绿，
但**全部勾满**这一档永远过不去（26 件 > 25 个可用字符）。

**批次 E 顺手修掉的那一半（已落地）**：本批落地时 `|S| <= 6` 曾出现 3 组真撞车
（如 `ads1115 + at24c02 + bmp180 + pca9685 + sgp30 + sht30`：`sht30` 的首选 `e` 被
`at24c02` 拿走、候选 `n` / `z` 又分别被 `pca9685` / `sgp30` 拿走）。根因不是哪一件写错，
而是**候选池整体太浅**——修法 = 给每条声明了 `console` 的配方补一个**共享后备池**
`n z i 0 1 2 3`（纯追加：已有候选一个不删、顺序不动），并立守卫
`tests/test_hwcheck_console.py::test_any_small_selection_of_real_recipes_builds_one_console_table`
（真库任意 `|S| <= 3` 全子集 + 固定种子抽样到 8 件，必须建得出表且页面 / 板上同字符）。

**仍未修的天花板**：`|S| >= 25` 那一档（把库里专精件全勾上）。出路有三条，都需要单独一张工单：
① 把命令从"单字符"扩到"短串"（板上 `debug_cmd` 的缓冲与命令台分派都要跟着改，属产品行为变更）；
② 让分配不只挑"没被占的"，而是在**全局**上做匹配（`|S| > 池子` 时仍然无解，只把边界往后推）；
③ 页面侧如实预警"勾太多了，这几件排不上号"（检测页现在只在 400 时才知道）。
**为什么现在不修**：spec 的射程是"首批 20 件专精化"，字符池容量是它之外的另一件事；
而三条出路里没有一条是"改几个字符"能收口的。

**工单 08（批次 F：hx711/joystick/servo/relay）落地后的复测**：专精件到 **26（stm32）/ 30
（mspm0）** 格，`|S| <= 6` 全子集穷举（39.8 万 / 76.8 万组）仍**零撞车**（共享池起作用了），
全部勾满那一档撞在第一件排不上号的身上（`servo`）。同批把本批四件的候选按工单逐件给的
助记字符放在共享池前面（两套顺序都实测过零撞车）。

> ✅ **天花板已收口（2026-09-26，工单 `hwcheck-hardening/05`）**：走的是"把池子补齐"这条最省的路——
> 命令空间 31 个字符里此前**只有 25 个**被任何配方声明过（`4 5 6 7 8 9` 无人用），
> 于是"全勾满"必然撞（stm32 第 23 件 / mspm0 第 26 件）。给 57 条 `console.candidates` **纯追加**
> 这 6 个池位（已有候选一个不删、顺序不动）之后：**stm32 27 件 / mspm0 30 件一次全勾也建得出表**
> （新守卫 `test_the_whole_specialized_set_of_one_platform_builds_one_console_table`）。
> 另外两件：① 报错那句「可用字符一共 31 个」此前**比实际能分配的多 6 个**——现在声明面并集 = 池子本身，
> 并立了守卫盯着这层对齐；② 页面加了**事前**余量提示（`console_capacity_note`，余量 ≤ 3 才吭声）。
> **上面那两个数字（"26 件 > 25 个可用字符"与"池子 31 个"）的自相矛盾就此消除**：现在两个数都是 31。
> 反证 `probe-05-red.py`（撤掉追加 → 红）；前置测量 `probe-05-capacity.py` 留下"改之前红 / 改之后绿"的对照读数。

## 23. 库里三处模块头注释的引脚与 syscfg 不一致（2026-09-25 记；✅ 2026-09-27 复核：三条盘上已对齐，见节末）

**来源**：工单 `hwcheck-specialize/08` 落地时按交接区口径③「recon 是二手来源，写进学生可见
文案前回驱动源码核一遍」逐件核对引脚，撞出来的**文档性缺陷**（代码行为不受影响）。

**实况（三处，都是"模块头注释写的是历史默认"）**：

| 模块 | 头注释写的 | 事实（syscfg / manifest） |
|---|---|---|
| `hx711` | `hx711.h:14-16`：SCK 默认 **PB24** / DT 默认 **PB8** | `mspm0.syscfg:334,338` = **PA28 / PA31**（manifest notes 同） |
| `joystick` | `joystick.h:13-15` / `joystick.c:10-12`：ADC12_0 是「四通道 sequence / endAdd=3」 | `mspm0.syscfg:1268` 一带 = **8 槽 / startAdd=0 / endAdd=7**（另 `CONTEXT.md` 写"六通道"——三处口径各不相同） |
| `servo` | manifest 描述写 `servo_init(servo_id)` **单参** | `servo.h:37` = **双参** `servo_init(servo_id, channel)` |

**影响面**：配方 note 已按事实写（并如实提示"头注释是过期读数"），所以**学生看到的文案是对的**；
真正会咬人的是下一个照着头注释写代码 / 写配方的人。

**出路**：三处都是模块源码里的一行注释（或 manifest 一句描述），改起来很小；但按 `module-hwcheck`
spec 的口径，**修库内驱动（含其注释）属另一张单**，且改完要跟一次两平台编译矩阵。
建议与 `.scratch/driver-defect-fixes/` 那三张单一起处理（它们本来就是"驱动侧修正"的家）。

> ✅ **已收口（2026-09-27，台账复核轮实测复核）**：三条**盘上全部已对齐**——看来随
> `.scratch/driver-defect-fixes/` 那三张单（01 joystick / 02 servo / 03 hx711，均 `resolved`）
> 一起修掉了，只是本节的"未开单"标记没人回改。本轮逐条核对（读的是库文件本身，不是二手记录）：
>
> | 模块 | 本节要求的"事实" | 盘上现状（实读） | 结论 |
> |---|---|---|---|
> | `hx711` | SCK/DT 默认 PA28 / PA31 | `code/hx711.h:14-16` 写「默认 PA28」+「PA31」 | ✅ 对齐 |
> | `joystick` | ADC12_0 = 8 槽 / startAdd=0 / endAdd=7 | `code/joystick.h:13-14`、`code/joystick.c:11/20-21/35/80` 均写八槽 `endAdd=7`；`CONTEXT.md` 的「六通道」已不存在（grep 零命中） | ✅ 对齐（三处口径已统一） |
> | `servo` | manifest 描述与 `servo_init` 签名一致（双参） | `manifest.json:3` 写 `servo_init(servo_id, channel)`，与 `code/servo.h:37` 双参一致 | ✅ 对齐 |
>
> **本项至此不算待办**。只留一条经验：**"记而不修"的条目修完后没人回改本节标记**——
> 下轮复核按这个模式（直接读盘核对，不信本文件的旧标记）即可。

## 24. hwcheck-hygiene 批收口（2026-09-27，工单 01–14 全部 resolved）

**这一批是什么**：`docs/improvement-review-hwcheck.md` 的 **P2 七项 + 前端守卫补洞 + 两个大文件
按职责拆分**（spec / 工单 / 反证读数都在 `.scratch/hwcheck-hygiene/`）。做完即进 **v1.3.1**。

**五件值得下一轮记住的事**：

| 事 | 为什么重要 |
|---|---|
| **`activate` 漏改那两个调用位**（11 号单） | 前端门禁 1834 条 + 结构守卫**全绿**，只有"点器件卡片"那 9 条真浏览器用例红（各 30s 超时）。教训：**门禁全绿只证明没搬坏，证明不了搬全**；随单新增判据 ⑥「调用位的自由标识符必须在场」——守卫 ⑧ 只看 window 桥上的名字，管不到"谁都没有的名字" |
| **搬迁完整性自检要能活过后续工单**（14 号单） | 09/10 的 ②「与搬前快照逐字相同」会在任何后续合法修改上误红 → 加 `LATER_EDITS` 逐条记账豁免表 + 「没登记的改动照旧报」的正向对照 + 「表里每条都能在快照与六件/四件里找到」的防腐烂体检 |
| **判据要对着"当年那个 bug 的机制"注入**（12 号单） | 第一版反证把"blur 里的就地同步"换成整块重绘**不会红**（blur 前状态已同步，重绘能原样画回来）；真咬人的是**输入回调**那一路。反证段落选错，判据强度就是假的 |
| **库数据里的 markdown 粗体标记**（14 号单） | 评审的 Y6 只看到 JS 产品串（实测 5 处），**库数据那一层没人看**：配方 `note.lines` 2434 处、74 个 manifest 的 `platforms.*.notes` 1844 处，学生看到的是 `**本件必须接个已知电压才有意义**`。处置 = 渲染层 `escRich`/`escPlain`（先 esc 再转），**不动库数据** |
| **浏览器判据的判据面要说清边界**（12 号单） | 「页面上零字面星号」第一版判整栏，当场红在库数据上（真缺陷但不属那一单）→ 收窄到产品模板容器并在用例注释里写明为什么；14 号单再把库数据那一半补上。**判据面收窄必须留话，否则下一个人以为"整栏都判过了"** |

**✅ 已收口（2026-09-27，`record-write-hardening` 批）**：上面那三处「固定临时名 + 无锁记录写」
（想法对话 / 草稿 / 参数表）连同评审当时补出的第四处（母版元数据 `master_store._write_meta`）
已经全部改掉——统一走 `src/contest_generator/atomic_io.py`（唯一临时名 + `finally` 清残渣 +
按记录路径的进程内锁）；工单 `01`–`06` 在 `.scratch/record-write-hardening/`（07 号单把
`hwcheck_triage` 的私有副本也迁到同一原语）。结构守卫
`tests/test_atomic_io.py::test_only_one_atomic_write_implementation_in_src` 盯着
"新写的记录文件又手搓一个固定临时名"。

**这一批明确没修的**（如实列出，别当成已修）——**逐条现状已由 `backlog-closeout` 批复核（2026-09-27）**：

- ~~`materials_apply._extract_zip` 的固定 `.update-tmp`~~ → **✅ 已修**（工单 `backlog-closeout/03`：
  解包改走 `atomic_io.atomic_write_via`，唯一临时名 + 清残渣；顺带把同一条链上的
  `.materials-manifest.json` 写回也改原子写）。
- ~~`entry_store.write_json` 的裸 `write_text`（靠目录级事务兜底，不是这一族）~~ →
  **⚠ 那句只对"新建"成立**（工单 `backlog-closeout/04` 逐调用点核实）：新建那半边确实在事务里，
  **更新那半边不在**——`library.py:712`（`_write_manifest` ← 四个更新函数）、
  `reference_library.py:1085`（`update_reference`）、`topic_library.py:502`（`update_topic`）
  都是**活条目目录上的裸写**，强杀会留半截 JSON。**已开单**
  `.scratch/backlog-closeout/issues/05-library-meta-atomic.md`（`ready-for-agent`）。
- **跨进程并发**（本应用是单进程 `uvicorn.run`，锁是进程内的；多开两个实例写同一工程不在射程）
  —— 维持不动。
- **强杀残留清扫**（只清本进程本次写失败留下的临时文件）—— 维持不动。
- 母版**目录换入**与 `delete_master` 删除动作之间那条窄缝（`record-write-hardening/05` 的账；
  要闭得把锁提到目录换入之前、并把 `delete_entry` 也包进来）—— 维持不动（已承认残留）。
- **新发现（同一族，本批不改）**：`tools/update-app.py:208-220` 有逐字同形的固定 `.update-tmp`
  + 无 `finally`——它是**独立脚本**（跑在应用被替换之前、不 import `contest_generator`），
  风险低一档但"中断留残渣"一样成立；结构守卫的扫描面是 `src/`，收它得先决定要不要扫 `tools/`。

**下次复核按"直接读盘核对"的模式，不信本节旧标记**（§23 那个坑：修完没人回改标记）。

**另一类"未做"**：`hwcheck-acceptance/05`（真机上板）与 `hwcheck-hardening/08`（OLED 分页 / 逐件汇总）
仍阻塞于真板子——本批一律标注"未上板"。

## 25. v1.3.1 发版收口（2026-09-27，**不带新代码**）

**这一版只带版本号与文档**：`hwcheck-hygiene` 那一批（`01`–`14`）的代码早在 main 上，这次是把它
送到用户手上。工单是 `.scratch/release-v1.3.1/`（`01` 版本同步与自检 / `02` 打包发布 / `03` 账本收口），
发布产物、闸门读数、服务端对账全在 `issues/02`；落差已在 `local-environment` §0 归零。

**四条下一轮直接照做的本机事实**（发版那一刻真撞到的）：

| 事 | 为什么重要 |
|---|---|
| **`http.https://github.com/.resolve` 是个不生效的键** | git 2.54.0.windows.1 上它**不被认**（git 仍按 hosts 解析 → 约 21 秒后超时）。v1.3.0 那次"钉了就通"很可能是巧合。有效键 = **`http.curloptResolve`** |
| **候选 IP 按内容验，不按 HTTP 码** | 本机中间人对任意域名都可能答 200；判据 = 拿回来的真是 `001e# service=git-upload-pack…` + 真 ref。且**同一个 IP 的成功率会变** |
| **推送被掐不是"重试即好"** | 第一次 `Recv failure: Connection was reset`（exit 128，一个字节没上去，钩子都没跑）→ 换验过的 IP **并加 `-c http.postBuffer=524288000`**（默认 1 MiB 之上 git 走 chunked 编码，中间人更容易掐）之后一次过 |
| **新写的 `.ps1` 必须当场补 BOM** | `.scratch/release-v1.3.1/finish-publish.ps1` 由编辑工具写出来是**无 BOM** 的，pre-push 的 `tests/test_ps1_encoding.py` 当场红两条、**推送被拒一次**（白等 ≈5 分钟重跑整套闸门） |

**记而不修（本轮顺手量到，未开单）**：设置页「软件更新」那行仍写着
**「不用重下 6.2 GB 完整包」**（`src/contest_generator/static/index.html:4785`）——那个 6.2 GB 形态是
**已下线的 7z 渠道**，现在的完整包是 755–792 MB（v1.3.1 实测 `791,672,980` B）。
`tools/check-download-docs.py` 只扫 README 与 Release 说明（还在提 7z / 6 GB 才红），
**扫不到产品界面里的字**，所以它一直没报。修它要动 `index.html`（浏览器门禁的落点），
得连带跑那 60 条真浏览器用例——留一件小事给下一批。

> **✅ 已收口（2026-09-27，工单 `backlog-closeout/01`）**：三处体量按实测改（`:4785` 6.2 GB →
> 「约 800 MB」、`:4794` 「5 GB+ / 几 GB 级更新」→「约 0.7 GB / 5000+ 个文件」、`:4803` 「约 1 GB」
> →「约 800 MB」），确认弹窗那句「6 GB 资料库」（`static/js/ui/update.js:47`）也去掉数字；
> **守卫从"只扫 README/Release 说明"扩到产品界面文本面**（`static/index.html` + `static/js/**/*.js`，
> 判据：与「完整包/资料库」同行的 GB ≥ 2 即红），并顺手修掉守卫自身一个假阴性
> （否定式回看跨分句——`…不用手动下分卷、需要装 7-Zip` 会被放行）。
> 读数：前端门禁 1830 passed、浏览器门禁 60 passed、全量 pytest 5641 passed。
> **顺带更正两处旧账**：①`index.html:4794` 的「5 GB+」**本来就错**（装完的资料库实测 ≈0.67 GiB；
> 5 GB 那句在 README 里说的是"故意不进包的第三方装机件"）；②README 三处「约 770 MB」→「约 800 MB」
> （两条渠道口径对齐）。

**仍未做**：`hwcheck-acceptance/05`（真机上板）保持 `ready-for-human`——**本版没有任何板上行为
被验证**，`hwcheck-hardening/08` 同样阻塞于真板子。

## 26. backlog 剩余项收口（2026-09-27，工单 `backlog-closeout/01–05`）

**来源**：用户「把 backlog 剩余没做的做了」。全 25 节逐节读完，**真还开着的只有三条**
（其余要么已 resolved、要么是人为阻塞、要么是 spec 明确划走的边界），加一条"只核实不改"。
批 spec 与四张单在 `.scratch/backlog-closeout/`。

| 单 | 做了什么 | 用户可见吗 | 读数 |
|---|---|---|---|
| `01` 界面体量说实话 | 更新面板三处体量按实测改；守卫扩到**产品界面文本面**；修掉守卫自身一个假阴性 | ✅ 用户可见（面板数字变了） | 前端 1830 / 浏览器 60 / 全量 5641 passed |
| `02` MQ 词表口径统一 | 九条 MQ 方案 note 同一套口径（补「正向映射」+ 预热口径）；**把手册里没有的「3-5 分钟」退回有据措辞**；两条不变量守卫 | ❌（选购方案说明的措辞） | 定向 93 / 全量 5643 passed |
| `03` 解包走共享原语 | `atomic_io.atomic_write_via` 收成唯一实现；`materials_apply` 解包改走它（流式不变）+ **清单写回也原子化**；守卫例外清单删一条 | ❌（失败时的残渣/半截清单） | 定向 84 / 全量 5650 passed；mypy Success |
| `04` `entry_store` 核实 | 逐调用点核实"靠目录级事务兜底"这句话——**只对"新建"成立**；新开 `05` | ❌ | `src/` 零改动 |
| `05` 更新路径元数据原子写 | `entry_store.write_json_atomic`（唯一临时名 + 换入 + 清残渣）收口三处更新入口（`_write_manifest` / `update_reference` / `update_topic`）；异常期恢复逻辑原样；判据六条（三库 × 写失败零残渣/强杀仍可读） | ❌（强杀/写失败时的半截 JSON） | 定向 473 / 全量 5656 passed；mypy 本单文件零错；探针五段 PASS |

**本批产生的两条账（都写清了为什么不是待办或要另开单）：**

1. **`backlog-closeout/05`**：已 resolved（见上表）。它治的是三个库的**更新**路径
   （`library._write_manifest` / `reference_library.update_reference` / `topic_library.update_topic`）
   把元数据**裸写**进活条目目录——那是 `record-write-hardening` 那族里**唯一被"靠事务兜底"一句
   放过**的地方。**残留一条**（见下「顺带量到、不动」第 1 条）：这三处的读-改-写仍不持锁。
2. **库层预热口径没动**（`library/modules/mq*/**`）：mq3/4/6/7/8/9 的 manifest/code 注释仍写
   「预热 3-5 分钟」（同样无出处）、mq2/mq135/mq5 写「几分钟级」——**词表与库层两套口径**。
   改库内容要跟一次两平台编译矩阵（§21/§23 的口径），属另一张单。

**另外三条"顺带量到、不动"的事实**（免得下轮当新发现）：
- **三库更新路径的"读-改-写"仍不持锁**（`05` 只做了"落盘这一步是原子的"）：两个写者同时改
  **同一条目**时是"后写的赢"，还可能撞上 Windows 对同一目标并发 `os.replace` 的 `WinError 5`。
  要做对得给 6 个 `update_*`（`library` 四个 + `update_reference` + `update_topic`）在**外层**持
  `path_lock(entry_dir / <元数据名>)`；**不能**塞进 `entry_store.write_json_atomic`（`path_lock`
  不可重入 → 将来外层持同一把锁时自死锁，那条边界写在该函数 docstring 里）。本单**不开单**：
  失败面是"后写的赢 / 一次报错"，不是"条目变坏"（半截 JSON 已经绝了），而单用户本地工具里
  两个写者改同一条目要人为并发。
- `tools/update-app.py:208-220` 有逐字同形的固定 `.update-tmp` + 无 `finally`（独立脚本，
  不 import `contest_generator`；结构守卫只扫 `src/`）；
  > ✅ **2026-09-29 已修**（工单 `backlog-agent-sweep/02`，见 §28）：唯一临时名（`pid` + 进程内计数）
  > + `finally` 清残渣（清理失败不掩盖原异常），三条新判据 + 反证（旧形态两条按预期红）。
- 浏览器门禁 `launcher-reload` 在**本机负载下**仍会偶发红（本批实测一次 54/6，空闲重跑 60/60；
  已补进 `docs/agents/local-environment.md`）。

## 27. v1.4.0 发版收口（2026-09-29，**不带新代码** ＋ 发布后一条 CI 修复）

**这一版把四批送到用户手上**（记录写加固 `01`–`07` / backlog 收尾 `01`–`05` / ui-density 检测页轮
`01`–`05` / ui-density-sitewide 全站轮 `01`–`12`）。工单在 **`.scratch/release-v1.4.0/`**
（`01` 版本同步与自检 / `02` 门禁与全站读数 / `03` 沙箱真机验收 / `04` 打包发布 / `05` 发布后 CI 红），
spec 与全套读数同目录；落差已在 `local-environment` **§0** 归零，发布表与下一版基线在 **§3**。

**四条下一轮直接照做的事实**：

| 事 | 为什么重要 |
|---|---|
| **钉 IP 的键仍是 `http.curloptResolve`；"验过的 IP"只保证那一刻** | 推送前 6 个候选里 5 个按内容验通过（`4.208.26.197` 54 秒后 reset）；推送用 `140.82.114.3` **一次过**，但**推送后复验它却 reset 了**，换 `20.27.177.113` 立刻通 |
| **红要按"CI 还是本机"分开读** | 发布提交的浏览器门禁在 CI 上 **2/2 稳定红**、在本机 **2/2 稳定绿**（同一份代码）：**"本机全绿"不足以否证 CI 红**，判据只能是 CI 复跑 |
| **文件级 `unhandledRejection`（用例自己全绿）= 夹具没结算的异步** | 本轮是 `page.route` 处理器睡 1.5 秒后 `continue()`，而那一发已被别的通路结算 ⇒ 迟到的那次抛错落在**文件级**上下文。出路照 `launcher-reload` 的先例写 `.catch(() => {})`，**别去查产品** |
| **`readings.py --out-dir` 只认仓库内路径** | 指到 `%TEMP%` 时它在"写完文件之后"的打印那步抛 `ValueError`（文件是好的、退出码被带成 1）——要么指仓库内，要么忽略尾部那条报错 |

**沙箱「模拟用户机」的验收口径**（本轮新立的第 4 关，**顺序在打包之前**）：从当前工作树重造干净沙箱
→ 8020 起真进程 → 真 Chromium 走十二页签量**计算样式**（正文基准 14px、有文字的元素字号 ⊆ 六档）
＋ 设置页版本与体量文案 ＋ 版本记录页首块。**量具的口径要先自证**：第一版把 `checkbox` / `radio`
（自绘控件、没有文字、computed 是浏览器默认 `13.3333px`）算进"字号档位"，白红 5 条；
改成"**有文字的元素**"并把折叠区全展开，复跑 33/33。

**仍未做 / 有意留着**（下一轮想动手就从这里挑；**没有一条是本版引入的**）：

- **描边那条线没有机器守卫**（115 处是逐条申报的例外）——要加腿得先解决"哪些框算例外"的判据问题；
- **`--accent` 小字在浅色下 3.39:1**（低于 AA）与"去框留淡底"×1.06——调色板级决定，改它要过颜色守卫；
- ~~`probe-01` 仍是草稿探针（要么整支对齐 `scope_lib`、要么弃用）；生成页 `#rec-progress` 那张图还没拍；~~
  ✅ **两条都早做完了、只是没人回改标记**（2026-09-29 读盘核实并更正措辞，工单 `backlog-agent-sweep/03`，见 §28）：
  `probe-01-scope-draft.py:36` 已是 `from scope_lib import …`（09 单对齐）；`shots/10-{light-light,dark-dark}-rec-progress.png`
  在盘且在库（10 单拍的）；同段的"7 处内联字号留给 08 收尾单"也早已由 08 单收口。
- 三库更新路径的**读-改-写仍不持锁**、`tools/update-app.py` 的固定 `.update-tmp`、库层 MQ 预热口径
  （mq3/4/6/7/8/9 仍写"预热 3-5 分钟"）——三条都在 **§26** 记着，各自写明了为什么不开单；
- `hwcheck-acceptance/05`（真机上板）与 `hwcheck-hardening/08`（OLED 分页）仍 `ready-for-human`：
  **本版同样没有任何板上行为被验证**；`identity-fields/06`、`real-acceptance/01` 也是等人的单。

## 28. backlog 机器侧小账清扫（2026-09-29，工单 `backlog-agent-sweep/01–03`）

**来源**：用户「哪些机器自己做的先做了」。把 §27 那串"仍未做"按**要不要人 / 要不要板子**分了三类，
先把**既不用等人也不用等板子**的三件做掉（spec + 三张单在 `.scratch/backlog-agent-sweep/`）。

| 单 | 做了什么 | 判据 / 反证 | 读数 |
|---|---|---|---|
| `01` 并发用例排序 | `test_concurrent_record_writes_share_no_tmp_file`：第二个写者**整条走完**再放行第一个（两次真实 `os.replace` 重叠 = Windows 平台行为，会让它在机器忙时假红） | 判据三条**一条没动**；反证 = 注入固定临时名 → 该用例照样红（红在"源临时文件被吃掉"） | 该用例连跑 **20 轮全绿**；全量 **5659 passed + 11 skipped** |
| `02` 更新器解压临时名 | `tools/update-app.py::extract_zip`：`<目标>.update-tmp` → **`<目标>.<pid>-<计数>.update-tmp`** + `finally` 清残渣（清不掉不掩盖原异常）；**保持"不 import `contest_generator`"的独立脚本边界** | 新 3 条判据（正常零残渣 / 失败零残渣且不碰目标 / 同进程两次临时名不撞）；反证 = 旧形态 → **2 条按预期红** | `tests/test_update_app.py` **10 passed**；全量同上（+3 条用例） |
| `03` 过期账措辞 | 读盘核实后更正三处：08 账第 9 条（`probe-01` 已由 09 单对齐 `scope_lib`）、`ui-density-sitewide/README` 的巡检图索引段与「当前读数」段（`#rec-progress` 图已由 10 单拍、7 处内联字号已由 08 单收） | 纯文档；核实手段 = `git ls-files` / `git check-ignore -v` / 读源码第 36 行 | 产品面零改动 |

**本轮新立的两条经验**：

1. **反证探针要"红在机制上"，不是"红就行"**（`01` 的探针第一版把替换串带上了缩进 → 注入出来是
   `IndentationError`：红是红了，但红在语法上）。探针里那条"失败要指向被测机制"的判据当场把它拦下来——
   **判据强度探针自己也要有判据**。
2. **"记而不修"的另一个变体：修完了没人回改标记**（`03`）。本轮我自己就先按 §27 的旧账把
   `probe-01` 与那张进度图列进了待办，**读盘才发现两件都早做完了**——与 §23 的坑同一个形状。
   下轮复核照旧：**直接读盘，不信账上的旧标记**。

**仍开着的（本轮明确不做，都写明了去向）**：描边那条线的机器守卫（要先定"哪些框算例外"的判据）、
`--accent` 小字浅色 3.39:1 与"去框留淡底"×1.06（调色板级）、库层 MQ 预热口径（改库内容要跟两平台编译矩阵）、
三库更新路径读-改-写持锁（§26 已判不开单）、`launcher-reload` 负载下偶发（要专门一轮压测），
以及等人的 `hwcheck-acceptance/05` / `hwcheck-hardening/08` / `identity-fields/06` / `real-acceptance/01`。

## 29. 描边那条线的机器守卫（2026-09-29，工单 `border-guard/01–03`）

**来源**：§28 那串"仍开着的"里的第一条——**描边那条线没有机器守卫**
（`ui-density-sitewide` 08 账第 1 条：115 处整圈完整框只有逐条申报的散文清单 + 人眼看图）。
用户点的口径：**先把"哪些框算例外"变成可对账的数据（防腐烂），再给守卫加一条腿 + 合成红证**；
口径沿用 `ui-density-sitewide/scope_lib.py` 的 `full_borders`，**读数每轮重跑**。

| 单 | 做了什么 | 判据 / 反证 | 读数 |
|---|---|---|---|
| `01` 样式块面 | `BORDER_REGISTER` **115 条**（`[作用域, 剥注释的选择器, 类别]`）+ `BORDER_KINDS` **10 类** + 守卫**腿⑥**（盘上 ↔ 登记簿双向对账 / `placeholder` ⟺ 含 `transparent` / 类别表形状） | 合成红证 9 类注入（新框 / 改名 / 删规则 / 占位变真框 / 未知类别 / 掏空类别 / 重复登记 / 形状不对 / 同键两条）；探针 `probe-03` 双向差 **0/0** | 前端 **1841/0**、全量 **5663+11**、产品面 0 行 |
| `02` 渲染方面 | `JS_BORDER_REGISTER` **10 条**（`[文件, 行内锚点, 类别]`，**不取行号**）+ **腿⑦** + 跨语言镜像守卫 `test_border_register_mirror.py`（5 条） | 红证 6 类注入 + 单边/撤框边界正反证；探针 `probe-04` 双向差 **0/0/0** + **覆盖审计**（15 行 `border…:` 全归类） | 前端 **1842/0**、全量 **5664+11**、产品面 0 行 |
| `03` 收口 | 三套门禁（浏览器**单独跑**）+ 上一轮三支探针不退化 + 文档四处回改 + 双轴评审整改 | 浏览器 **61/0**；14 作用域 0/0、页面尺 0、`--fs-*` 428 不退化 | 见 `.scratch/border-guard/README.md` |

**本轮量清的两条口径（别混着读）**：

1. **115 处整圈完整框 = 94 条可见框 + 21 条非框**（12 透明占位 + 9 圆点 / 字形 / 滚动条）。
   「115」是**声明数**口径，与"渲染出来的框元素数"不是同一把尺。
   非框里 **10 / 21** 在悬停 / 选中态会拿到 `border-color`——**合法逃逸**（单声明不是完整框），不是漏网。
2. **样式块面有一条、渲染方面另有一条**：`static/js/**` 里还有 **10 处内联整圈框**
   （08 单给「内联字号」补第五条腿时，描边这一面是对称地空着的）。

**两条本机事实（写进 `local-environment`）**：

- **`.venv\Scripts\python.exe` 里没有 pytest**（那是应用运行时）——跑门禁要用系统 `python`（9.1.1）。
  拿 `.venv` 跑会得到"退出码 1 但没有失败用例"的假读数。
- **PowerShell 5.1 的 `Get-Content` 不带 `-Encoding UTF8` 会把 UTF-8 无 BOM 读成 GBK 并吞换行**
  （`ui/codeeditor.js` 读出 2711 行 vs 真实 3231 行）——行号全错；读源码一律 `-Encoding UTF8` 或走 Python。

**仍开着的（本轮明确不做，去向写清）**：`--accent` 小字浅色 3.39:1 与"去框留淡底"×1.06
（调色板级，改它要过颜色守卫）；`.pdf-*` / `.lib-*` 两处跨页前缀的谓词归属
（sitewide 08 账第 8 条判过"按第一命名页保留现状"，要动的唯一理由是"哪条腿看着它"）；
渲染方**跨行拼出来的**内联声明抓不到（与第五条腿的已知留白同类，`probe-04` 的覆盖审计盯着）。
本轮**没有**新增任何"等人 / 等板子"的单。

## 30. 浅色调色板 + 对比度守卫（2026-09-30，工单 `light-contrast/01–05`）

**来源**：§29 那串"仍开着的"里的头两条——**`--accent` 小字浅色低于 AA** 与**「去框留淡底」×1.06**。
用户拍板：两条一起做（同一类改动、同一套验证），accent 走"引入 `--accent-text`"，并**顺手立对比度守卫**。

| 单 | 做了什么 | 判据 / 反证 | 读数 |
|---|---|---|---|
| `01` 守卫与数据 | 腿⑧ **五面**（机械 376 对 / 族面 / 令牌面 28 个文字令牌 / 渐变端点 / 例外表）+ 三个例外认人键 + 跨语言镜像 22 条 | 红证 14 类 + 反证探针 8 处注入；双向差 0/0/0 | 例外表 **128** 条；前端 1844/0；pytest 5685+11；产品面 0 行 |
| `02` 六族落地 | 六族 `-text` 令牌 + **223 处 HTML + 14 处 JS 内联**迁移 + 实心块字色令牌化 + 渐变盲区修补 | 机械面同尺对照；非取色声明逐规则零差异 | 浅色 **99 → 1**、暗色 **16 → 0**；例外表 **128 → 9** |
| `03` 淡底与非文字 | 浅色 `--panel-2` ×1.065 → **×1.179**；焦点环提到 3:1（走 `--accent-text`） | 联动三数（`--muted` 4.87 / `--accent-text` 5.53 / 淡底 ×1.179） | 前端 1844/0、浏览器 61/0、pytest 5686+11、描边 115 不变 |
| `04` 渲染方腿⑨ | `JS_CONTRAST_REGISTER` 19 条内联取色入册（认人键 = 文件 + 行内锚点） | 五条红证；probe-02 逐处清单作覆盖审计 | 前端 1845/0；双向差 0 |
| `05` 收口 | 量具跨十四页重跑 + 三套门禁 + 浅暗各 28 张截图人眼复核 + 文档四处回改 | 见 `.scratch/light-contrast/README.md` | —— |

**本轮量清的三条口径（别混着读）**：

1. **底 = 元素自己那层背景合成到 `--panel` 上**——上一轮那三个"乐观数"（6.11 / 5.19 / 3.39）
   量的是祖先底；按真实合成底是 **4.50 / 4.38 / 2.95**。这条更正后，"浅色只有 accent 小字越线"
   这个结论就不成立了：**六族都越线**。
2. **"逐条登记"与"现算 + 只记债"不是同一把尺**：描边那条腿登记 115 条全量；
   对比度这条腿**只登记不达标与不适用**（达标的现算即可）。
3. **渐变是静态面的盲区**：`ruleBackground` 对渐变返回 null，所以"文字压在渐变上"必须
   **逐端点**另立一面（`CONTRAST_GRADIENT_ENDS`）——本轮正是靠它逮到"浅色 ok 渐变两端太接近、
   没有单色字能同时过"。

**一条方法论**：两轮双轴评审共 27 条发现，其中**三条改变了产品**（覆盖缺口 → 补令牌面；
渐变退步 → 修填充层；落值不可复现 → 对齐余量口径）。**评审不是形式**：这轮最值钱的三件事
都是评审提的，不是施工时想到的。

**仍开着的（本轮明确不做，去向写清）**：`--tok-*` 语法高亮族的配色（浅色 8/10 个令牌在代码底上
低于 4.5，**改它 = 改代码长什么样**，另立一轮）；控件普通描边 / 语义左条的非文字 3:1
（`--accent` 压加深后的淡底 2.70，装饰性强于信息性，记债）；`.pin-subtitle` 的 `var(--fg)`
未定义令牌（笔误，已登记 `skip`）；两个图例色点的令牌定义在页面作用域块里，静态解析面看不到
（要动得先扩令牌解析面）。**禁用态是全站对比度最低的一类**（人眼复核 + 像素采样实测：hwcheck
「带进生成页」禁用钮 **2.66**、master「AI 提炼报告」禁用钮 **2.06**）——根因是全局
`button:disabled { opacity: .45 }`（既有模式；把淡底加深后前者从 2.94 掉到 2.66），
**改它要一并定"禁用态该长什么样"**（opacity 还是灰底灰字），属设计决定、另开单。
另：浅色**视觉面**缺一张"有已完成步骤"的图（紫色族与实心绿在十二张图里零实例，
静态面已用渐变端点判据覆盖）。本轮**没有**新增"等人 / 等板子"的单。

## 31. 代码配色族修到 WCAG AA（2026-09-30，工单 `code-contrast/01–04`）

**来源**：§30 那句「**仍开着的**」的头一条——`--tok-*` 语法高亮族只量不修。
用户拍板：**七层全包**（把上一轮漏登记的两层补上）、修法走「**降一档 + 暗色换深青**」、
叠加态**只保单层**（记边界）、禁用态口径定为**灰底灰字**（有余力再做）、**本轮不发版**
（v1.4.1 另开一轮）。

| 单 | 做了什么 | 判据 / 反证 | 读数 |
|---|---|---|---|
| `01` 口径补齐 | 层 **5 → 7**（+当前搜索命中 +错误行）+ **叠放几何**（真像素实测：高亮**压在字上**）+ `--code-hl-rgb`（值取现值）+ 代码页 11 条规则改引用 | 族面格数冻结 168；红证 5 条新分支；`probe-01`（上一轮探针）漏改的二元组解包当场修 | **观感零变化 14/14 格逐字节相同**（`git stash` 前后各拍一套）；前端 1845/0、浏览器 61/0、pytest 5688+11 |
| `02` 落值 | 选区 `.32→.20`、当前命中 `.38→.24`；暗色 `--code-hl-rgb` `0,190,230`；浅色八个令牌压深、暗色两个微调 | 例外表 `--tok-*` 两行**摘掉**；最坏格冻结 `CONTRAST_TOK_WORST`（浅 4.66 / 暗 4.65） | 例外表 **9 → 7**；真像素（选区态）浅 4.80/4.68、暗 4.90/4.55（**改前 2.78/3.02/3.52/3.17**） |
| `03` 禁用态 | 全站 8 条规则的 `opacity`（`.45/.5/.55/.6/.65`）→ **灰底灰字**（`--panel-2` 底 + `--muted` 字 + `--border` 描边）；写法改成"形态规则自己带 `:not(:disabled)`、禁用态只剩一条通用规则"（双轴评审整改，消掉枚举） | 族面加「--muted × 禁用态底」4 格（格数 168 → **172**）；判据⑥（禁用态不许 `opacity`）+ 判据⑦（涂色形态必须表态）；内存红证 n1–n6 + **真文件反证 2/2**；新增 `probe-08`（真元素截图 + 读像素，含"**没量到**"逐条记账）+ `probe-07` 禁用桶不再被祖先渐变滤掉 | 真像素 **浅 2.65 / 2.06 → 5.25**、**暗 3.93 / 2.36 → 5.67**（8/8 格变好）；扫描禁用桶 5 处/主题、**0 处低于阈值**（改前那个桶是**空的**）；前端 1845/0、浏览器 61/0（222.9s）、pytest 5689+11 |
| `04` 收口 | 真像素比值入读数 + `probe-07` 回归 + 人眼截图（两主题 × 两种源 × 三态）+ 文档四处 | 见 `.scratch/code-contrast/README.md` | probe-07 不退化（浅 2 / 暗 2） |

**本轮量清的两条口径（都是"上一轮的算法偏乐观"）**：

1. **叠放几何**：代码页的高亮层**压在字上**（`.code-marks` z-index 0、`.code-ta::selection` z-index 1
   都在 `.code-hl` 文字之上）⇒ 半透明色把**字形本身**也染了，真比值比"文字压在合成底上"更低
   （浅 `--tok-com` @ 当前命中：旧算 **3.10** / 真渲染 **2.69**）。只有行元素自己那两层
   （`.active` / `.flash`）垫在字下。**默认取严格那侧**：带 tint 的配方没登记进层表就按 `over` 算
   ——乐观的默认正是本轮踩的坑（括号彩虹 8 层照 `behind` 算 7.70–10.03，实测是 6.57–7.37）。
2. **层会叠**（本轮的**口径边界**）：双击选词 = 词命中 + 选区，合成 alpha = `1-∏(1-α)`。
   落定档下叠词命中 浅 4.15 / 暗 4.02、叠当前命中 浅 3.42 / 暗 3.11。
   **不进判据**——要收它得让所有高亮淡到几乎看不见（选区 α ≈ .12 量级）。

**一条方法论（第二次验证）**：两轴评审 10 条发现里**一条是真 bug**（括号彩虹几何落成 `behind`，
登记格比实测乐观 ≈2.5 且不红）＋**一条是纪律违规**（上一轮探针的二元组解包没跟着口径改形，
实跑 ValueError）。两条都不是施工时想到的。

**仍开着的（本轮明确不做，去向写清）**：① **禁用态剩下两处"别的类名"的 opacity 形态**（03 单收尾时量出来的，
本单按票面判据（只认 `:disabled` / `.disabled`）够不着）：`.module-card.off`（"需切换平台"的模块卡，
现算 **浅 3.40 / 2.24**、暗 5.09 / 2.69——浅色那两格低于 AA）与 `.pin-menu-list li.cant`（选不了的引脚角色行）；
要收得先决定"不可选卡片/菜单行"要不要跟按钮同一口径（改名成 `.disabled` 才进判据⑥），**另开单**；
② **叠加态定价**；③ `--accent` 控件普通描边 / 语义左条的非文字 3:1（2.70，仍记债）；
④ `.pin-subtitle` 的 `var(--fg)` 未定义令牌（登记 `skip`）；⑤ 两个图例色点的令牌定义在页面作用域块
（要动得先扩令牌解析面）；⑥ **发版 v1.4.1**（版本号已定、未发；这一批要进发布说明的用户可见变化：
**代码页语法色与高亮强度** + **禁用态的样子**）。
本轮**没有**新增"等人 / 等板子"的单。
