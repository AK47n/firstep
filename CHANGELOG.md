<!-- changelog-auto: last-commit=71fe8e601524943d9be761d6a99e62c0a8075f64 -->
# 更新记录

（格式说明：`## YYYY-MM-DD` + `- HH:MM 描述`，新记录插最前面，日期组倒序、
组内条目按时间先后写；`HH:MM` 时间前缀可省略。以下为示例）

## 2026-08-25
- 00:04 工单 deepen-report/01：深化完成后展示「深化效果」——main.c 前后确定性 diff 报告（统计+逐处改动点），不再只有一句深化完成
- 00:12 工单 deepen-report/01 补丁：跨行块注释（/* TODO: …）起始行也能提取深化效果标题——真实深化发现任务状态机 TODO 是跨行注释
- 00:38 generate-conflict-guard：桌面同名工程冲突防护（同键互斥 + 目录裁决 + 失败清理 + 成功自动打开）
- 12:19 mspm0-uart-osr：母版 UART 过采样率 3x→16x，消除 SysConfig ovsRate 基线警告
- 12:56 ui-polish-11/01：阴影令牌化——亮色柔和灰影、普通卡片 hover 只提阴影不上浮
- 12:59 ui-polish-11/02：背景氛围光——body 固定层顶部青色径向微光 + 卡片顶部微渐变（装饰色令牌化）
- 13:01 ui-polish-11/03：表格行 hover 高亮——模块库/参考库/PDF 库/母版库 tbody 行背景 panel-2
- 13:04 ui-polish-11/04：呼吸光晕收敛——只有生成工程/让 AI 推荐/一键编译修复/确认入库/保存设置 5 个关键 CTA 保留 btn-breathe
- 13:08 ui-polish-11/05：折叠按钮弱化——默认半透明 hover 显现 + aria-label 读屏同步（collapseBtnLabel/syncCollapseBtn 纯函数 + 单测）
- 13:10 ui-polish-11/06：步号徽章统一圆角——24px 正圆与左侧步骤圆点呼应，两位数 10-12 自然加宽不挤压
- 13:54 ui-polish-12/01：设置页整卡折叠——默认收起次要卡 + localStorage 记忆，保存卡不可折叠
- 18:37 ui-polish-12/02：AI API 卡内「计费」小节折叠——默认收起 + 独立 toggle + 状态记忆；修复祖先卡被误判为小节的判别 bug
- 18:40 ui-polish-12/03：设置页折叠总开关——页首工具栏一键「全部收起/全部展开」，含计费小节并落盘记忆
- 18:54 生成页就绪总览条与卡片状态徽章（gen-overview/01-02）
- 19:04 生成页新增「检查能否生成」：判据与生成按钮同源 + 检查单面板（a3-readiness-check/01-02）
- 19:10 修正步骤 7 完成判定：默认布线生成 / 无需配置也显示完成（step7-done/01）
- 19:24 上传 PDF 显示页图：/api/extract 返回渲染页 + 前端页图展示（upload-pdf-pages/01-02）
- 19:29 图片上传显示原图：/api/extract 回传原图 + 前端原图箱展示（upload-image-preview/01-02）
- 19:47 问答式精注记：图注一轮描述后追问细节补型号/尺寸/引脚号，设置页加开关（vision-detail-qa/01-02）
- 20:17 生成页就绪总览条一键补齐与结果面板两列网格（gen-overview-act/01、gen-result-panel/01）
- 20:23 生成页细节打磨 D 系列：状态色三处统一 / 动效令牌化 / 修复·修订卡内分组（ui-detail/01-03）
- 20:46 main.c 工具栏（复制/下载/全屏）与视觉通道自检（mainc-tools/01、vision-selfcheck/01）
- 21:08 最近生成列表：recent.json 落盘与生成页历史条（recent-jobs/01）
- 21:13 最近生成条与下方卡片间距微调（recent-jobs-spacing）
- 21:32 评分点核对清单与模块选择网格（score-checklist/01、module-grid/01）
- 21:54 工单 desktop-platform-suffix/01：桌面工程目录名带平台后缀（Auto_Car_STM32 / Auto_Car_MSPM0），同题双平台各生成各的目录不撞护栏
- 22:02 工单 compile-error-jump/01：错误列表点 main.c 错误行 = 预览滚动定位并高亮（整行选中、折行精确），非 main.c 行维持源码行展开
- 22:06 工单 compile-error-jump/01 补充：headless 冒烟脚本（CDP 探针断言选区偏移/卡片可见/折行精确/非 main.c 回归/空预览 toast，11 项全 PASS）——验收证据随工单入库
- 22:16 文档与约定收尾：PowerShell 脚本 UTF-8 BOM 硬性约定写入 CLAUDE.md 与 workflow.md（含 nav-states.ps1 补 BOM 与 test_ps1_encoding.py 兜底测试）；E2/E3 工单状态标记 resolved

## 2026-08-24
- 00:09 按需视觉问答传输层与装配（工单 recommend-vision-qa/02）——vision_qa 渲染题面页针对性作答（否定词/异常判无绝不阻塞）+ 缓存键升级含 prompt + TopicContext.figure_pdf 带出 + /api/recommend 视觉配置时注入回调
- 01:04 取题面默认展示原题 PDF 页（工单 topic-pdf-viewer/01）——新增 /api/topics/{key}/pages 页图端点（定位题面页+逐页渲染 PNG+base64 data URL，四种失败路径 400 中文明确报错）+ 前端页图叠放/点击放大/文字收起切换，输入编号与用此题生成双路径接入
- 01:13 推荐澄清少问能从题面/图找到答案的问题（工单 clarify-vision-relax/01/02）——vision_answerable 放宽为题面引用图∧（点名图∨关键词），未点名图但问图内信息也走视觉从原题渲染页找答案（答不上照旧问用户）；CLARIFY_SYSTEM_PROMPT 补流程/时序/指示灯含义/计时起止绝不重复问条款；真机 2021F 三问原文回归测试
- 01:26 取题面展示多页题面完整页范围（工单 topic-pdf-viewer/02）——2021F 共 4 页此前只显示前 2 页（定位硬编码命中页起 2 页），现按真题汇总 PDF 页脚 (k, N) 归一：起始页=命中页-(k-1)、范围=起始页起 N 页（k 归一防定位落非首页卷进下一题），无页脚回退既有 span；补图注/视觉问答路径零改动；多页 PDF 假件独立成 tests/topic_pdf_fakes.py
- 08:41 赛题条目补图注
- 12:33 推荐补问全面收紧——无规定即无限制 + 材料性门槛 + 上限 5 条（工单 clarify-no-restriction/01）
- 12:52 题面「自定」即答案，未提及规格参数视为无限制（工单 02）
- 13:18 平台卡点击不再误清推荐勾选（工单 platform-click-guard/01）
- 13:35 main.c 编辑器行号与占位文字重叠 + 取题面 PDF 渲染期占位（工单 ui-polish-10/01,02）
- 19:20 模块 exclusive_group 声明 + 库级校验 + 摘要行互斥标注（工单 recommend-exclusive-groups/01）
- 19:35 ﻿feat: 推荐链路功能组选择卡 + hint 兜底（工单 recommend-exclusive-groups/02）
- 19:45 ﻿feat: 推荐提示词功能组互斥规则段 + 题面核查条（工单 recommend-exclusive-groups/03）
- 19:59 前端功能组选择卡——单选交换/取消/同组去重/需求灰注/多选警告（工单 recommend-exclusive-groups/04）
- 20:48 main.c 预览行号逐行显示 + 滚动三同步——三明治布局补齐 white-space/overflow/display/gutter（此前行号 1-9 两两挤行、滚动只动行号列不动代码、尾部 7px 错位）
- 20:55 main.c 预览加字号缩放（−/＋ 80%-200%，三明治三层 em 同缩 + localStorage 记忆；工单 code-zoom/01）
- 21:06 修复步骤2/4完成打勾：补齐赛题简介与参考资料判定（此前从未打勾）
- 21:15 修复推荐卡死：led 实例清单跨需求条目不一致改为并集合并
- 21:29 实例配置卡：依赖带入的多实例模块也允许配实例清单（2024H 只选 led_beep 也能配置灯的页面）
- 21:36 实例配置卡：展开即预填平台默认实例清单（不再空卡——只选 led_beep 也直接配好一版灯）
- 22:58 工单 ascii-project-name/01-03：工程目录名英文化（字典+AI 英文起名）根治中文路径乱码

## 2026-08-23
- 00:06 UI 打磨（ui-polish-6/02）：修复卡片折叠按钮（选择器失效变大 + 空状态无反馈）
- 00:25 测试：会话收尾自动清理桌面测试产物（AI 生成的赛题简介_时间戳）
- 00:30 UI 打磨（ui-polish-7/01）：字号体系美化（品牌 20 / 卡片标题 16 / 正文 14）
- 00:57 UI 打磨（ui-polish-7/02）：顶部导航字号加大（13.5→16px）并加字重与过渡
- 10:04 UI 打磨（ui-polish-7/03）：顶部导航栏吸顶固定（sticky）便于随时切换
- 10:09 UI 打磨（ui-polish-7/04）：步骤导航吸顶避开固定顶栏（CSS 变量跟随头部高度）
- 10:32 UI 打磨（ui-polish-7/05）：导航 hover 淡青圆角背景与激活 tab 渐变下划线（青→紫发光）
- 10:43 UI 打磨（ui-polish-8/01）：main.c 行号与语法着色（注释/字符串/关键字/数字/预处理五类 token）
- 10:46 UI 打磨（ui-polish-8/02）：步骤完成庆祝动画（徽章弹跳 + 顶部青光扫过，动画结束自清理）
- 10:47 UI 打磨（ui-polish-8/03）：toast 类型左边框与背景微染、点击关闭离场动画、reduced-motion 兼容
- 10:49 UI 打磨（ui-polish-8/04）：生成中阶段播报（校验/子阶段轮播/等待计时，修复中心阶段已覆盖）
- 10:49 chore(ui-polish-8)：四张工单标记 resolved
- 11:18 UI 打磨（ui-polish-9/01）：主按钮呼吸微光（disabled 无光、hover 暂停、reduced-motion 兼容）
- 11:20 UI 打磨（ui-polish-9/02）：赛题库卡片化（编号徽章+年份chip+题面预览，topicCardHTML 纯函数，保留 data-topic-use/del 契约）
- 11:21 UI 打磨（ui-polish-9/03）：设置页卡内小节分组（连接/计费、Keil-gmake/CCS 三件套、模块库-母版库）
- 11:22 UI 打磨（ui-polish-9/04）：高频按钮图标化（btnIcon 内联 SVG，data-ico 注入，17 按钮）
- 13:40 生成工程自动附带设计报告草稿与演示脚本（A2/A3）——demo_script/report_draft 纯函数渲染器 + LLM 方案段接线 + 前端摘要卡标注（四工单 resolved，实施与评审整改记录入库）
- 21:46 模块推荐 LLM 输出失控防护——select 请求加 max_tokens 上限（4096）+ 超长输出免重试守卫 + 观测响应前缀留痕（deepseek-v4-flash 曾无上限输出 20K tokens/次致解析失败重试烧钱烧时间）
- 21:56 澄清阶段蠢问题——clarify 题面预算 4000 提到 12000 字符（长赛题后半句被截导致模型问题面已明确的细节，如送药小车已说红色指示灯还问颜色）+ 提示词强制题面已明确的细节绝不重复问
- 22:09 本地模型错误提示分类——区分「Ollama 未启动」与「模型加载失败（内存不足）」（llama-server 崩溃特征换模型提示，不再误导启动 Ollama）
- 22:32 赛题条目补图注
- 22:35 共享 PDF 赛题补图注——页范围定位提取（2021F 图1 落地）+ 图内标注段长判定修正 + 澄清提示词图缺失兜底
- 23:05 赛题补图注改为渲染视觉优先——矢量图渲染+DeepSeek 视觉描述（extraction 渲染路径 + enrich 三级降级链 + 图号防撞与无实质过滤 + 双轴评审整改）；工单 01/02 实施记录入库
- 23:06 赛题条目补图注
- 23:18 模块选择连续 5 次失败——关闭 deepseek-v4-flash 思考模式（reasoning 吃光 max_tokens 致 content 为空、截断判确定性失败免重试）
- 23:24 模块选择域拒绝免重试——非多实例模块带 instances 改报 client 立即失败（同参数重试稳定同错）+ 提示词多实例规则前置硬约束
- 23:59 推荐阶段按需视觉问答编排（工单 recommend-vision-qa/01）——图内问题机械判定 + vision_qa 回调消化并入澄清历史 + 收敛补问带答案重跑，未注入时行为逐字节不变

## 2026-08-22
- 01:18 UI 打磨（ui-polish/01）：全局动效渐变微光与空状态升级
- 01:25 UI 打磨（ui-polish/02）：生成页左侧步骤导航与完成态
- 01:36 UI 打磨（ui-polish/03）：顶栏合并为单行并全量回归验证
- 12:18 UI 打磨（ui-polish-2/01）：步骤导航升级为胶囊标签
- 12:31 UI 打磨（ui-polish-3/01）：生成页草稿自动记忆（localStorage）
- 12:33 UI 打磨（ui-polish-3/02）：顶部流程进度条与完成计数
- 12:36 UI 打磨（ui-polish-3/03）：Toast 轻通知（生成/编译/复制/修订等 9 处接入）
- 22:19 UI 打磨（ui-polish-4/01）：生成页卡片折叠与收起已完成
- 22:23 UI 打磨（ui-polish-4/02+03）：赛题库一键生成与复制输出路径
- 22:59 UI 打磨（ui-polish-5/01）：亮色主题切换（防闪烁 + 偏好记忆）
- 23:04 UI 打磨（ui-polish-5/02）：LLM 用量统计（会话差分 + 历史累计 + 费用估算）
- 23:06 UI 打磨（ui-polish-5/03）：细节包（动效降级 + 禁用态统一 + 按钮 spinner 对齐）
- 23:44 UI 打磨（ui-polish-6/01）：内容区加宽（生成页 1400 / 其它页 1280 居中）

## 2026-08-21
- 00:54 生成尾部落盘上下文清单 + 历史目录反推 + 加载 API（工单 revise-deepen/01）
- 01:08 工单 01 评审整改——清单字段收敛 spec、main.c 现读、空模块集提示、反推健壮性
- 01:14 修订影响分析与确定性 diff（工单 revise-deepen/02）
- 01:23 工单 02 评审整改——事件常量单源、逐条覆盖与一致性校验、重试兜底测试
- 01:27 修订执行——备份 + 覆盖式重生成 + 回滚（工单 revise-deepen/03）
- 01:35 工单 03 评审整改——ccs_tools 透传、回滚路径安全、展开集 diff、清单一致性
- 01:39 深化——填 TODO + 编译验证闭环（工单 revise-deepen/04）
- 01:44 工单 04 评审整改——工具链探测复用单源、状态文案单源、工单目录入库
- 01:53 前端「修订与深化」阶段卡 + 补题面闭环（工单 revise-deepen/05）
- 01:58 工单 05 评审整改——补题面闭环前端接线、回滚竞态、Q&A 原文展示
- 20:42 视觉通道切 DeepSeek 原生——默认值/主 key 复用/BMP 友好报错/观测文案全链路（工单 vision-deepseek-native/01）
- 20:42 设置页视觉文案去智谱化——复用主 key 提示 + CONTEXT.md 图注更新（工单 vision-deepseek-native/02）
- 21:02 设置页视觉服务下拉——DeepSeek / 智谱一键切换，自动填参数与 key 沿用（工单 vision-provider-switch/01）
- 21:46 PDF 内嵌图自动转码——BMP / JPEG2000 转 PNG 后走 DeepSeek 视觉（工单 vision-format-transcode/01）

## 2026-08-20
- 00:00 多实例默认兜底——AI 没猜实例时按平台默认自动填（stm32 红黄绿 / mspm0 单实例，与不配置生成等价零回归，工单 instance-default-fallback/01）+ backlog 计划
- 00:08 推荐与蒸馏进度面板接入 LLM telemetry 快照——每次调用完成显示调用数 / provider 分流 / 最新操作 / 耗时（照修复流程先例，bind_llm_telemetry + 前端展示位 + 生命周期清理 + 结构钉）
- 00:17 赛题条目补图注
- 00:39 引脚自动配置（一键解冲突，合法共享保留+标注，工单 pin-auto-assign/01）+ LLM telemetry 状态行中文化（operation/状态/计数全映射，三面板共用）
- 00:52 赛题答疑 Q&A 注入推荐——输入框随请求带 qa_text，题面后独立段注入（权威澄清，不并入题面不干扰收敛判定）+ 缓存 qa_sha256 指纹（Q&A 变化失效重推，工单 qa-material/01）
- 00:52 赛题答疑 Q&A 输入框显示高度 4 行调 6 行 + 说明点明可输入任意多行（rows 非上限）
- 01:01 gmake 探测补 CCS 自带路径与 mingw32-make 兜底——Windows 上 CCS 的 gmake 不在 PATH、MinGW 的 make 名为 mingw32-make，之前漏探显示 ❌（实测 C:/ti/ccs2050 自带 + C:/mingw64 均可用）
- 01:08 推荐缓存加模块库指纹——library_sha256 = ManifestSummary 摘要行排序 hash，库变（模块增删/简介/能力/多实例标注）缓存失效走真实推荐，旧缓存无字段保守失效（工单 recommend-cache-fingerprint/01，backlog 清零）
- 11:19 赛题条目补图注
- 21:38 赛题条目补图注
- 22:05 赛题文件重清洗 + 补图注加共享 PDF 守卫
- 22:05 推荐链路修正 + LED 多实例死按钮 + 内嵌母版标注
- 22:26 历史赛题桌面目录名改为「编号 + 短题名」

## 2026-08-19
- 00:02 费用估算按缓存命中/未命中拆分计价（DeepSeek Flash 官方两档输入价）
- 00:15 计费时段选择（高峰期/空闲期）——按所选时段官方价计算与展示
- 10:55 推荐结果携带题面评分点
- 11:52 生成产物输出评分点清单
- 12:50 推荐结果展示评分点并完成前端回归
- 15:07 修复 PR109 评审发现的规格偏差
- 16:32 LLM 观测、成本控制与评分点闭环
- 21:08 生成页支持生成到桌面赛题文件夹——AI 题名命名与重名时间后缀（工单 desktop-topic-output/01）
- 22:08 赛题条目补图注（取题面自动补矢量图标注布局，工单 topic-vision-notes/02）
- 22:42 赛题条目补图注
- 22:46 赛题条目补图注
- 22:48 视觉通道升级与历史赛题图注闭环（GLM-4.6V-Flash 默认 / key 掩码统一 / 拆条视觉 / 存量补图注两级化——矢量图标注布局优先、视觉兜底，工单 topic-vision-notes/01-03）
- 23:11 设置页定价表格重复显示——renderPriceReference 重绘前清空 tbody（loadSettings 每次进设置页都调用，appendChild 不清空会累积，曾出现重复 4 遍）+ 结构钉测试
- 23:11 计费时段默认改低谷 off_peak（配置 / settings GET 与 PUT 缺省同步，基准价按官方空闲档计）
- 23:22 最近 LLM 工作流调用明细行完整显示——去掉单行截断（white-space nowrap + ellipsis 改 normal + break-all，超长自动换行）

## 2026-08-18
- 09:53 LLM 调用结构化观测（llm_observation 记录：operation/provider/status/parse_status/error_kind/request_bytes/usage，日志脱敏）（工单 llm-observability-dashboard/01）
- 13:49 LLM 重试预算护栏（RetryBudget 上限 + 预算耗尽 not_sent 观测）（工单 llm-observability-dashboard/01）
- 14:45 LLM 观测收集器（工作流级 collector：workflow_id + 单调 sequence + 脱敏收集）（工单 llm-observability-dashboard/01）
- 17:18 修复 SSE 流内实时 LLM 遥测（llm_telemetry 事件 + 前端紧凑状态行）（工单 llm-observability-dashboard/02）
- 18:59 设置页最近 LLM 工作流仪表盘（内存 ring buffer + 只读端点 + 脱敏摘要/明细）（工单 llm-observability-dashboard/03）
- 19:29 规范：仓库文档与提交信息统一中文——工单与 CHANGELOG 英文记录全量翻译、.githooks/commit-msg 中文门禁（GBK/UTF-8 兼容 + lib 机器提交豁免）、语言规范写入 workflow.md/CLAUDE.md、tests/test_repo_language.py 兜底
- 20:13 LLM 成本控制闭环——费用估算（可配置单价表 + 仪表盘费用行 + 本地路由节省额）与推荐缓存上 Web（done 载荷复用 + 指纹校验 + 设置开关）
- 20:44 推荐收敛提速——核验轮短标记提前停（模型自报无修订即收敛，省 2-4 分钟/轮）+ 收敛轮数上限可配置（设置页 2/3/4）
- 22:22 新增 adc/servo 模块（b1-adc-servo/01-03）——模拟采样与舵机角度双平台落地
- 22:24 K230 副产物多模板（k230-multi-template/01-04）——python_artifact 多模板声明 + 矩形识别模板
- 23:32 给 DeepSeek 装眼睛（vision-eyes/01-04）——免费云端视觉通道 GLM-4V-Flash
- 23:42 设置页 DeepSeek Flash 官方价格参考表（2026-08 官方定价）

## 2026-08-17
- 00:02 ball_detect 模块重命名为 coord_detect（坐标检测）——纯机械改名（git mv 保留历史，解析逻辑/协议一字不改）：C 符号 BallResult→CoordResult、ball_detect_*→coord_detect_*、BALL_RX_BUF_SIZE→COORD_RX_BUF_SIZE、引脚宏 BALL_DETECT_UART*→COORD_DETECT_UART*；帧契约单源 BALL_FRAME_*→COORD_FRAME_*（前缀值 "B" 保持——协议字节与模块名解耦）、模板占位符 ball_frame_format→coord_frame_format、BALL_THRESHOLD→COLOR_THRESHOLD；k230 依赖/母版/测试/CONTEXT 同步（工单 coord-detect-rename/01）
- 00:08 模块重命名 ball_detect → coord_detect（工单 coord-detect-rename/01）
- 00:21 模块重命名 ball_detect → coord_detect（工单 coord-detect-rename/01）
- 13:24 随工程生成 README（工单 project-readme/01）
- 13:29 随工程生成「上手即战」README（工单 project-readme/01）
- 13:39 README 追加两章：快速上手（编译+烧录）+ 验证顺序清单（工单 project-readme/02）
- 13:40 README 追加两章：快速上手（编译+烧录）+ 验证顺序清单（工单 project-readme/02）
- 14:00 README 引脚表：绑定生效引脚 + 多实例每实例一行（工单 project-readme/03）
- 14:02 README 引脚表：绑定生效引脚 + 多实例每实例一行（工单 project-readme/03）
- 20:48 配置扩展：AppConfig 增可选本地 LLM 端点字段（工单 local-llm-routing/01）
- 21:08 路由层：RoutingLLM 本地文本三调用派发 + build_llm 接线（工单 local-llm-routing/02）
- 21:20 设置页 UI：本地模型端点可填写/清空 + /api/settings GET/PUT 新字段（工单 local-llm-routing/03）
- 22:43 解析层剥围栏：_unwrap_json_fence 单点剥 json_mode 外层 + 文本模式不动（工单 local-llm-json-group/01）
- 23:14 扩本地组：LOCAL_LLM_METHODS 3→6（澄清/简介校验/归档判定转本地，其余仍留 DeepSeek）（工单 local-llm-json-group/02）

## 2026-08-16
- 00:19 骨架生成新增自检冒烟模式（main_mode=smoke，OLED 为主串口为辅）
- 00:37 骨架生成注入参考实现草稿（锚定+手动全文，reference_ids 透传）
- 00:55 骨架参考注入按合计预算截断，防多篇全文撑爆 128KB 网关
- 01:45 自检骨架 sanitize 跨词法区域调用替换残留实参尾巴
- 08:44 模块依赖清理——motor 纯驱动化 + 编码器计数迁入 motor + 依赖声明修正
- 09:29 led/beep 拆分为独立模块，led_beep 组合化，stm32 led 内嵌母版统一 API
- 09:34 LED 极性改为拉电流高电平点亮（一脚接地一脚接引脚，用户更正）
- 09:46 motor stm32 补统一 API（motor_set_duty/direction/encoder_read，与 mspm0 对偶）
- 10:02 ntb_time 补 stm32（SysTick 1ms 时间戳，get_time_stamp_ms 双平台对偶）
- 10:51 key/uart 补 stm32 + 骨架/冒烟 prompt 输出函数约束（防 LLM 出稿碎片）
- 11:42 module-functionalize 最后一批——协议驱动补 mspm0
- 12:33 解析类模型重试上限 3 → 5
- 12:39 骨架/冒烟出稿接入重试原语
- 13:19 module-polish 批次——debug_uart mspm0 + OLED 共同 API + delay_us + 编译矩阵
- 13:23 module-polish P2 收尾——led 便捷宏对齐 + motor 旧 API 标注
- 14:12 module-multi-instance 01——manifest 多实例能力声明 + 实例数据形状
- 14:31 module-multi-instance 02——实例展开 + 默认脚分配纯函数（命名/去重/上限守卫）
- 15:30 module-multi-instance 03——led 渲染 hook + led_instances.h 生成 + 骨架通道宏注入（stm32/mspm0 真编译 0 error）
- 16:00 module-multi-instance 04——webapp 请求层 instances 解析 + 前端实例配置 UI（增删改名/颜色/引脚，上限 8）
- 16:38 module-multi-instance 06——推荐链路 AI 猜实例数（题面「4 个指示灯」→ led×4）+ 实例解析/收敛键/done 载荷 + 前端回填实例卡
- 16:56 module-multi-instance 05——双平台编译回归关门验收
- 17:09 stm32 led_toggle 反转逻辑（高→灭/低→亮真翻转）
- 17:22 git log 自动补记手工文件缺失的日期
- 17:45 多实例配置「添加实例」按钮读错属性（data-add vs dataset.slug）导致点了没反应
- 18:03 第六步搜索框改为搜可用模块→点结果添加（去掉装饰性的已展开过滤，保留下拉两套共存）
- 18:35 第七步引脚配置新增总览模式——按模块着色已配置引脚（必接+可选已绑），多模块同脚时焊孔填充/描边/高亮环三层均分着色
- 18:58 回退 rebase 残留的 #94 运行时补记（webapp/test 改回 load_changelog 本地钩子口径）
- 19:14 头部品牌升级——firstep 双色(白+青)+终端闪烁光标+副标胶囊，标签页标题/流程副标题/步骤徽章对齐
- 19:50 mspm0.syscfg 文件模型模块——独占文法+一次解析+槽位身份原语（架构评审 ② 工单 01）
- 19:55 refactor(syscfg-model): 去掉解析产物死字段 modules（评审：speculative generality）
- 20:05 mspm0.syscfg 文件模型模块——独占文法+一次解析+槽位身份原语（工单 syscfg-file-model/01）
- 20:14 mspm0 syscfg 裁剪委托文件模型——prune_syscfg 切到 SyscfgModel.prune，删自有 addInstance/addModule 正则（工单 syscfg-file-model/02）
- 20:15 mspm0 syscfg 裁剪委托文件模型——prune_syscfg 切到 SyscfgModel.prune（工单 syscfg-file-model/02）
- 20:32 mspm0 syscfg 改写委托文件模型——rewrite_syscfg 切到 SyscfgModel.rewrite，删自有 $assign 文法/路径匹配（工单 syscfg-file-model/03）
- 20:33 mspm0 syscfg 改写委托文件模型——rewrite_syscfg 切到 SyscfgModel.rewrite，删自有 $assign 文法/路径匹配（工单 syscfg-file-model/03）
- 20:53 mspm0 syscfg 单一 pipeline 收尾——generator 写侧 prune+rewrite 单 pipeline、MSPM0_SYSCFG_FILENAME 迁入文件模型、删 shim/冗余、CONTEXT 词条（工单 syscfg-file-model/04）
- 21:12 前端裁决接缝 01——校验端点接 resolve_bindings（工单 pin-verdict-seam/01）
- 21:13 前端裁决接缝 01——校验端点接 resolve_bindings（工单 pin-verdict-seam/01）
- 21:43 骨架/编译编排归位——run_skeleton + run_compile 域函数（工单 route-orchestration-homing/01）
- 21:45 骨架/编译编排归位——run_skeleton + run_compile 域函数（工单 route-orchestration-homing/01）
- 22:34 manifest「Python 副产物」声明——python_artifact 能力块：缺省不落键/旧 manifest 逐字节兼容/非法值大声失败（工单 k230-vision-copilot/01）
- 22:42 manifest「Python 副产物」声明能力（工单 k230-vision-copilot/01）
- 23:00 生成写盘机制——选中 python_artifact 模块 → k230_render 渲染写 .py 副产物（工单 k230-vision-copilot/02）
- 23:04 生成写盘机制：选中带副产物模块 → 额外写 .py（工单 k230-vision-copilot/02）
- 23:22 k230 模块落地 + 真实视觉模板——manifest 依赖 ball_detect（files 空不重复声明串口 pins）+ CanMV main.py 模板（FPIOA 串口 → sensor → find_blobs 色块追踪 → CSV 帧 → UART）；双平台生成断言 + 帧契约锁扩 mspm0 + 零 C 文件模块依赖形态豁免（工单 k230-vision-copilot/03）
- 23:23 k230 模块落地 + 真实视觉模板——依赖 ball_detect + CanMV main.py 副产物模板（工单 k230-vision-copilot/03）
- 23:24 k230 模块落地 + 真实视觉模板（工单 k230-vision-copilot/03）
- 23:40 k230 前端闭环——产物摘要体现 .py 副产物（工单 k230-vision-copilot/04）
- 23:41 前端接入：模块配置 + .py 交付（工单 k230-vision-copilot/04）

## 2026-08-15
- 07:49 stm32 pwm 类型级解锁 + 骨架定时器冲突门禁
- 08:06 ml_led 双 LED 定义修复——pin_config.h 派生 + 低电平点亮翻转
- 08:14 stm32 startup 弱 handler 死循环雷拆除：B . → BX LR
- 08:39 软 I2C 参数化 + 共享端口宏异值门禁
- 09:41 stm32 enc 类型级 + EXTI 线冲突门禁 + motor 条件 handler + ml_exti 扩 48 项
- 10:46 stm32 uart 类型级 + TX/RX 对 + 实例冲突门禁 + isr.c 聚合 + fputc
- 12:08 mspm0 同族实例迁移 Tier A
- 13:18 mspm0 PWM 跨族迁移 Tier B：全类型级 + 两通道同实例门禁
- 13:50 stm32 默认 5 组同脚冲突重排 4 组 + 1 残留白名单
- 14:03 ntb_time 软件回绕累加修复时间戳语义
- 14:58 板图卡 7 说明与图例美化
- 15:27 mspm0 syscfg 按选中模块动态裁剪
- 16:07 mspm0 HUIDU R3/R4 板内化 PB6/PB7 + 默认冲突提示
- 17:17 步骤 6 下拉截断/紧凑两行/自动展开/来源标注 + 默认脚红圈高亮
- 17:42 步骤 7 可选角色默认折叠 + 交接提示词移到最后一步、补平台警告/引脚绑定/自动参考资料上下文
- 18:54 推荐模块移除不再回加 + 依赖模块无移除按钮 + 可选角色绑定后自动展开
- 19:49 mspm0 STEP_MOTOR SLP2/DIR2 板内化 PB6/PB7 + 改写器按实例路径定位重叠默认
- 20:20 模块平台徽标两行显示
- 20:46 更新记录改 git log 自动补录（post-commit 钩子）

## 2026-08-14
- 08:28 generate_check --reuse-recommend 推荐缓存 + 参数指纹警告（8m50s→2m41s）
- 09:41 gmake 报错路径 ../main.c 定位修复（构建目录基准 + ../ 前缀逐级剥除兜底）
- 10:07 推荐请求体预算保证：REFERENCE_FULLTEXT_CAP 60000→35000 + 澄清历史段两级截断
- 11:45 生成门禁 #if defined 预处理行误判修复（defined 入控制关键词 + 预处理行剔除）
- 12:55 修复请求体预算保证：文件上下文 wire 字节记账 + 回喂段截断
- 13:12 骨架提示词补「不声明未使用变量」约束（真机 UV4 0 警）
- 14:15 修复循环纳入 warning 收敛（停条件 passed && warnings==0）
- 15:37 修复循环轮上限终态加「继续修复」按钮
- 16:29 CLI 修复循环对偶补齐：发 previous_fixes + 超时停条件
- 16:32 请求预算 wire 口径统一：预算记账单源 budget.py + 推荐侧全文注入改 wire 字节预算
- 16:35 门禁闭包：第六道 unresolved_includes 纯谓词化
- 16:48 CLI 首编超时即停（timed_out 不喂修复循环）
- 19:06 mspm0 母版 syscfg 地猛星化 + 孤儿实例补齐
- 20:13 板级引脚配置数据层：boards 双板定义 + pins 声明 + stm32 硬编码迁移
- 21:35 板级引脚绑定机制层：bindings 模型 + 双平台写侧 + 两条门禁
- 22:21 板级引脚配置前端：板图 SVG 卡片 + 角色菜单 + bindings 载荷
- 23:36 板图细节多轮校正：蓝药丸排针按真板布局、俯视画法/上下校正、旋转 90°/180°、Type-C/排针朝向加长、板载共用引脚橙虚环警示、PA11/PA12 USB 共用解锁、PA18 BSL 注记

## 2026-08-13
- 10:19 参考文件库录入 TI MSPM0 SDK driverlib 例程 143 条（每例一条、平台 mspm0，adc / uart / spi / timx / gpio / dma / i2c / comp 等全外设；仅 UTF-8 文本，排除工具链胶水与 SDK 副本树；空骨架不入库）
- 10:37 例程标题改中文直观名（如「ADC12 单次转换」「定时器 QEI 编码器模式」），原 SDK 目录名保留在简介末尾；删 9 条 CCS 空工程模板；库内共 147 条
- 12:27 参考文件库「塔克R3两驱小车底盘资料」拆分为 6 条独立条目（DB20 电机 PID 五例 + 编码器电机小车控制源码，每例一条中文直观名标题 + 独立简介，搜索「舵机」等子功能可精确命中）；库内共 152 条
- 12:53 参考文件库「MSPM0_MOTOR参考例程」修复拆分为 3 条：GBK 转码补录 7 个电机核心源码（motor_crc / motor_read_enc / motor_set_speed / user.h / imu.c，原 UTF-8 直读静默漏录）+ 剥 source/ SDK 副本树与 gcc/iar/keil/ticlang 工具链胶水（镜像保真 + 清单留痕）+ 拆「MSPM0 Motor_Ctrl 电机控制例程」「MSPM0 m0imu 姿态例程」「MSPM0 MOTOR 例程移植笔记」，全文回读电机实现代码可见；库内共 154 条
- 13:45 参考全文回读改逐文件截断：read_fulltext 每文件独立截 20000 字符（截头带标注、措辞单源迁 library.truncate_content 共享层），注入处总截断 4000 → 60000（按 128KB 网关预算实测倒推）——旧实现首个大文件（素材清单 10 万+ 字符）吃光配额、真正代码进不了模型；现在每个文件开头都进上下文，电机拆分条目整条全量直传；截断文案共享层防环（reference_library 不运行时 import llm）
- 16:41 DeepSeek 网络/解析两类重试分流：网络 5 次指数退避 1/2/4/8s，解析 3 次快重试不变
- 18:21 mspm0 生成自动产出 CCS Debug/makefile 集 + 三件套探测（config 覆盖 > C:/ti/ccs*/ 扫描，缺一件整体跳过不阻断）
- 19:59 修复循环停滞检测 + 上轮应用结果回喂（0 applied 即停 + previous_fixes 透传）
- 23:15 generate_check CLI 修复循环 ≤3 轮与 web 对齐
- 23:38 推荐链路提速三棱镜：一轮问全 + 有历史跳过澄清门 + 收敛提前停（2026C 4→2 轮）

