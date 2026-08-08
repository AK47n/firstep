# CONTEXT.md — 电赛工程生成器

单上下文领域词表（架构评审 / 领域建模的共享语言）。实现决策见 `docs/adr/`。

## 领域词表

| 术语 | 含义 | 主要实现 |
|---|---|---|
| 赛题 | 粘贴或上传（PDF / .docx / .txt / .md）的竞赛题目原文 | extraction.py → str，贯穿所有 LLM prompt |
| 平台 | `stm32`（STM32F103C8T6 / Keil5）、`mspm0`（地猛星 MSPM0G3507 / CCS） | 词表在 platforms.py；行为在 patchers.py / master.py / webapp.py |
| 模块 | 可复用 .c/.h 单元 + 机器可读 manifest；库目录即数据库；与功能库相对——模块承载外设/赛题功能，功能库是母版自带底层库 | manifest.py（模型）/ library.py（库操作） |
| manifest | 模块目录下 manifest.json：slug、简介、依赖、平台条目（文件 / 验证状态 / 硬件绑定 / 备注 / 硬件身份字段 kit + source_url） | manifest.py |
| 简介 | manifest.description，判据三要素：① 与代码一致（AI 校验）；② 硬件身份可确认——套件型号（kit）与购买链接（source_url），平台条目字段、新录入必填、URL 格式校验、由人补填；③ 专用性——逻辑绑定具体赛题的模块必须标注"XX 题专用"（如 lock_control / zone = 2026C 数字钥匙题专用，pid = 巡线题专用） | library.py / llm.py |
| 依赖 | manifest 声明的模块依赖，生成前递归展开（依赖先于使用者）；上层依赖下层；不得声明对功能库的依赖（母版必有，声明反而使解析器找不到而报错） | selection.py |
| 可选配套 | 模块的可裁剪组件：如 filter 之于 uwb_uart——代码层现状为必需依赖（uwb_uart.c 写死 include 与滤波调用），可选化（条件编译 + 生成器按选中定义宏）已立项未实现；普适 filter / 普适巡线逻辑为将来方向 | （未实现） |
| 母版 | 每平台一个的基础工程；现阶段 = 空的最小系统板工程（平台基础设施齐全 + 模板 main.c，能直接编译烧录；stm32 母版自带全套逐飞库 ml_* 功能库）；元数据在母版目录外的平级 json | master.py |
| 功能库 | 母版自带的底层库（stm32 母版 = 逐飞 ml_*：I2C/UART/PWM/GPIO/OLED 等，headfile.h 聚合），先于一切模块存在、生成时随母版进工程；不属于模块库 | masters/stm32/ml_libs |
| 提炼 | 导入多旧工程 → 对比 → AI 判定 → 报告（保留 / 整合 / 剔除 + 残留清单）→ 确认 → 入库；判定范围 = 公共 + 冲突 + 独有全部逐个判定，唯一判据：读内容判断是否通用、是否基础建设必需，不看重复次数 / 出现范围；确认是一条事务（confirm_distillation） | master.py + llm.py |
| 参考文件库 | 与赛题库分开的独立素材区（存储与浏览入口都分开）：参考文件 = 不编译进生成工程的整包配套资料（套件例程 + 参考说明书）与提炼残渣，锚定赛题或套件；生成时 LLM 两级注入读取（先关联清单、需要时取全文）作学习素材——与模块相对（模块进工程，参考文件只被读）；区别于"可选配套"（那是模块的可裁剪组件，这是独立条目） | （未实现） |
| 赛题库 | 与参考文件库分开的独立素材区：历年真题长 PDF 导入拆成的条目（年份 + 编号 + 题面），支持"几几年几题"编号解析为题面、作生成入口之一（贴题面或选历史题）；赛题条目锚定该题附带的完整程序（如 2026C 钥匙/锁两套）；关联模块可复用简介的专用性标注（"XX 题专用"）自动发现 | （未实现） |
| 判定模型 | 提炼报告的判定条目与容器（FileDecision / DistillationReport）+ AI 判定素材（JudgmentFile / FileVersion）：形状 / 序列化 / 不变量（merge 必须带整合产物全文与说明；main_c_preview 与 uvprojx_preview 由平台重推导；版本分组不重不漏）唯一所有者；报告平台必须与工程平台一致（平台交叉校验） | report.py |
| 模板 main.c | 母版自带的最小系统板空 main（时钟初始化 + while(1) 空循环 + TODO 区），确定性模板、非 AI 生成；生成时被按赛题的"骨架"覆盖 | master.py |
| 整合 | 同路径多份内容不同时的动作：读多份 → 分析 → 产出通用版本（选一份是特例）；产物全文 + 说明进报告，用户审查后可改回选某份或剔除 | llm.py / master.py |
| 工程配置文件 | .uvprojx（stm32）：确定性渲染器现写（固定落位 user/Project.uvprojx，C8T6 设备块，文件树引用全部保留 .c/.s，IncludePath = 保留 .h 目录），移出 AI 判定（判例 09 治本）；.cproject/.project（mspm0）：确定性保留首份原样；条目不可改动作、进报告 keep 带规则原因；报告带 .uvprojx 全文预览 | keil.py / master.py |
| 启动文件 | startup_stm32f10x_*.s 候选跨工程去重：至多保留一份（优先 _md，无则路径排序取第一份），落选规则剔除（Reset_Handler 重复定义风险）；密度守卫：保留份非 _md 大声失败（目标板 C8T6 中密度） | keil.py / master.py |
| 残留 | 构建产物（.o/.axf/.hex/.map/.lst/.crf/.dep/.lnp/.out/.elf/.htm）、备份（.bak 精确后缀，以及路径含 .bak 段的变体如 .bak2 / .bak_consolidate）、临时文件、IDE 用户选项（.uvoptx / .uvguix，编译时自动重建）：机器识别、确定性剔除，但进报告 exclude 清单并带规则化原因；构建输出目录（Debug/Release/Listings/Objects，后者任意层级）整目录忽略 | master.py |
| 二进制 | 非源码素材（文档 / 图片 / 模型 / 压缩包 / .exe 等）：文件头含 NUL 字节即判定，读全文会污染 LLM 判定素材，确定性剔除，但进报告 exclude 清单并带规则化原因 | master.py |
| 文件类别 | 残留 / 旧 main.c / 基础设施 / 二进制四类的统一生命周期：识别（reason_of）→ 扫描分类 → 对比并集 → 报告汇编 → 越界拦截（AI 判定即报错）→ 处置校验；新增类别 = RULE_CATEGORIES 加一条 + 结构/对比字段声明 | master.py（RuleCategory / RULE_CATEGORIES） |
| 骨架 | AI 生成的 main.c（初始化序列 + TODO 预留区）+ 静态自检（幻觉调用改注释占位） | skeleton.py |
| 修改器 | 平台工程文件适配器：Keil 改 .uvprojx、CCS 改 .cproject；各自是格式读 + 写的唯一所有者；XML 解析 / 写回 / 头部回注共用 projectfile.py 底座 | keil.py / ccs.py / patchers.py / projectfile.py |
| 平台警告 | missing / unverified / hardware_bound，生成前暴露 | selection.py |
| 功能需求层 | 推荐输出的第一层：题面驱动的能力/外设级需求清单（声光提示 → LED/蜂鸣器、识别数字 → 视觉），粒度贴题面关键词；每条必须挂题面对应句（逐句对照），禁止题外联想——"送药小车所以需要视觉"是脑补，题面要求识别数字才需要视觉 | llm.py（未实现） |
| 逐句对照 | 收敛循环的机械防漏机制：题面按句编号，每句对应功能需求或"无功能"；找不到对应句的功能 = 脑补，删 | llm.py（未实现） |
| 实现覆盖检查 | 功能需求逐条查库内模块能否实现：命中 → 库内模块（可勾选进工程）；无命中 → 库外建议 | llm.py（未实现） |
| 库外建议 | 无库内实现的功能的外设推荐：类别名（视觉模块）+ 常识举例（K230 / OpenMV），仅展示、不进工程、不参与生成；name 只允许硬件词表条目（型号或类别），词表外型号降级为类别或拒收，examples 自由发挥 | llm.py（未实现） |
| 硬件词表 | 电赛常见硬件名两条目型（类别 / 具体型号），进选模块 prompt 作科普素材、作库外建议 name 的校验源，可手补 | llm.py（未实现） |
| 收敛循环 | 推荐分析以题面为依据反复自检修订（删脑补 / 补遗漏 / 重查覆盖），连续两轮功能需求层一致即收敛（上限 4 轮）；拿不准暂停向用户补问；收敛解可缓存进赛题条目（v2，库内命中每次现算，库会变） | llm.py / webapp.py（未实现） |
| 错误映射 | 路由异常的唯一出口：error_to_http 表把核心异常转 HTTP 状态与中文 message（业务 400 / LLM 502 / 文件系统 400）；**未登记异常 = 真 bug → 500 大声失败**，不吞成业务 400 | webapp.py（_error_response / _map_errors） |
| 进度事件 | 提炼期间后端经 SSE 推送的实时进展（阶段 / 批次 / 补问轮；最后一个事件携带完整报告）；模型单次调用期间不产生事件，存活证明 = 客户端每秒跳动的计时器 | llm.py / webapp.py |

