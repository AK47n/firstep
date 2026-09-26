# 10 — mspm0 生成用例断言 `Debug/makefile`，而那一步要 CCS 工具链（CI 上没有）

**要做什么：** 让 `tests/test_my_devices_endpoint.py::test_generate_on_mspm0_keeps_the_i2c_instance_alive`
里那条 `Debug/makefile` 判据**认清自己的前提**（要 CCS 三件套才摆得出来），
缺工具链时**显式 skip 并写明原因**——同时**不许**把这条用例真正要守的那几条判据
（自建件小节进 main.c / `i2c_probe.h` 而不是 SDK 头 / 母版 `I2C_0` 的 `$assign` 活下来）一起丢掉。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 定性：读 `generation` 那条路，确认 `Debug/makefile` 是**工具链那一步**摆的
      （`ccs_tools` 为 None 时不产出、只出 `build_hint`，与 `/api/hwcheck/generate` 的
      docstring 一致）。也就是说这条断言在**没有 CCS 的机器上从来不成立**——本机装了 CCS，
      所以一直看不见（与工单 08 同族的"本机替 CI 兜底"）。
- [x] 改法：那条断言按"工具链在不在"分流，缺了就**显式 skip 并说明本机怎么补**
      （判据口径与工单 08 的编译用例一致：skip 在摘要里看得见，不静默变绿）；
      **前面那几条与工具链无关的判据一条都不许少**——它们才是这条用例的本体。
- [x] 反向验证：本机（有 CCS）该用例仍真跑真断言；把 `ccs_*` 指到不存在的路径后
      得到的读数要如实记进 Comments（skip 发生在哪一步、跑了哪几条判据）。
- [x] 中文提交

### 收口读数（2026-09-26，本机）

判据单源：用**产品自己那个函数**问"本机有没有 CCS"（`find_ccs_tools("", "", "")`，
与夹具的空 `ccs_*` ⇒ 自动探测同一条路），不另写一份猜测。

| 状态 | 读数 |
|---|---|
| 基线（本机装着 CCS：`CcsTools(sdk_dir=…/ccs2051/…, compiler_dir=…/ccs2050/…, sysconfig_cli=…/sysconfig_1.26.2/sysconfig_cli.bat)`） | `1 passed`——真跑真断言（`Debug/makefile` 在） |
| 注入"本机没装 CCS"（把 `compile_runner._CCS_SCAN_ROOT` 临时指到不存在的目录） | **`1 skipped, 0 failed`**，skip 原因里点名缺哪三件、怎么补 |
| 复原 | 逐字节复原 **OK**（sha256 `00b4c2f8…` 前后一致） |

读数与探针：`.scratch/ci-gate-fixes/probe-10-skip-path.py` / `probe-10-skip-path.txt`。


## Comments

### 现场（2026-09-26，CI run `36216009452` 的 `全套 pytest（windows-latest）` job）

```
FAILED tests/test_my_devices_endpoint.py::test_generate_on_mspm0_keeps_the_i2c_instance_alive
E  AssertionError: 编译链入口（Debug/makefile）要摆好，否则这一份工程在检测页点不动「编译」
tests/test_my_devices_endpoint.py:616: AssertionError
1 failed, 5530 passed, 25 skipped, 29 warnings in 282.91s
```

**这条是"上一道门修好之后才露出来的"**：此前 pytest job 在**前端门禁**那一步就拒了
（工单 07 修的就是它），后面那步 `全套测试` 一直被 skip——所以这条在 CI 上**从来没跑过**。
07 修好之后它第一次真跑，当场红。这正是 spec 里那条教训的又一次复现：
**新加一道门之后必须真推一次让它跑起来；「门存在」与「门生效」是两件事。**

**旁证（本机与 CI 的跳过数不一样）**：本机 `5545 passed + 11 skipped`、CI
`5530 passed + 25 skipped`——差出来的那些 skip 就是各用例自己按"本机有什么"分流的结果。
这条用例没分流，于是红。
