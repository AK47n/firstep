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
UTF-8 stdout（原锚点版是崩在 GBK 编码上的）。第 7 节的两道候选已拍板（A 放行待立单 / B 维持现状），
见本节末「拍板结果」。

## 6.5 完整包 / 发版打包线（2026-09-13 开单，同日补登台账）

这两单是 09-13 发 v1.1.0/v1.1.1 时开的，**先前没登记进本台账**（第 6 节与
`.scratch/tracker-audit/2026-09-09-在途盘点.md` 都停在 09-12），导致每轮盘点会漏看——
本轮补登。真机挂账单里的同源进度见 `.scratch/real-acceptance/issues/01` 的 G 组。

| 工单 | 级别 | 现状 |
|---|---|---|
| `full-download/07` | 真机项 | **ready-for-human**：v1.1.0/v1.1.1 发版 + 沙箱「模拟用户机」演练已勾（G1 前两步）；剩 G1 后三步极端场景（弱网中途取消 / 断网重试 / 改坏一个卷造校验失败），代码侧已由自动化覆盖，真机只验过等价的「取消后重试跳过已完成卷」 |
| `full-download/08` | 🔴 真隐患 | **✅ 已落地（resolved，2026-09-13）**：两个打包器字节口径不一致（`git archive` 的 `core.autocrlf` 转换 vs 读工作树）——v1.1.0 实测 3474 个共有文件里 **926 个字节不同、内容差异 0**（v1.1.1 为 929 个，本轮用新判据在真实发版包上复核）。修法：把 `git archive` 钉 `-c core.autocrlf=false`（实测 `.gitattributes` 的 `-text` 压不住它），新增 `src/contest_generator/pack_update.py` 打包核心 + 14 例跨包守卫；真实仓库复跑 **共有文件 3480 个、字节差异 = 0**。附带修掉空 `removed.txt` 被 `gh` 拒收（`HTTP 400`）的老坑 |

## 7. 选中集引脚容量预警 —— 🔶 A 已拍板待立项 / B 维持现状（2026-09-18 拍板）

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

- **A 放行，待立单**：门禁命中时补可操作数字（落点 / 可用脚 / 至少去掉几个模块），
  **只升文案不增拦截**，前端零改动。立单命名用「引脚容量」。
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
  （见第 15 节）、**C7（73 个私有符号公开化）仍挂账、未立项**。

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

**仍然挂账的（评审候选里最后两条）**：

- **C6 进程级状态进 `AppContext`**：`_running_task_execs` / `_MATERIALS_LAST_CHECK` /
  `_materials_task` 仍在 `webapp` 模块级（23 处引用），测试靠跨缝 import 它们——未立项。
- **C7 私有符号公开化**（评审里的"73 个私有符号被测试翻墙"，`llm` 19 / `generator` 15）：
  当验收尺用，未立项（`llm` 那簇是冻结区，价值有限）。

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

