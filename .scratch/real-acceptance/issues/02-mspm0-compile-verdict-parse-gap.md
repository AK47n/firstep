# 01 — gmake/tiarmclang/SysConfig 报错解析缺口：编译失败被报成「0 错误 0 警」

**要做什么：** mspm0 线（CCS / gmake / tiarmclang / SysConfig）的编译输出解析补上
SysConfig 与 tiarmclang 的报错/汇总形态，让「编译失败」不再被 `parse_compile_errors`
+ `summarize_compile_output` 报成 `{errors: 0, warnings: 0}`。

**被谁阻塞：** 无。

**状态：** ready-for-agent

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

- [ ] 红证：把上面那段真机输出喂 `parse_compile_errors` / `summarize_compile_output`，
      现状 `{0,0}`（已有本站现场文本可直接用）；实施后 ≥7 errors / 0 warnings 且逐条带外设名
- [ ] 修复链不再把这 7 条当「未定位到可修复文件」喂 LLM（配置级冲突走专门分支）
- [ ] 全量 pytest 绿 + 结构测试钉住「SysConfig 段有解析」
- [ ] 真机复跑 2026H/mspm0：CLI 轮次文案与前端错误列表都能看到 7 条冲突

## 附：本轮同时观测到的相关事实（不属本单范围，供参考）

- 生成门禁（`run_generation_gates`）对这条 2026H 组合**全过**——引脚冲突是
  SysConfig 语义级（同一外设实例的 `associatedPins` 互斥），门禁现有检查面
  （include / 符号 / 宏 / 引脚角色）覆盖不到，属另一条待立项的缺口。
- 该工程的 makefile 集固定引用了 `C:\ti\ccs2051\sysconfig_1.26.2` +
  `C:\ti\ccs2051\mspm0_sdk_2_10_00_04`（探测取目录名排序最大），而编译器取自
  `ccs2050`——探针实测可编过（`.scratch/real-run/verify-16-A8-mspm0-min-servo.txt`），
  但「三件套可跨版本混搭」这一事实值得在环境体检文案里说明。