## 架构要点

- 薄壳（webapp 路由 / LLM 网络调用 / 文本抽取）包裹纯逻辑核心。
- 判定素材模型归模型层（依赖倒置）：JudgmentFile / FileVersion 在 report.py（master 构造、llm 消费），llm 层依赖模型层而非反向；master 不再从 llm 导入模型类型（仅 LLM 协议参数类型）。版本分组不变量（版本工程名组不重不漏）在素材模型上唯一声明与校验。
- 文件类别生命周期单源化：四大类别（残留 / 旧 main.c / 基础设施 / 二进制）+ 工程配置文件（工单 09）各是一条 `RuleCategory` 描述（识别规则 + 确定性处置 + 报错文案），流水线遍历 `RULE_CATEGORIES`，不再每处复制平行分支；启动文件候选是表内钩子（决策 2，跨工程去重）。
- 错误映射单源化：路由不写 catch 元组（漏类型是裸 500 的 bug 根源），`_map_errors` 包装兜底统一走 error_to_http 表；新异常类型必须登记，否则按真 bug 500 暴露。
- 生成流程的接缝是 `generator.generate_project`（选模块 → 定位母版 → 生成 → 摘要；内部落盘步骤 `generate`）；母版库布局（masters_dir/<platform>）归母版模块（`master_project_dir`）。
- 不变量：任何校验失败都在落盘前发生，绝不产出残缺工程。
