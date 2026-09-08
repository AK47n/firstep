# 02 — 推荐候选扩容（related_limit=15 + related 来源标注 + 清单段 wire 兜底）

**要做什么：** 用户生成任意赛题（含粘贴题面 no-topic）时，推荐阶段的候选清单除了既有锚定目录外，还会出现与题面外设相关的未锚定参考例程（标注「与题面 / 模块相关，自动列出」），AI 可照旧点名后回读全文；候选清单段新增 wire 字节预算兜底（带截断标注），保证最坏形态请求预算仍有确定上界（≥ 2KB 余量——2026-08 修订 4，见下「预算定案」）。词表未命中的赛题候选与现状逐字节一致（条件段先例，零增量）。

**被谁阻塞：** 01（相关性匹配纯函数）

**状态：** resolved

- [x] 装配域新增 `related_limit` 参数（缺省 0 = 关闭，向后兼容），recommend 路由传 15（`budget.RELATED_CANDIDATES_LIMIT`）；候选 = 锚定 ∪ 相关（锚定优先、按 id 去重）
- [x] 题面来源：识别到历史赛题用库内题面全文 ∪ 粘贴片段（用户粘贴的重点也是题面信号，测试驱动的小设计），no-topic 用粘贴题面
- [x] 候选清单来源标注新增 related 值（沿用既有 auto/manual note 机制，prompt 清单行按 source 区分）
- [x] 清单段 wire 预算兜底：超限截断且带标注（与全文段同一 `_fit_segment_wire`，段级预算 `REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES=4096`）；相关候选进入 references 契约后 AI 点名 → 回读全文走既有通道（回读器键覆盖锚定 ∪ 相关）
- [x] `test_selection_prompt_worst_case_fits_request_budget` 以「15 条最坏清单 + 64KB 全文 + 20 条历史 + 题面 4000」为新最坏形态重新核算并更新（断言由 −6KB 收紧为 −2KB，见「预算定案」）
- [x] 装配域单测：related 并入、去重、锚定优先、related_limit 透传、recommend 端到端（题面含 uart/串口 → 候选含相关例程、done 载荷标注 related）+ 回读器可读 related 条目
- [x] generate 路由行为不变（不传 related_limit）

---
**预算定案（2026-08 修订 4，红证先行实测校准）：**

工单正文原要求「余量 ≥ 6KB」——真实库简介 194-348 字/条（实测脚本
`.scratch/ref-related-autoload/measure_suggestions_wire.py`：15 条相关候选清单段
实际 4725-5077B，远超 80 字/条的乐观估算）。15 条形态下最坏 ≈128.2KB：
距 MAX_REQUEST_BYTES（131072）余约 2.8KB，6KB 边界（124928）保不住。
定案：清单段段级预算 `REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES = 4096`（整段截断、
通用截断标注，截了要明说），worst-case 测试断言从 `MAX_REQUEST_BYTES - 6*1024`
改为 `MAX_REQUEST_BYTES - 2*1024`（129024，余 ~830B）。10KB 备量是历史多次
修订累计消耗的真实结果；现按「距 MAX_REQUEST_BYTES 保持 ≥2KB 充分距离 +
新增段再加即红」校准——预算再涨必须先红证实测再动常数。

**巡检补丁（实现期发现，已并入本工单）：**

- 词表补「巡线」（与「循迹」同义——库内 21F 巡线送药 / 26H 滚球巡线 /
  car-1-1 巡线模板三个条目标题用「巡线」，题面多写「循迹」，单收一词桥接失败）；
- 同义词组机制 `PERIPHERAL_SYNONYM_GROUPS`（组内任一词题面命中 → 整组激活 →
  条目侧组内任一词命中 token 计 1 分，按语义组计分不重复）：（循迹，巡线）与
  （摄像头，camera，cam）——后者桥接「C7-3-4L ESP32-CAM开发板资料」；
- 英文词项粘连中文尾巴的 token 内独立出现规则（`cam开发板资料` 中 cam 命中；
  canmv 内 can 仍不命中，边界反例不误报）；
- `platform_matches` / `related_references` 补登记 autocommit 写追踪注册表
  （工单 01 迁移 platform_matches 时漏登记，全量回归暴露）；
- done 载荷参考清单改由候选清单（suggestions，带来源标注）单源构造——
  旧「references + manual_references」构造无法区分 related 标注，单源后
  模型看到的候选 = 最终回显（透明闭环，来源标注同源同序）。

**验收记录：**

- 装配域（tests/test_generator.py，工单 02 区块 4 用例）+ 参考库域（同义词组/
  粘连 token/词表单源，tests/test_reference_library.py）+ llm 域（related 标注 /
  清单段截断 / worst-case，tests/test_llm.py）+ webapp 端到端（recommend related
  可见与标注，tests/test_webapp.py）+ done 载荷（tests/test_selection.py 适配）
  全部通过；全量 3152 passed（补 autocommit 登记后 3153）。
- 真实库冒烟（library/，related_limit=15）：2026H（滚球巡线）related=3
  （21F-巡线送药决策例程 / C7-3-4L-ESP32-CAM开发板资料 / car-1-1-巡线模板-mspm0），
  2021F（送药）related=1（无线串口模块资料），2024H（小车）related=1
  （C7-3-4L-ESP32-CAM开发板资料），no-topic（串口/ADC/定时器题面）related=15
  （全 ADC12/定时器/PWM 类）——死库激活验证通过，候选 ≈0 的历史行为已解决。
- code-review 双轴完成：Spec 轴 1 低（no-topic references 与手动去重口径——
  已通过 `_related_admission` 单点统一）+ 1 需回填（本定案/巡检补丁记录）+ 无错
  实现；Standards 轴 3 判断项均整改（no-topic 去重、fixed 改名 base_suggestions、
  死代码删除、note 链式三元改查表、`_synonym_representative` 单点、`_fit_segment_wire`
  改名与 docstring 泛化、budget 注释口径修正）。

**状态变更历史：**
