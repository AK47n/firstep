# CONTEXT.md — 电赛工程生成器

单上下文领域词表（架构评审 / 领域建模的共享语言）。实现决策见 `docs/adr/`。

## 领域词表

| 术语 | 含义 | 主要实现 |
|---|---|---|
| 赛题 | 粘贴或上传（PDF / .docx / .txt / .md）的竞赛题目原文 | extraction.py → str，贯穿所有 LLM prompt |
| 平台 | `stm32`（STM32F103C8T6 / Keil5）、`mspm0`（地猛星 MSPM0G3507 / CCS） | 词表在 platforms.py；行为在 patchers.py / master.py / webapp.py |
| 模块 | 可复用 .c/.h 单元 + 机器可读 manifest；库目录即数据库 | manifest.py（模型）/ library.py（库操作） |
| manifest | 模块目录下 manifest.json：slug、简介、依赖、平台条目（文件 / 验证状态 / 硬件绑定 / 备注） | manifest.py |
| 依赖 | manifest 声明的模块依赖，生成前递归展开（依赖先于使用者） | selection.py |
| 母版 | 每平台一个的基础工程；现阶段 = 空的最小系统板工程（平台基础设施齐全 + 模板 main.c，能直接编译烧录）；元数据在母版目录外的平级 json | master.py |
| 提炼 | 导入多旧工程 → 对比 → AI 判定 → 报告（保留 / 整合 / 剔除 + 残留清单）→ 确认 → 入库；判定范围 = 公共 + 冲突 + 独有全部逐个判定，唯一判据：读内容判断是否通用、是否基础建设必需，不看重复次数 / 出现范围；确认是一条事务（confirm_distillation） | master.py + llm.py |
| 报告模型 | 提炼报告的判定条目与容器：形状 / 序列化 / 不变量（merge 必须带整合产物全文与说明；main_c_preview 由平台重推导）唯一所有者；报告平台必须与工程平台一致（平台交叉校验） | report.py |
| 模板 main.c | 母版自带的最小系统板空 main（时钟初始化 + while(1) 空循环 + TODO 区），确定性模板、非 AI 生成；生成时被按赛题的"骨架"覆盖 | master.py |
| 整合 | 同路径多份内容不同时的动作：读多份 → 分析 → 产出通用版本（选一份是特例）；产物全文 + 说明进报告，用户审查后可改回选某份或剔除 | llm.py / master.py |
| 残留 | 构建产物（.o/.axf/.hex/.map/.lst/.crf/.dep/.lnp/.out/.elf/.htm）、备份（.bak/*~）、临时文件：机器识别、确定性剔除，但进报告 exclude 清单并带规则化原因；构建输出目录（Debug/Release/Listings/Objects，后者任意层级）整目录忽略 | master.py |
| 骨架 | AI 生成的 main.c（初始化序列 + TODO 预留区）+ 静态自检（幻觉调用改注释占位） | skeleton.py |
| 修改器 | 平台工程文件适配器：Keil 改 .uvprojx、CCS 改 .cproject；各自是格式读 + 写的唯一所有者；XML 解析 / 写回 / 头部回注共用 projectfile.py 底座 | keil.py / ccs.py / patchers.py / projectfile.py |
| 平台警告 | missing / unverified / hardware_bound，生成前暴露 | selection.py |

## 架构要点

- 薄壳（webapp 路由 / LLM 网络调用 / 文本抽取）包裹纯逻辑核心。
- 生成流程的接缝是 `generator.generate_project`（选模块 → 定位母版 → 生成 → 摘要；内部落盘步骤 `generate`）；母版库布局（masters_dir/<platform>）归母版模块（`master_project_dir`）。
- 不变量：任何校验失败都在落盘前发生，绝不产出残缺工程。
