# 02 — gmake/tiarmclang/SysConfig 报错解析缺口：编译失败被报成「0 错误 0 警」

**要做什么：** mspm0 线（CCS / gmake / tiarmclang / SysConfig）的编译输出解析补上
SysConfig 与 tiarmclang 的报错/汇总形态，让「编译失败」不再被 `parse_compile_errors`
+ `summarize_compile_output` 报成 `{errors: 0, warnings: 0}`。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-17 第十七轮落地，见文末「实施记录」）

## 真机现场（2026-09-10 第十六轮，A 组 A8 实跑）

2026H / mspm0 生成工程真机 `gmake -C Debug -f makefile -B all` **exit=2**，
原始输出（`.scratch/real-run/verify-16-A8-mspm0-2026H-buildlog.txt`）：

```
error: DC_MOTOR(/ti/driverlib/GPIO) associatedPins[3].pin: Resource conflict
	PA7/49 is currently in use by SERVO_PWM(/ti/driverlib/PWM) peripheral.ccp0Pin
error: HUIDU(/ti/driverlib/GPIO) associatedPins[5].pin: Resource conflict
	PA27/31 is currently in use by L298N(/ti/driverlib/GPIO) associatedPins[0].pin
... （共 7 条 Resource conflict）
7 error(s), 0 warning(s)
gmake: *** [subdir_rules.mk:9: build-1290584808] Error 1
```

产品侧判读（实测，同一段文本喂两个产品函数）：

| 函数 | 结果 |
|---|---|
| `compile_passed("mspm0", 2)` | `False`（编译失败——**只有这一处是对的**） |
| `fix_errors.parse_compile_errors(text)` | `()` **0 条**（SysConfig 的 `error: NAME(path):` 形态无 `文件:行号`，两条正则都不吃） |
| `fix_errors.summarize_compile_output(text, ())` | `{"errors": 0, "warnings": 0}` —— **失败却报 0 错 0 警** |

现场连带后果（同一跑的真实行为）：

- CLI 修复轮回喂文案：「第 1/3 轮：**0 条 Warning** → AI 修复…」——错误数在轮次文案里
  直接消失（`run_fix_loop` 的 verdict 由 summary 派生）；
- `/api/fix-errors` 拿到不含文件引用的报错全文 → 「未定位到可修复文件（降级），修复未落盘」
  → 「本轮未应用任何修复，停止循环」——**用户看到的是「没找到能修的东西」，不是 7 条真实冲突**；
- 前端「修复中心」横幅四态里 fail 态会显示，但错误列表（`parsed_errors`）为空——
  用户拿不到任何可读原因。

## 根因

`fix_errors._UV4_ERROR_RE` / `_CCS_ERROR_RE` 都要求 `路径:行号` 形态；
`_UV4_SUMMARY_RE` 只认 UV4 的 `N Error(s), M Warning(s)`（大小写敏感）。
SysConfig 的两条真实形态都不匹配：

1. 行级：`error: NAME(/ti/driverlib/GPIO) associatedPins[N].pin: Resource conflict`
   ——无文件无行号（是**工程外设配置冲突**，不是源码报错）；
2. 汇总：`7 error(s), 0 warning(s)` ——全小写，与 UV4 汇总形态不同。

tiarmclang 的源码级报错形态（`path:line:col: error: ...`）已被 `_CCS_ERROR_RE` 覆盖
（本轮 stm32 线与早前 mspm0 单模块编译均验证过），缺口集中在 **SysConfig 段**。

## 修复方向（实施会话定措辞，红证先行）

1. `_UV4_SUMMARY_RE` 放宽大小写（`Error\(s\)` → 忽略大小写，或加 `error(s)/warning(s)`
   小写形态），并**优先于行级计数**——这样「7 error(s)」至少让 summary 说真话；
2. 新增 SysConfig 冲突行识别：`^error:\s*(?P<name>\S+)\((?P<periph>[^)]+)\)`
   → 产出「无文件引用」的条目（`path` 用伪路径或新增可选字段），让 UI / 修复提示
   能列出「DC_MOTOR × SERVO_PWM 抢 PA7」这类**人话冲突**；要点：这类冲突**不是
   LLM 能修的**（没有源码可改），修复链应识别为「配置级冲突」并给用户指路
   （改引脚绑定 / 去掉冲突模块），而不是喂给 `/api/fix-errors` 白烧一轮；
3. 契约与结构测试：`tests/test_fix_errors.py` 补 SysConfig 两形态用例 + 汇总大小写用例；
   `tests/test_generate_check_contract.py` 的 CLI 判读同源（同一份 parse/summary，不另写正则）。

## 验收标准

