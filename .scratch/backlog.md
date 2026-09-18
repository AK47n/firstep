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

## 8. 沙箱真机演练第二梯队 B1–B5 开出来的三张单（2026-09-18）

演练本体（spec + 五张工单 + 脚本 + 原始证据）在 `.scratch/sandbox-drill/` 与
`.scratch/verify-gate-drills/`；下面是**演练暴露的真缺陷/待决策项**，都已开单，别漏看：

| 工单 | 级别 | 一句话 | 证据 |
|---|---|---|---|
| `update-restart-stale-service/01` | 🔴 用户可见 | **从 v1.1.1 点「一键更新」：文件全换成 1.2.1，但跑着的服务还是 1.1.1**（发起更新的那一代没传停服端口 → 旧进程没被停 → 启动器判 `already_running` 只开浏览器）。根因链完整、修复在 v1.2.0 起已有，**但那一批老用户会得到「说更新成功、其实是旧版」**；手动重开一次即可到新版（已实测） | `verify-gate-drills/verify-01-upgrade.{txt,json}` + `-aftercare.*` |
| `update-orphan-files/01` | 🟠 卫生 | 小发版删除清单只覆盖「上一版 → 本版」，**落后两版以上的用户升级后留下 1483 个孤儿文件**（全在 `library/` 备份目录与 `sources/` 下几个）；官方包比对 3057 一致 / 3 不同 / 0 缺。附带发现：`src/contest_generator.egg-info/*` 随包分发，且更新器的 `pip install -e .` 每次都会重写它 | `verify-01-upgrade-aftercare.txt` 的构成一节 |
| `update-content-mismatch-retry-cap/01` | 🟡 决策单 | 持久「内容与清单不符」→ **永远 downloading + 每轮整卷重下**（spec 第 122 行明文如此，**不是实现 bug**）；真机量出 150 秒 6 次重试、台账起始偏移全 0。建议加「连续 N 次转终态」或至少把重试量写进摘要 | `verify-02-degraded.{txt,json}` 的 `content-mismatch` 一节 |
| `update-verify-failure-leftovers/01` | 🟡 卫生（可自愈） | **不可重试**的校验失败（清单 size 与对端总长矛盾）终态 `failed` + 中文话术都对，但 `updates/full/` 里留下**整卷半成品**（实测 3,961,701 B）+ 边车，与 spec 第 147 行「校验失败一并删除」不符；线上完整包场景 = 失败后白占 ~765 MB（下次重试会因 416 自愈） | `verify-02-degraded.{txt,json}` 的 `verify-size` 一节 + 文末更正节 |