## 2026-08-12
- 00:04 DeepSeek 空内容偶发重试兜底（≤3 轮）
- 00:47 2024H 巡线 xunji 模块补录（MSPM0G3507）：白区计数路口 + 状态机 + 加权质心 + LED 声光
- 10:13 模块普适化：xunji / pid / ball_detect 剥离决策层为纯驱动、lock_control/zone 解散、config 决策参数剥离、六模块题词清理
- 14:11 PDF 资料库新栏上线 + 素材收录 9 份 + 全库 PDF 改名 21 个
- 14:43 全工具深色科技感换皮：近黑底 + 青色强调 + JetBrains Mono 自托管
- 15:02 生成页新增交接提示词栏：赛题 / 平台 / 模块 / main.c / 输出目录一键打包给下一个 AI
- 15:21 编译错误回填自愈：snippet 替换 + 备份回滚
- 16:38 自动编译修复闭环：生成后自动编译 → 报错自动喂 AI 修复 → 重编译验证 ≤3 轮，失败自动回滚
- 17:01 LLM 修复匹配容错：old_snippet 行首前缀归一化兜底，真机修复成功率提升
- 17:48 编译体验展示层：结果横幅四态 + 结构化错误列表 + 点击展开源码行 + 编译耗时
- 18:20 新增「更新记录」栏目（第 8 个 tab）：按天 + 时间点回看工具改进历程
- 19:32 编译判读换闸 + 契约对齐：验收脚本与生产同闸（-r 全量重建）、前端错误数改读 summary、无 AI key 也能编译看结果

