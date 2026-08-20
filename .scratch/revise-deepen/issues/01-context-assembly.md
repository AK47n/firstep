# 01 — 上下文装配：清单落盘 + 读侧 + 历史目录反推 + 加载 API

**要做什么：** 生成任何工程时，输出目录根多出一份隐藏上下文清单（纯新增文件，README.md 先例，不触碰任何既有生成文件、不影响 Keil/CCS 编译、缺省路径输出与现状逐字节一致），完整记录本次生成的输入（题面、平台、所选模块 slugs、引脚绑定、多实例清单、Python 副产物模板选择、Q&A 原文、功能需求清单、参考条目、生成时间、工具版本）。新增加载 API：给一个输出目录，返回可修订的上下文——有上下文清单直接读；没有清单（历史工程）自动反推：工程配置文件认平台、工程内模块文件反查库内 slug（歧义/找不到要求用户手动勾选，不猜测）、引脚配置回读成绑定载荷、main.c 现读；题面反推不了时明确提示用户补（粘贴或选题号）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved（2026-08-21 实施完成 + code-review 双轴评审整改闭环）

## Comments

**实施记录（2026-08-21）：**
- 新模块 `context_manifest.py`：写侧（build_context_fields / write_context_manifest，
  工程根 `.contest_context.json` 纯新增隐藏文件，README 先例）、读侧
  （read_context_fields 缺字段/旧版本兼容，坏 JSON → ContextError 400）、反推
  （infer_context：平台 = 工程配置文件后缀识别；模块 = modules/<slug>/ 目录名；
  绑定 = stm32 pin_config.h 宏现值写侧逆运算 / mspm0 syscfg $assign 落点值；
  main.c 现读）、形状校验（validate_context_fields：平台词表 / slugs 库内存在
  性 / 绑定键形状 → 400 中文）。
- generate / generate_project 尾部写清单（缺省路径既有文件逐字节不变）；webapp
  /api/generate 接收 requirements / qa_text / references / problem_text /
  topic_id 落盘；前端生成请求回传推荐产物摘要（requirements）与 Q&A。
- 新增 /api/revise/context：有清单直读（main.c 现读磁盘覆盖快照，手工编辑不丢）、
  无清单自动反推；missing 列表 = problem_text / requirements / main_c / slugs
  （前端提示补）。ContextError 登记 errors.py。
- 测试 20 项（tests/test_context_manifest.py）+ 全量 2072 绿 + mypy 54 文件干净。

**评审整改（code-review 双轴）：**
- Standards：测试补 docstring；_match_stm32_pin 异常收窄 PinBindingError；
  母版文件逐字节保留断言（验收 1 直接证据）。
- Spec：清单去掉 score_points（生成结果类字段不入清单）；main_c 统一现读；
  missing 补 slugs（空模块集 → 手动勾选兜底入口）。
- 已知边界（spec「尽力而为」语义）：内嵌母版模块（files 空）在产物树无
  modules/<slug>/ 目录，反推不到 → 前端手动勾选兜底（05 工单 UI 承载）。

- [x] 生成尾部写上下文清单（纯新增文件），缺省生成路径输出与现状逐字节一致（既有逐字节断言先例跑绿）
- [x] 读侧对缺字段 / 旧版本清单向后兼容（缺字段 = 走反推或要求补，不崩）
- [x] 加载 API：有清单直读；无清单自动反推平台/模块/绑定/main.c；歧义模块报错并支持手动勾选兜底；题面缺失明确提示
- [x] 功能需求清单随生成请求回传并落盘（推荐产物摘要，供深化工单消费）
- [x] 加载 API 的上下文形状校验：平台词表 / slugs 存在性 / 绑定形状，非法输入 400 中文
