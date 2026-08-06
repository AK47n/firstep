# 08 — 真实运行验证：确认入库裸 500 / 坏 uvprojx 母版照样入库 / 413 预算政策统一

**What to build:** 用真实应用（main，8000 端口）+ Playwright 真实浏览器点击复验完整流程（扫描 → AI 提炼 → 确认入库）后的三个修复。主路径全绿（63+64 文件、12.7 分钟提炼、浏览器真实点击"确认并入库"成功），但暴露两个问题：

1. **确认入库裸 500**（已复现）：AI 整合出截断的 .uvprojx 时，`masters_confirm` 只捕获 MasterError，`rewrite_project_references` 抛的 KeilProjectError 与落盘阶段 OSError 裸传 → FastAPI 默认 500 无中文 message；前端 catch 不清 confirm-status，"落盘与入库中"残留成假象。修复 568cf51：webapp 错误映射补 KeilProjectError/CcsProjectError/OSError → 400 带中文；confirm 与 generate 端点补捕获；前端状态清理；回归测试（raise_server_exceptions=False 捕获真实 500 语义）。
2. **坏 uvprojx 母版照样入库**（判例 09）：AI 把两工程各自的 .uvprojx 判了 merge，整合产物 XML 合法但组被清空（丢了启动文件、system_stm32f10x.c 的引用）、连 Cads/IncludePath 节点都没了；模板 main.c 需要的 stm32f10x_conf.h 两个原工程都没有。流程只校验 XML 合法与配置文件存在，不校验"保留文件进了工程树 / 配置节点齐全"，坏母版照样入库——到生成时 KeilPatcher 才拒绝。修复：`analyze_structure` 对 stm32 接入 `keil.validate_project_structure` 三层校验（XML 合法 / Targets+ Cads/IncludePath 节点齐全 / 工程内全部 .c/.s 都在工程树有引用），失败在入库前 400 带中文拒绝，不留痕迹。
3. **413 预算政策统一**：worktree-fix-413-body-too-large / worktree-413-budget-policy（6fa12fe/d80399d）基在 ticket 07，与 ticket 08 已在 main 的补问/逐文件营救机制正面冲突——naive 合并会回退实测跑通的机制。统一后：TRUNCATION_NOTICE 截断标注单源（双端契约测试）、所有嵌内容调用走 _truncate_content（上限取实测过的 4000）、_judgment_batches 双重约束分批（字符预算 24000 防网关 413 + 文件数上限 25 防模型批量超载、单文件多版本超预算按版本拆批）、_chat 发送前序列化体积断言兜底（未截断长输入发出前大声失败而非等网关 413）。

**Blocked by:** 无

**Status:** resolved

## Answer

- [x] 568cf51 合入 main（500 已复现，回归测试在 webapp 端点层）
- [x] 413 统一（llm.py 保留 ticket 08 补问机制 + 413 预算政策三层），10 个新测试
- [x] uvprojx 结构校验：红测试先行（坏整合产物今天成功入库 → 修复后 confirm_distillation 大声拒绝），keil 层 4 个单测 + master/webapp 层适配
- [x] 假工程 fixture 补真实工程树（Groups/Files 引用各自源码，B 含独有文件）；顺手修 keil.py / test_master.py 文档串无效转义 SyntaxWarning（Python 3.14 报警）
- [x] 全套测试绿（403），mypy 干净
- [ ] 8000 端口服务需重启加载新代码
- [ ] 待定：uvprojx merge 策略是否改"选一份"（结构校验是安全网，不治本——AI 手写 XML 配置仍有失败率；真实超长冲突工程的 merge 截断盲区未验证，ADR 0001 已记录已知风险）
