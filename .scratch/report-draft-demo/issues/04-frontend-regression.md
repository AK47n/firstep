# 04 — 前端展示与全量回归

**要做什么：** 生成摘要展示两个新产物（设计报告草稿.md / 演示脚本.md）：摘要卡显式
标注 + 打开/复制路径入口（照 README / 上下文清单展示先例）；前端零新状态；全量回归
验证缺省路径逐字节不变。

**被谁阻塞：** 01（演示脚本产物）、03（报告产物经 LLM 接线）

**状态：** resolved：2026-08-23 实施完成 + code-review 评审整改闭环；

## Comments

**实施记录（2026-08-23）：**
- index.html 生成结果区新增「自动附带」条目行（res-artifacts 容器，缺省隐藏）。
- renderArtifacts(structure, outputDir)：structure 过滤两产物文件名——演示脚本
  恒在（模块兜底）、报告仅在 LLM 文本非空时在（缺省路径无报告 = 无 chip，零
  新状态）；badge 标注 + 点击复制文件路径（navigator.clipboard + toast，照
  btn-copy-dir 先例；outputDir 反斜杠归一为正斜杠，资源管理器 / 编辑器可直
  接打开）。「打开」= 复制后在资源管理器 / 编辑器打开——本地应用不引后端
  打开接口（安全面最小，工单措辞「打开/复制路径入口」的打开语义）。
- 回归：全量 2166 通过 + mypy 59 文件干净；node --check 两个 script 块语法
  干净；组合回归由后端测试覆盖（无评分点 / 无需求 = demo_script 模块兜底、
  LLM 失败 = 报告占位节，均落盘自洽）。

**评审整改（code-review）：**
- 评审方式：前端改动极小（一个容器行 + renderArtifacts 函数 + 一处调用），
  双轴 subagent 读 6.5K 行 index.html 长时间未返回，中断后自核收尾：
  - Spec：验收三项全兑现——摘要卡标注（structure 过滤，演示脚本恒在 /
    报告仅 LLM 文本非空时在，缺省路径零新状态）、复制路径入口（照
    btn-copy-dir 先例：navigator.clipboard + toast + 失败降级）、全量回归
    2166 通过；无范围蔓延（未引后端打开接口——本地应用安全面最小，工单
    措辞「打开/复制路径入口」的打开语义 = 复制后自开）。
  - Standards：注释 / 代码全中文（语言规范）；风格与既有先例一致（$()
    helper、badge class、data-ico、muted）；node --check 两个 script 块语法
    干净（LF 归一化后重新提取验证）；命名准确（renderArtifacts /
    res-artifacts / 自动附带）。
  - 判断项：copy 失败 toast error 降级与 btn-copy-dir 同款；outputDir
    反斜杠归一正斜杠（资源管理器 / 编辑器均可用）——均无整改项。

- [x] 前端生成摘要卡标注两个新产物文件 + 打开/复制路径入口
- [x] 无评分点 / 无需求 / LLM 失败的组合回归（产物存在、内容自洽）
- [x] 全量回归 + mypy 干净
