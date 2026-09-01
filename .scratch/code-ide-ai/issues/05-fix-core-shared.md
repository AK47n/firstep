# 05 — fixLoop 状态机抽共享（去 DOM 化 + 事件回调广播）

**要做什么：** 二期（B 全配）第一步：ui/generate-fix.js 的修复循环状态机
（startFixCenter/continueFixCenter/fixRounds/fixLoop 域）抽为共享模块
（建议 ui/fix-center-core.js）：
- 核心只持有流程状态（running/round/batch/resume/结果缓存），SSE/端点
  调用不变，渲染改为**事件回调广播**：onState(statusText)、onErrors(list)、
  onRound(roundInfo)、onApply(item)、onDone(summary)、onTelemetry、onRollback
  ——generate-fix.js 绑定回调保持现有 DOM 渲染（第 10 步修复中心行为零变化）。
- 导出 startFixCenterCore(callbacks)/continueFixCenterCore(callbacks) +
  fixLoop 只读查询（isFixRunning()）。
- 生成页入口与写盘守卫/平台工具链校验路径不迁移（仍在 generate-fix.js 包
  一层薄壳——守卫在壳层，核心只管流程）。
- 回归要求：生成页修复中心（一键/继续/轮次条/回滚/降级模式/轮上限终态）
  行为与现状完全一致（smoke + 回归绿）。

**被谁阻塞：** 一期 01-04（避免并行冲突；流程上二期在一期后）。

**状态：** resolved

- [x] 验收 1：抽取后生成页修复中心 6 大场景回归一致（首编直通/有错轮修/
  告警轮/轮上限终态/继续批次/降级模式）。
- [x] 验收 2：新模块无 DOM 引用（纯流程 + 回调）；node 可测部分（若抽纯逻辑
  → 单测）。
- [x] 验收 3：全部既有冒烟/单元回归绿。

**结论：** 实现完成（双轴评审整改，见 spec.md「评审确认」段 s5）。要点与偏离：
- 新 ui/fix-center-core.js：无 DOM 流程核心（fixLoop 状态/lastFixDone 回喂/
  单次编译/单次修复/轮批 + SSE 调用 + 轮次与停滞/轮上限算法），渲染经 13 个
  事件回调广播（onState/onError/onRound/onApply/onLog/onBanner/onList/
  onTelemetry/onDone/onReset/onBusy/onResume/onCompiled——与 issue 列的
  onErrors(list) 语义分拆为 onError(text) + onList(parsed,fixes,round)）。
- generate-fix.js 变薄壳：校验（输出目录/平台/工具链）+ 写盘守卫 + aiAction/
  秒表 + 回调绑 DOM；导出面保持（startFixCenter/continueFixCenter/
  runCompileOnce/runFixOnce/fixRounds/renderToolchainStatus/
  updateFixCenterAvailability/toolchains/setToolchains/compileBanner +
  re-export FIX_MAX_ROUNDS/fixLoop 自核心——check_contract 3 结构钉重指向核心）。
- **偏离 1（onRollback）**：issue 字面列 onRollback——实现回滚全在壳层
  （confirmModal + /api/fix-errors/rollback + lastFix 登记，export 未变）；
  rollback 是壳层交互+API 调用、非状态机事件——可接受（记录）。
- **偏离 2（手动模式单实例）**：Standards 评审整改——runFixOnceCore 置
  running（原基线手动/自动可并发互相清空共享态；抽取后更显）；运行中触发
  抛「修复循环进行中」交壳层显示。
- **偏离 3（runFixOnceCore 清 resume/batch/lastFixDone）**：手动模式新生命
  周期语义（原壳层 btn-fix-errors 手动清理）——迁入核心。
- 判断项记录：Middle Man（*Core 转发壳——导出面保持有意）；Repeated Switches
  （compile/fix 两处 SSE type 链——基线同构）；Speculative Generality（*Core
  三件套 + 回调为工单 06 预留——issue 字面）；onApply 与 fixRenderResults
  重复建行（既有）；fixLoopSnapshot 现仅测试使用（06 将用）。
- 测试：tests/js/fix-center-core.test.mjs 10 用例（node 1070 全绿）；smoke-04
  等浏览器回归全 PASS。
