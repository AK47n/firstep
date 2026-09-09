# 01 — 演示脚本确定性渲染（demo_script.py + generate 接线）

**要做什么：** 生成工程时，工程根自动落盘 `演示脚本.md`（README 先例，纯新增文件）：
按评分点逐条列出「操作 / 预期现象 / 对应功能需求与模块」的演示步骤表；评分点与功能
需求经题面句子编号桥接（score sentence_refs ↔ requirement sentence_index）；无评分点
降级为功能需求驱动，两者皆无按模块清单列验证演示项；尾部注明「请按实物调整」。纯
确定性渲染，零 LLM 调用；幂等（同输入两次调用逐字节一致，尾部单换行收尾）；缺省
数据下文件仍生成但内容自洽，不触碰任何既有生成文件。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-08-23） 实施完成 + code-review 双轴评审整改闭环；

## Comments

**实施记录（2026-08-23）：**
- 新模块 `demo_script.py`：render_demo_script 纯函数（评分点 / 需求 dict 直传 /
  manifests → 完整脚本文本），幂等 + 尾部单换行（README 先例）。
- 结构：头段（生成方式声明 + 演示前准备：编译烧录 / 接线 / 模块自检）→ 评分点
  分区组织（每评分点小节 = 操作 / 预期现象 / 对应功能需求 / 对应模块）→ 桥接
  不上的需求独立成条进「补充功能需求演示」节 → 尾部「请按实物调整」注明。
- 降级链：无评分点 = 功能需求驱动；两者皆无 = 模块清单验证演示（不空文件）。
- 桥接 = 需求.sentence ∈ 评分点.sentence_refs（同编号体系）；对应模块行带
  manifest 描述（能力方向，spec:29 逐字规定），库外 slug 只显 slug。
- 畸形需求防御（缺 requirement 键 / sentence 非整数（含 bool，int 子类）/
  编号非 1 起 → 跳过，不阻断渲染）。
- generate() 接线：README 之后写盘 演示脚本.md，数据 = score_points /
  requirements / manifests 既有参数，零新参数；写失败走既有 rmtree 兜底。
- 测试：tests/test_demo_script.py 10 项（纯函数分支 / 桥接 / 降级 / 防御 /
  流程落盘 / 幂等 / 缺省自洽）+ test_generator.py 落盘断言 + test_k230_artifact
  例外名单（随 manifest 集渲染，与 README/context 同类）；全量 2154 通过 +
  mypy 59 文件干净。

**评审整改（code-review 双轴）：**
- Spec：(a) 对应模块行补 manifest 描述（能力方向进文案，spec:29）；(b) 按
  spec:81-82 补 test_generator.py 落盘断言（缺省不写 + 有文本落盘 + 内容与
  渲染函数一致，换行归一化比对——写盘经平台换行转换，README 先例）；(c)
  _clean_requirement 排除 bool（int 子类，selection.py:419 同防御）+ 拒绝
  sentence < 1（编号 1 起）。
- Standards（判断项）：CleanRequirement dataclass 替代 tuple 位置索引
  （Data Clumps 整改）；readme 私有函数（_score_part_label 等）跨模块复用
  保持私有——spec:63「同包内共享」明确预告，mypy 不报；「演示步骤表」=
  小节清单（操作/预期现象/对应需求/模块四行）非 markdown 表格——长文本
  表格可读性差，条目结构满足 spec:25-26「每条 = 操作 + 预期现象 + 对应
  功能需求/模块」；「补充功能需求演示」保留未关联需求 = spec「关联不上
  独立成条不丢弃」精神延伸（漏演即丢分），评审标低风险，保留。

- [x] 新模块 demo_script.py：render_demo_script 纯函数（幂等、尾部单换行，参照 readme.render_readme 契约）
- [x] 评分点驱动：按 part 分组逐条操作/预期现象，sentence_refs 关联功能需求与模块
- [x] 降级分支：无评分点 = 功能需求驱动；两者皆无 = 模块清单验证演示项
- [x] generate() 接线：README 之后写盘 演示脚本.md，数据全来自既有参数（score_points / requirements / manifests），零新参数
- [x] tests/test_demo_script.py（纯函数：分支 / 幂等 / 降级）+ test_generator.py 落盘断言
- [x] 全量回归 + mypy 干净
