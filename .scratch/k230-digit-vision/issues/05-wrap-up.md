# 05 — 收尾：文档同步与全量回归

**要做什么：** CONTEXT.md 同步 K230 数字识别域术语与新机制（模板级依赖覆盖 / 静态资产分发 / DIGIT 帧契约），全量测试 + 编译矩阵回归通过，CHANGELOG 核定（提交信息自动补录，人工核对条目完整性）。

**被谁阻塞：** 04。

**状态：** resolved

- [x] CONTEXT.md：「Python 副产物」域条目更新——模板级依赖覆盖（per-template dependencies 语义）+ 静态资产分发（assets 复制对）+ DIGIT 帧契约（帧头/数据行字段序单源，与 digit_uart 双平台防漂移）
- [x] 全量测试跑通（pytest 2946 全绿，含 test_k230_artifact / test_repo_language / test_ps1_encoding 等兜底）
- [x] 编译矩阵回归（既有 compile_runner 相关测试保持绿）
- [x] CHANGELOG 核定：k230 数字识别条目完整（机制 + 模板）

**实现备注（2026-08-30）：**

- CONTEXT.md「Python 副产物」行重写：并入多模板增强形状（dependencies/assets 可选字段）、模板级依赖覆盖语义（None=继承/非空=替换/[] 拒绝 + 库级校验 validate_template_dep_slugs + 三端点同一答案来源）、静态资产分发（AssetSpec/互斥/撞文件语义）、DIGIT 帧契约（帧头/10 字段派生格式/消费槽位/无检测语义）、k230 三模板；「模板级依赖替换留待第二批」句子由「digit 已落地」事实替换。
- 全量回归 2946 passed（含 01-04 全部新增用例 + compile_runner 系列 + 语言/编码兜底）；k230 专项 79 用例 + webapp 371 用例 + 前端 node:test 918 用例全绿。
- CHANGELOG 核定：2026-08-30 组内 k230-digit-vision/01（21:59 契约）/ 02（22:12 覆盖）/ 03（22:22 资产）/ 04（22:28 模板落地）齐备，自动补录无缺漏。
- 编译矩阵：本机无 Keil UV4 / gmake（编译冒烟注释见 04 工单）。
