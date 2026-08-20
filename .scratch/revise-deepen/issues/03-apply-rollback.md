# 03 — 修订执行：备份 + 覆盖式重生成 + 回滚

**要做什么：** 用户确认影响分析与 diff 后，工具对目标输出目录整树备份到输出目录外（修复备份先例，带编号），然后覆盖式重生成进同一目录——复用既有生成全链路（门禁 / 模块复制 / 绑定写侧 / 多实例 / 副产物 / README / 构建脚本），并同步落新上下文清单。模块集变化时 main.c 由新骨架替换（旧版在备份里）；模块集不变时跳过重生成（main.c 原样保留）。执行结束给出 diff 记录（模块增删 + Q&A 原文 + 时间），可一键回滚（回滚 = 目录内容恢复为备份内容）。执行走 SSE 进度流（备份中 / 重生成中 / 完成）。

**被谁阻塞：** 02（拿确认后的模块集与影响记录）

**状态：** resolved（2026-08-21 实施完成 + code-review 双轴评审整改闭环）

## Comments

**实施记录（2026-08-21）：**
- 新模块 `revision.py`：backup_tree（整树备份到输出目录外 revise-backups/，
  带编号；空目录拒绝）/ restore_revision（清空 + 恢复备份内容，恢复前整树
  路径安全校验）/ run_revision 编排（备份 → 展开集判定变化 → 骨架重生成 →
  覆盖式重生成 → 上下文清单更新 → diff 记录）。
- main.c 保全策略落地：模块集变化 → 新骨架替换（旧版在备份）；不变 →
  不重生成、main.c 原样保留（手工编辑不丢），清单 main_c 现读磁盘。
- webapp POST /api/revise/apply（SSE：revision_backup → revision_generating
  → done diff 记录 + impacts 留痕）+ /api/revise/rollback（同步恢复）；
  mspm0 修订重生成透传 ccs_tools（构建脚本全链路复用）。
- events.py 加 revision_backup / revision_generating 词表；RevisionError 登记
  errors.py；测试 12 项（tests/test_revision.py）+ 全量 2105 绿 + mypy 干净。

**评审整改（code-review 双轴）：**
- Standards：impacts 确认载荷落实（done 留痕）；restore_revision 整树路径
  安全校验（对齐 fix_errors.restore_backup 先例）；diff 用依赖展开后的集合
  （与产物一致，确认集缺依赖不误报 removed——spec「模块集」语义 = 生成时
  有效集 = 展开后，Comments 留痕）。
- Spec：ccs_tools 透传（构建脚本全链路）；空目录拒绝；不变路径清单 main_c
  现读；topic_id 重生成保留；失败路径 SSE 中文文案测试。
- 决策留痕：修订骨架不注入参考全文（spec 未要求，模块接口已够）；score_points
  修订不恢复（清单只记生成输入，结果类字段不入清单——工单 01 决策）。

- [ ] 执行 API：确认载荷（模块集 + 影响记录）→ 备份 → 覆盖式重生成 → diff 记录，SSE 进度事件
- [ ] 备份：整树备份到输出目录外、带编号；回滚后目录内容与备份逐文件比对一致
- [ ] 模块集变化 → 新骨架替换 main.c（旧版在备份）；模块集不变 → 跳过重生成、main.c 原样保留
- [ ] 重生成后上下文清单同步更新（与执行时输入一致）
- [ ] 失败路径：备份成功但重生成失败 → 目录保持可回滚状态，报错中文