- [x] 红证：把上面那段真机输出喂 `parse_compile_errors` / `summarize_compile_output`，
      现状 `{0,0}`（已有本站现场文本可直接用）；实施后 ≥7 errors / 0 warnings 且逐条带外设名
- [x] 修复链不再把这 7 条当「未定位到可修复文件」喂 LLM（配置级冲突走专门分支）
- [x] 全量 pytest 绿 + 结构测试钉住「SysConfig 段有解析」
- [x] 真机复跑 2026H/mspm0：CLI 轮次文案与前端错误列表都能看到 7 条冲突

## 实施记录（2026-09-17 第十七轮）

**红证（实施前，真机日志 `verify-16-A8-mspm0-2026H-buildlog.txt`）**：
`parse_compile_errors` → `()` 0 条；`summarize_compile_output` → `{errors: 0, warnings: 0}`；
`compile_passed("mspm0", 2)` → False（只有这一处对）。三处缺口逐条对应工单「修复方向」。

**改动（解析域单源在 `fix_errors.py`，未另写平行正则）**：

1. `_UV4_SUMMARY_RE` 加 `re.IGNORECASE`——UV4 的 `N Error(s), M Warning(s)` 与
   gmake / SysConfig 真机全小写 `7 error(s), 0 warning(s)` 同判（`\d+\s+` 前缀
   要求保证不误命中行级 `error:` 行）；反馈折算仍以汇总行为准、行级为底。
2. 新增 SysConfig 冲突段识别 `_SYSCFG_CONFLICT_RE` + `_SYSCFG_OCCUPY_RE`：
   报错行 + 紧随的「被占用方」续行合成**一条**条目——`kind="syscfg_conflict"`、
   伪路径 `SYSCFG_CONFLICT_PATH="mspm0.syscfg"`、`line=0`，结构化明细
   `name / periph / field / pin / by / by_periph / conflict_count`；
   message = 人话（`DC_MOTOR 与 SERVO_PWM 抢 PA7（引脚）：资源冲突，引脚绑定需去重`）
   + 指路句 + 两行原文逐字（可追溯）。解析优先级：先配置级（形态更具体）再行级两类。
3. 修复链分流（`run_fix_round`）：报错全是配置级冲突且无源码候选 → **不调
   `llm.fix_compile_errors`**（不白烧一轮分钟级调用），done 载荷追加
   `syscfg_conflicts`（逐条明细）+ `notice`（人话指路，`SYSCFG_CONFLICT_NOTICE` 单源），
   `parsed` 里带 `kind`（前端据此渲染不可跳转的冲突行）。
   与前端同判据：`fx/code-compile.js isSyscfgConflict` / `ui/fix-center-core.js`
   首编即收口（`syscfgConflictsOf` + `syscfgConflictStateText`）——错误列表可见、
   状态行给准话、不进修复轮。
4. 载荷形状单源 `parsed_error_entries`：`/api/compile` 的 `parsed_errors`、
   修复轮 `parsed`、深化摘要的 `parsed_errors` 三处共用（源码级仍恰三字段，
   配置级多一个 `kind`——旧前端 / 旧契约零改动）。
5. CLI 验收脚本（`.scratch/real-run/generate_check.py`）**调 LLM 之前**判冲突：
   逐条列出 + 指路 + 「未应用任何修复（配置级冲突无源码可改），停止循环」，
   替掉误导的「未定位到可修复文件（降级）」。

**红→绿**：`tests/test_fix_errors.py` 新增 8 例（真机日志端到端 7 条 / 汇总 7,0 /
人话 message 三条事实 / 合成形态 / 小写汇总 / `syscfg_conflicts` 两路同源 /
`run_fix_round` 短路 0 次 LLM 调用 + 载荷形状 / 无冲突零回归）；
`tests/test_generate_check_contract.py` 新增 2 例（`gmake_build` 摘要「7 错误 0 警」、
`run_fix_loop` 配置冲突不喂 `/api/fix-errors`）；
`tests/js/code-compile.test.mjs` 新增 4 例、`tests/js/fix-center-core.test.mjs`
新增 2 例（前端渲染 + 首编收口）。

**真机结果**（`.scratch/real-run/verify-17-A8-mspm0-2026H-verdict.txt`）：
`[真机] ✗ gmake exit=2（7 错误 0 警）` → `第 1/3 轮：7 条 Error 0 条 Warning`
→ 7 条冲突逐条人话列出 → 指路 → 停止循环（**0 次 LLM 调用**，不再白烧额度）。
编译仍 exit=2：7 条冲突是工程真实的外设引脚互斥，属**另立缺口**（见下方「附」），
本单只负责判读如实。

