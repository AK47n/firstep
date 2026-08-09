# CONTEXT.md — 电赛工程生成器

单上下文领域词表（架构评审 / 领域建模的共享语言）。实现决策见 `docs/adr/`。

## 领域词表

| 术语 | 含义 | 主要实现 |
|---|---|---|
| 赛题 | 粘贴或上传（PDF / .docx / .txt / .md）的竞赛题目原文 | extraction.py → str，贯穿所有 LLM prompt；生成入口装配唯一出处 = generator.resolve_topic_context（TopicContext） |
| 平台 | `stm32`（STM32F103C8T6 / Keil5）、`mspm0`（地猛星 MSPM0G3507 / CCS） | 词表在 platforms.py；识别知识（工程配置文件后缀表）= platforms.PLATFORM_CONFIG_FILE_SUFFIXES 单源；蒸馏侧平台行为经 distill_adapters 适配器（master 只消费）；生成侧行为在 patchers.py / webapp.py；工具链外部头豁免（stm32 = DFP 提供、mspm0 = SysConfig 生成）经 patchers.external_headers 分派，C 标准库头归门禁（generator._LIBC_HEADERS，平台无关） |
| 模块 | 可复用 .c/.h 单元 + 机器可读 manifest；库目录即数据库；与功能库相对——模块承载外设/赛题功能，功能库是母版自带底层库；模块推荐（AI 选模块）的模型类与收敛工作流归 selection.py——llm 层运行时依赖 selection 而非反向（report.py 先例） | manifest.py（模型）/ library.py（库操作）；模块推荐域在 selection.py；推荐域判决（build_module_selection：模型输出 → ModuleSelection 解释链——需求派生 / 词表约束 / DeepSeek 怪癖）在 selection.py，llm 只做机械提取 |
| manifest | 模块目录下 manifest.json：slug、简介、依赖、平台条目（文件 / 验证状态 / 硬件绑定 / 备注 / 硬件身份字段 kit + source_url） | manifest.py |
| 简介 | manifest.description，判据三要素：① 与代码一致（AI 校验）；② 硬件身份可确认——套件型号（kit）与购买链接（source_url），平台条目字段、新录入必填、URL 格式校验、由人补填；③ 专用性——逻辑绑定具体赛题的模块必须标注"XX 题专用"（如 lock_control / zone = 2026C 数字钥匙题专用，pid = 巡线题专用） | library.py / llm.py |
| 依赖 | manifest 声明的模块依赖，生成前递归展开（依赖先于使用者）；上层依赖下层；不得声明对功能库的依赖（母版必有，声明反而使解析器找不到而报错） | selection.py |
| 可选配套 | 模块的可裁剪组件：如 filter 之于 uwb_uart——代码层现状为必需依赖（uwb_uart.c 写死 include 与滤波调用），可选化（条件编译 + 生成器按选中定义宏）已立项未实现；普适 filter / 普适巡线逻辑为将来方向 | （未实现） |
| 母版 | 每平台一个的基础工程；现阶段 = 空的最小系统板工程（平台基础设施齐全 + 模板 main.c，能直接编译烧录；stm32 母版自带全套逐飞库 ml_* 功能库；**mspm0 母版 = TI 官方 empty 示例（CCS Theia 20.5 导出，TMS470_TICLANG 4.0）整理入库**：main.c 模板 = SYSCFG_DL_init() + while(1)（ADR 0002 形态），mspm0.syscfg 按 TI 官方板 LP_MSPM0G3507、由赛题工程按需自改，.cproject/.project 原样保留语义）；元数据在母版目录外的平级 json | master.py（蒸馏编排）/ master_store.py（母版库 CRUD 与元数据） |
| 功能库 | 母版自带的底层库（stm32 母版 = 逐飞 ml_*：I2C/UART/PWM/GPIO/OLED 等，headfile.h 聚合），先于一切模块存在、生成时随母版进工程；不属于模块库 | masters/stm32/ml_libs |
| 提炼 | 导入多旧工程 → 对比 → AI 判定 → 报告（保留 / 整合 / 剔除 + 残留清单）→ 确认 → 入库；判定范围 = 公共 + 冲突 + 独有全部逐个判定，唯一判据：读内容判断是否通用、是否基础建设必需，不看重复次数 / 出现范围；确认是一条事务（confirm_distillation） | master.py + llm.py |
| 上传暂存 | 「选择文件夹」上传（webkitdirectory 整夹上传）的落盘点：路径穿越拒绝（entry_store.is_unsafe_path 单源，空段 a//b 也拒绝）、目录名清洗（白名单 + 空回退 "upload"）、噪音跳过（.git 任意深度 + 构建产物目录，与扫描侧 iter_project_files 同一套）、单次上限 512MB、空清单报错——staged/ 目录在母版库同级、扫描后即用不自动清理；与 master.py 蒸馏预览的 mkdtemp 暂存（函数内自生自灭）区分命名 | stage.py（staged_root 推导 / stage_project_files）/ webapp.py（路由只收参数转调） |
| 条目库原语 | 模块库 / 赛题库 / 参考文件库共用的"目录即数据库"骨架：事务落盘、目录迭代、JSON 元数据读写与校验（read_json）、删除（delete_entry）、目录名 = 键的校验（validate_store_key）、必填字符串字段（require_str）、路径安全（is_unsafe_path）；不持业务形状，错误类型与文案归各库（StoreError 家族从不直达 web 层）；键文法 SLUG_PATTERN 单源（模块 slug 与母版平台名共用）；库的 StoreError 翻译骨架（3 分支映射 / require_str 包装 / key 校验包装）不参数化共享——各库语义差异真实（master 不存在特判 / manifest 合并分支 / topic 上下文文案），参数化劣于清晰重复；新库以 reference_library 为最新模板（错误类 + 元文件名 + 键文法 + 3 分支映射 + CRUD 形状） | entry_store.py |
| 库根 | 四库（模块库 modules / 母版库 masters / 赛题库 topics / 参考文件库 references）平级共居的根目录；随软件仓库走（仓库内 library/，git 版本化，ADR 0008）——库生命周期与软件一致、发布时随软件分发；config.json 只配 module_library_dir 与 masters_dir 两个键，topics / references 按约定跟随同级；**写库动作自动 git 提交**（工单 01 + 深化）：库 CRUD 落盘成功后自动 add + commit（变更限库根子树、不碰 src/），开关 config.json 的 autocommit_enabled 默认开，库根在 git 工作树外静默跳过；四库全部写函数全覆盖（结构测试强制分类注册表：commit / delegated / read 三类，新增公开函数漏挂即红）；批次级动作（confirm_topics / write_archive_entries）一次提交一批、不逐条提交 | config.py（布局推导 / 开关）/ autocommit.py（自动提交）/ master_store.py / library.py / topic_library.py / reference_library.py / archive.py |
| 参考文件库 | 与赛题库分开的独立素材区（存储与浏览入口都分开）：参考文件 = 不编译进生成工程的整包配套资料（套件例程 + 参考说明书）与提炼残渣，锚定赛题或套件；生成时 LLM 两级注入读取（先关联清单、需要时取全文）作学习素材——与模块相对（模块进工程，参考文件只被读）；区别于"可选配套"（那是模块的可裁剪组件，这是独立条目）；套件锚定的 kit 词表单源 = manifest.collect_kits（保序去重） | reference_library.py / webapp.py；两级注入装配在 generator.py（TopicContext）+ selection.py（清单段）+ reference_library.py（全文回读 read_fulltext，store 自持：路径安全 + 二进制跳过 + 标签单源） |
| 归档 | 提炼确认时的"归档为该题参考文件"动作：字节复制入库、锚定该题、内容自持（源工程删除不丢）；AI 判定不配归档的文件拒绝；归档批次与母版入库同事务；归档步骤在 archive.py（master 不 import 参考库族，防 import 链，函数级延迟导入） | archive.py / master.py / reference_library.py / report.py（ArchiveDecision）/ llm.py |
| 赛题库 | 与参考文件库分开的独立素材区：历年真题长 PDF 导入拆成的条目（年份 + 编号 + 题面），支持"几几年几题"编号解析为题面、作生成入口之一（贴题面或选历史题）；赛题条目锚定该题附带的完整程序（如 2026C 钥匙/锁两套）；关联模块可复用简介的专用性标注（"XX 题专用"）自动发现 | topic_library.py（拆条 LLM 协议与解析在 llm.py，确定性分块在 topic_library）/ webapp.py |
| 判定模型 | 提炼报告的判定条目与容器（FileDecision / DistillationReport）+ AI 判定素材（JudgmentFile / FileVersion）：形状 / 序列化 / 不变量（merge 必须带整合产物全文与说明；main_c_preview 与 uvprojx_preview 由平台重推导；版本分组不重不漏）唯一所有者；报告平台必须与工程平台一致（平台交叉校验）；扫描/对比模型（ProjectStructure / ProjectComparison）归模型层（report.py），master↔archive 依赖环消除；master 对 archive 保留函数级延迟导入（链约束非环，工单 C3） | report.py |
| 模板 main.c | 母版自带的最小系统板空 main（时钟初始化 + while(1) 空循环 + TODO 区），确定性模板、非 AI 生成；生成时被按赛题的"骨架"覆盖 | master.py |
| 整合 | 同路径多份内容不同时的动作：读多份 → 分析 → 产出通用版本（选一份是特例）；产物全文 + 说明进报告，用户审查后可改回选某份或剔除 | llm.py / master.py |
| 工程配置文件 | .uvprojx（stm32）：确定性渲染器现写（固定落位 user/Project.uvprojx，C8T6 设备块，文件树引用全部保留 .c/.s，IncludePath = 保留 .h 目录），移出 AI 判定（判例 09 治本）；.cproject/.project（mspm0）：确定性保留首份原样；条目不可改动作、进报告 keep 带规则原因；报告带 .uvprojx 全文预览 | keil.py（格式）/ master.py（编排）；渲染与预览经蒸馏适配器（守卫翻译归 MasterError） |
| 启动文件 | startup_stm32f10x_*.s 候选跨工程去重：至多保留一份（优先 _md，无则路径排序取第一份），落选规则剔除（Reset_Handler 重复定义风险）；密度守卫：保留份非 _md 大声失败（目标板 C8T6 中密度） | keil.py（格式）/ categories.py（去重生命周期）；谓词（is_startup_candidate / is_md_startup）经蒸馏适配器按平台取，mspm0 显式 False |
| 残留 | 构建产物（.o/.axf/.hex/.map/.lst/.crf/.dep/.lnp/.out/.elf/.htm）、备份（.bak 精确后缀，以及路径含 .bak 段的变体如 .bak2 / .bak_consolidate）、临时文件、IDE 用户选项（.uvoptx / .uvguix，编译时自动重建）：机器识别、确定性剔除，但进报告 exclude 清单并带规则化原因；构建输出目录（Debug/Release/Listings/Objects，后者任意层级）整目录忽略 | categories.py（规则）/ treewalk.py（目录忽略） |
| 项目树遍历 | "绕开噪音遍历工程目录"的唯一出处：iter_project_files（rglob + 统一跳过规则，绝对路径、排序确定性）+ skip_project_noise（顶层 .git / Debug / Release / Listings / Objects + Keil 输出目录任意层级）——母版扫描 / 旧工程扫描 / 生成摘要 / 语料构建六处消费，不再各走各的树（旧矛盾：Listings/ 下的 .uvprojx keil 找得到、master 忽略）；不持业务形状，类别判定归 categories.RuleCategory | treewalk.py |
| 二进制 | 非源码素材（文档 / 图片 / 模型 / 压缩包 / .exe 等）：文件头含 NUL 字节即判定，读全文会污染 LLM 判定素材，确定性剔除，但进报告 exclude 清单并带规则化原因 | categories.py |
| 文件类别 | 残留 / 旧 main.c / 基础设施 / 二进制四类的统一生命周期：识别（reason_of）→ 扫描分类 → 对比并集 → 报告汇编 → 越界拦截（AI 判定即报错）→ 处置校验；新增类别 = RULE_CATEGORIES 加一条 + 结构/对比字段声明 | categories.py（RuleCategory / RULE_CATEGORIES / classify，唯一出处） |
| 骨架 | AI 生成的 main.c（初始化序列 + TODO 预留区）+ 静态自检（幻觉调用改注释占位） | skeleton.py |
| C 词法层 | C 源码文本的机械切分唯一出处：围栏剥离 / 行号检测、注释剥离（keep_preprocessor 轴：# 行透传与否）、引号 include 提取、顶层 #define 扫描、语句级切分原语（iter_c_regions 区域迭代 / match_bracket 括号配对 / next_significant 空白注释跳读，骨架替换走查与死循环检测的消费基座）；接口 = 字符串进 / 字符串出，不碰盘上文件；不做调用形态识别（那是骨架自检的语义判断） | clex.py |
| 校验语料 | 生成前五道门禁共吃的内存语料：模块文件（文本 / 类别 / 所在目录）+ 母版头 + 母版搜索目录 + main.c，一次读盘；门禁退化为吃语料的纯谓词（可内存直构测试），不各自读盘 | generator.py（ModuleCorpus / ModuleFile / build_module_corpus） |
| 模块摘要 | 模块库摘要对象（喂 LLM 的可用模块清单）：slug / description / kits（collect_kits 单源）/ 依赖；行渲染唯一实现 = to_line()（字符串只在 prompt 边界渲染一次，无反向解析方）；known_slugs 取 slug 字段 | manifest.py（ManifestSummary / build_manifest_summaries 批量投影） |
| 修改器 | 平台工程文件适配器：Keil 改 .uvprojx、CCS 改 .cproject；各自是格式读 + 写的唯一所有者；XML 解析 / 写回 / 头部回注与 include 查找器（find_project_file，孪生查找器收敛）/ 条目解析核心（resolve_include_entries：绝对保留 / 相对基准 / 去重保序 / resolve）共享 projectfile.py 底座，宏策略归平台模块（ccs 展开 ${PROJECT_LOC} / ${PROJECT_ROOT} 并跳过 SDK 宏与 ${ 残留，keil 无宏）。ccs.py 双格式认知：同时认 CCS classic 与 Theia 20.5（TMS470_TICLANG 4.0）——差异在 cdtBuildSystem 的 storageModule 位置（classic 在 settings 内、Theia 独立）、include/define 选项 superClass 命名空间（ti.ccs.misc.* / com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.*）与位置（classic 直接子元素、Theia 在编译器 tool 内），单实现路径通吃；include 值展开 ${PROJECT_LOC} / ${PROJECT_ROOT}，SDK 环境宏（${COM_TI_MSPM0_SDK_*}）跳过不猜。include 读侧接缝：patchers.include_search_dirs 按平台分派——stm32 走 keil 版 .uvprojx IncludePath、mspm0 走 ccs 版 .cproject buildIncludePath | keil.py / ccs.py / patchers.py / projectfile.py |
| 平台警告 | missing / unverified / hardware_bound，生成前暴露 | selection.py |
| 功能需求层 | 推荐输出的第一层：题面驱动的能力/外设级需求清单（声光提示 → LED/蜂鸣器、识别数字 → 视觉），粒度贴题面关键词；每条必须挂题面对应句（逐句对照），禁止题外联想——"送药小车所以需要视觉"是脑补，题面要求识别数字才需要视觉 | selection.py |
| 逐句对照 | 收敛循环的机械防漏机制：题面按句编号，每句对应功能需求或"无功能"；找不到对应句的功能 = 脑补，删 | selection.py |
| 实现覆盖检查 | 功能需求逐条查库内模块能否实现：命中 → 库内模块（可勾选进工程）；无命中 → 库外建议 | selection.py |
| 库外建议 | 无库内实现的功能的外设推荐：类别名（视觉模块）+ 常识举例（K230 / OpenMV），仅展示、不进工程、不参与生成；name 只允许硬件词表条目（型号或类别），词表外型号降级为类别或拒收，examples 自由发挥 | selection.py |
| 硬件词表 | 电赛常见硬件名两条目型（类别 / 具体型号），进选模块 prompt 作科普素材、作库外建议 name 的校验源，可手补 | selection.py |
| 收敛循环 | 推荐分析以题面为依据反复自检修订（删脑补 / 补遗漏 / 重查覆盖），连续两轮功能需求层一致即收敛（上限 4 轮）；拿不准暂停向用户补问；收敛解可缓存进赛题条目（v2，库内命中每次现算，库会变） | selection.py / webapp.py |
| 错误映射 | 路由异常的唯一出口：error_to_http 表把核心异常转 HTTP 状态与中文 message（业务 400 / LLM 502 / 文件系统 400）；**未登记异常 = 真 bug → 500 大声失败**，不吞成业务 400 | errors.py（error_entry 单表，webapp 只取值 / 包装；结构测试反射包内全部异常类防漏登） |
| 进度事件 | 后端经 SSE 推送的实时进展（提炼 = 阶段 / 批次 / 补问轮，推荐 = 收敛轮次 round / converged；最后一个事件携带完整结果）；模型单次调用期间不产生事件，存活证明 = 客户端每秒跳动的计时器 | llm.py / selection.py（进度发射）/ events.py（事件词表唯一出处，含终态）/ sse.py（线格式与流化运行器） |

## 架构要点

- 薄壳（webapp 路由 / LLM 网络调用 / 文本抽取）包裹纯逻辑核心。
- 判定素材模型归模型层（依赖倒置）：JudgmentFile / FileVersion 在 report.py（master 构造、llm 消费），llm 层依赖模型层而非反向；master 不再从 llm 导入模型类型（仅 LLM 协议参数类型）。版本分组不变量（版本工程名组不重不漏）在素材模型上唯一声明与校验。
- llm.py 拆层——域判决随域走（照 report.py / selection.py 先例）："模型输出 → ModuleSelection"整条解释链归 selection.build_module_selection（需求派生 / 词表约束 / DeepSeek 怪癖，错误类型 SelectionError 由传输侧翻译回 LLMError），ValidationResult 归 library.py，llm 缩为 协议 + 提示词 + 机械解析 + 预算 薄传输层。
- 文件类别生命周期单源化：四大类别（残留 / 旧 main.c / 基础设施 / 二进制）+ 工程配置文件（工单 09）各是一条 `RuleCategory` 描述（识别规则 + 确定性处置 + 报错文案），流水线遍历 `RULE_CATEGORIES`，不再每处复制平行分支；启动文件候选是表内钩子（决策 2，跨工程去重）。类别表与 `classify` 收进 categories.py，master 只消费（结构测试防回退：恒等引用 + 模块内无规则函数）。
- 蒸馏侧平台适配接缝 = distill_adapters（摘要读 / 渲染（含密度守卫翻译）/ 启动候选谓词 per platform；mspm0 显式无操作；母版库入库结构校验留在 master_store，存储域边界）。识别知识（工程配置文件后缀表）单源 = platforms.PLATFORM_CONFIG_FILE_SUFFIXES。
- 错误映射单源化：路由不写 catch 元组（漏类型是裸 500 的 bug 根源），`_map_errors` 包装兜底统一走 error_to_http 表；表住 errors.py，结构测试反射枚举包内全部异常类断言已登记（白名单只放从不直达 web 层的类）——漏登从此是测试红，不是线上 500。
- 库素材拼装标签格式单源 = library.file_label：模块源码 / 参考素材 / 参考全文共用（prompt 可见契约，改格式只改这一处——曾三处各抄一份，漏一处模型就逐功能看到不同格式）。
- 生成流程的接缝是 `generator.generate_project`（选模块 → 定位母版 → 生成 → 摘要；内部落盘步骤 `generate`）；母版库布局（masters_dir/<platform>）归母版库模块（`master_store.master_project_dir`）。赛题入口装配 = `generator.resolve_topic_context` 唯一出处（永远返回 TopicContext，key 空串 = 未识别到历史赛题），路由只消费不装配。
- 生成侧读缝成真——include 搜索目录按平台分派（写侧 patcher registry 对偶），generator 不再 import 平台模块。外部头豁免同缝：工具链头在 keil/ccs 声明、经 patchers.external_headers 分派（跨平台工具链头拒绝放行），C 标准库头（_LIBC_HEADERS）留门禁，generator 不持有平台工具链知识。
- 模块源读路径单源：模块文件的读盘与头部判定归 skeleton.py 原语（read_module_sources + is_header_path），errors="replace" 编码策略单源——骨架（build_skeleton_interfaces）与生成语料（build_module_corpus）同读法，非 UTF-8 头文件骨架阶段不再崩（曾各抄一份读盘、两种容错）。
- 不变量：任何校验失败都在落盘前发生，绝不产出残缺工程。