## 2026-08-11
- 08:46 在途清零：分支清理 + 工作区干净
- 17:42 推荐两阶段编排归位 selection.run_recommendation，路由只取参 + 转调
- 18:20 推荐请求契约对偶：CLI / 前端双客户端字段与词表一致，两层可证伪实证
- 19:14 ball_detect 模块 NULL 解引用修复
- 19:36 zigbee_uart_key 文件 / 符号唯一化：修双选时的链接错误 L6200E
- 19:54 生成侧跨模块同名文件查重门：重复声明直接拦截并提示
- 20:33 2021F Keil 真机验收闭环：UV4 0 错 0 警（EXTI 编码器计数 + TIM3 调度 + pin_config 宏集中）
- 21:19 生成门禁装配表驱动化
- 22:20 产物树门禁对偶
- 23:21 澄清历史收敛透传：AI 不再重复问已答问题

## 2026-08-10
- stm32 电机链路可用性闭环：2021F 全链路可用（编码器 / 定时器调度 / 引脚配置）

## 2026-08-09
- 架构深化 v5 五工单闭环：master.py 三轴拆块 / 赛题入口单一接缝 / 模块摘要投影 / 蒸馏侧平台适配 / 参考全文归位
- 架构评审 8 候选 + include 解析契约工单（find_project_file / resolve_include_entries 共享原语）
- llm 拆层：域判决归 selection，llm 只留机械提取
- 推荐层平台过滤：mspm0 / stm32 模块各自可用，跨平台推荐不再出现
- 题库真机入库 + 模块推荐工作流归位

## 2026-08-08
- 生成门禁合 main：main.c 围栏剥离 + include 解析校验
- 工单 09 验收闭环：用户 Keil 复编 0 错 0 警
- SSE 流化运行器 / entry_store 原语补全 / 错误映射归位
- 架构深化 round2 六工单合 main

## 2026-08-07
- 模块推荐功能上线：AI 按赛题逐句对照功能需求，库内命中可勾选
- 赛题库 UI 新栏 + 题库真机入库 8 条

## 2026-08-06
- 参考库 UI 新栏
- 素材库批次 01/02/03 入库（PDF 资料、完整工程、源码文本）
- 工单 04 拆条分块

## 2026-08-05
- 项目启动：电赛工程生成器首个版本（赛题 → 完整工程生成）+ 工单体系建立