**基线**：全量 `pytest` 3941 passed（原 3935 + 新增 6）；`node --test tests/js/*.test.mjs`
1429 passed（原 1422 + 新增 7）。另有 2 例 `test_tracker_audit_status.py` 因本单 00
缺状态行而红，已补状态行修复（见下）。
**顺手修复**（零行为变更）：`fix_errors` 模块 docstring 未加 `r` 前缀导致
`\m` 转义告警；`.scratch/real-acceptance/issues/00-待修清单-新会话入口.md`
补标准状态行（tracker 全库不变量要求）。

## 双轴评审与整改（2026-09-17，code-review：Standards + Spec 两轴并行）

**Spec 轴**指出三处「分流只做了一半」，逐条整改：

1. **判据分叉**（原：CLI `if conflicts` vs 域层 `conflicts and not candidates`）
   → 抽出判据单源 `should_skip_llm_fix(source_candidates, conflicts)`，域层
   `run_fix_round` 与 CLI `run_fix_loop` 共用同一函数（`fix_errors.py` 定义，
   CLI 导入调用），并有直测 `test_should_skip_llm_fix_predicate_shared_by_domain_and_cli`。
   **取舍记录**：并存「源码错 + 配置冲突」时**不短路**（LLM 修得动的是源码错，
   冲突条目照常带出）——新增用例
   `test_run_fix_round_mixed_source_error_and_conflict_still_fixes_source` 钉住。
2. **手动贴文本路径文案与行为不符**（域层不调 LLM，前端却报「AI 修复中」/
   「降级模式」）→ `parse_done` 事件新增 `conflicts` 字段（`ProgressEvent`），
   前端在本阶段即判 `isSyscfgConflict` 并改报冲突 + 指路；新增 JS 用例
   「手动贴文本路径遇配置级冲突：parse_done 就报冲突指路，不显示「AI 修复中」」。
   同时补上 Spec 指出的「`notice` 没人读」：状态行文案与后端
   `SYSCFG_CONFLICT_NOTICE` 刻意同文（跨语言对偶，注释与测试双侧钉住）。
3. **`conflict_count` 恒为 1（名字说谎）+ `elif pin:` 死分支 + 载荷字段无消费方**
   → 删 `conflict_count`；`if occupied is not None / else` 两分支取代死分支；
   `syscfg_conflicts` 载荷只留 `name / pin / by / message`（消费方真用的四字段），
   `periph / field` 留在 `CompileError` 解析明细。

**Standards 轴**指出的硬违规同样整改：工单 H1 编号 `01` → `02`（与文件名一致）；
`deepen._error_entries` docstring 参照物写错（说「与 `_parse_errors` 同款」但两者
导入源不同）→ 改为如实说明「本模块对 fix_errors 一律延迟导入」；
`SYSCFG_CONFLICT_NOTICE` 原注释自称「前端共用」与事实不符（前端读不到后端常量）
→ 改成与 `TRUNCATION_NOTICE` 同款的对偶说明；`syscfg_conflicts` 两个分支的
重复过滤表达式收敛到 `_is_syscfg_conflict` 单源；`ui/fix-center-core.js` 的
`syscfgConflictsOf` 中间人删除（调用点直接用单源判据 `isSyscfgConflict`）；
模块 docstring 补配置级判读契约段。

**未采纳的评审意见（附理由）**：`periph / by_periph / field` 三个结构化字段与
`SYSCFG_CONFLICT_PATH` 伪路径、前端 `.fix-tag.conflict` 样式保留——前者是验收
标准「逐条带外设名」的机器可读承载（Spec 轴归入「合理承载的范围蔓延」），
后者是「前端错误列表能看到 7 条冲突」的必要渲染分支。
另 Spec 轴提到 `node --test tests/js/` 目录形态 exit 1——本仓文档口径一直是
显式 glob（`node --test tests/js/*.test.mjs`，CLAUDE.md / 本轮提示词同款），
非回归，不改。

整改后复跑：pytest **3941 passed**、node **1429 passed**、真机
2026H/mspm0 输出不变（仍如实报 7 条 + 指路 + 停止循环，0 次 LLM 调用）。

## 附：本轮同时观测到的相关事实（不属本单范围，供参考）

- 生成门禁（`run_generation_gates`）对这条 2026H 组合**全过**——引脚冲突是
  SysConfig 语义级（同一外设实例的 `associatedPins` 互斥），门禁现有检查面
  （include / 符号 / 宏 / 引脚角色）覆盖不到，属另一条待立项的缺口。
- 该工程的 makefile 集固定引用了 `C:\ti\ccs2051\sysconfig_1.26.2` +
  `C:\ti\ccs2051\mspm0_sdk_2_10_00_04`（探测取目录名排序最大），而编译器取自
  `ccs2050`——探针实测可编过（`.scratch/real-run/verify-16-A8-mspm0-min-servo.txt`），
  但「三件套可跨版本混搭」这一事实值得在环境体检文案里说明。
