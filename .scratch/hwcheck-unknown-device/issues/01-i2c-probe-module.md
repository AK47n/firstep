# 01 — 库内新增总线原语模块 `i2c_probe`（两平台）

**要做什么：** 模块库里多出一件「通用 I2C 总线原语」模块 —— 纯 ping 一个 7 位地址、读一个 8 位寄存器，**不含任何器件语义**。它是后面「陌生器件探测」的支点：mspm0 上 `main.c` 只准调「所选模块头里真实存在的函数」，探测代码只能经由它进工程；两平台各自真编译通过，选中它生成的工程里自然出现那一对脚与接线行。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] `library/modules/i2c_probe/` 有 manifest + 两平台实现；`GET /api/modules` 能看到它，身份判据按**内部件**（不做 kit / source_url 要求）
- [x] 接口只有三件事：初始化、ping 一个 7 位地址（返回通/不通）、读一个 8 位寄存器地址取回一个字节（失败有明确返回值，不与"读到的 0x00"混淆）；头里没有第二类语义
- [x] stm32 实现 = **位操作软 I2C 自实现**（照 aht10 / sht20 先例，**不用**母版 `ml_i2c`），引脚走自己那组宏、默认 **PA6/PA7**；母版 `pin_config.h` 加对应的一组宏（与库内六件软 I2C 共挂同一条总线）
- [x] mspm0 实现 = `I2C_0_INST` + SDK `DL_I2C_*`（照 `ml_mpu6050` 的 `mpu_port.c` 先例）；`syscfg_instances` 里把 `i2c_probe` 登记为 `I2C_0` 的消费模块，选中它时该实例**不被裁剪**、PA0/PA1 的 `$assign` 存活
- [x] manifest 如实声明两平台引脚（stm32 带宏、mspm0 走 SysConfig 不带宏），因此选中它生成的工程里接线表与 README 有这两根线（页面与工程同源这条不变量不破）
- [x] 两平台各真编译一次 **0 error / 0 warning**（stm32 走 UV4、mspm0 走 gmake，用仓库既有编译口径）
- [x] 库内既有不变量全绿：身份字段判据、参考关联映射或显式豁免、默认布局共享白名单（与六件软 I2C 共挂 PA6/PA7）、来源与版面守卫
- [x] 平台已知代价写进模块说明与检测页可见处：mspm0 的 PA0/PA1 **与板载 LED 共用**（通信期间 LED 微闪）、PA0 的板载上拉位未焊（依赖模块板自带）
- [x] 反证：把「`I2C_0` 消费者登记」那一行拿掉，mspm0 选中本模块时 `I2C_0` 确实被裁掉（读数记进本工单）

---

## 结论（2026-09-22，工单 01 已 resolved）

### 交付物

| 落点 | 是什么 |
|---|---|
| `library/modules/i2c_probe/manifest.json` | 两平台条目：stm32 = `I2C_PROBE_SCL/SDA`（PA6/PA7 + 逐脚端口宏）、mspm0 = `I2C_0_SCL/SDA`（PA1/PA0，走 SysConfig 不带宏）；内部件、`kit`/`source_url` 为空 |
| `…/code/i2c_probe.c` + `.h` | mspm0：硬件 I2C（`I2C_0_INST` + `DL_I2C_*`）；`DL_*` 全部封在 `.c` 里（母版一个 `.h` 都没有） |
| `…/code/i2c_probe_stm32.c` + `.h` | stm32：位操作软 I2C 自实现（照 aht10/qmc5883l），不用母版 `ml_i2c` |
| `library/masters/stm32/pin_config.h` | 新增 `I2C_PROBE_SCL/SDA_GPIO/_PIN` 四个宏，默认 PA6/PA7 |
| `src/contest_generator/syscfg_instances.py` | `INSTANCE_CONSUMERS["I2C_0"]` 新增 `"i2c_probe"` |
| `src/contest_generator/library.py` | `MODULE_KIND` 登记内部件 + `MODULE_KIND_REASONS` 写明理由 |
| `src/contest_generator/reference_library.py` | `MODULE_REFERENCE_EXEMPT` 显式豁免（理由以「内部件」开头） |
| `tests/test_default_layout.py` / `tests/test_mspm0_default_layout.py` / `tests/test_pins.py` | 两平台默认布局共享白名单 + mspm0 默认脚映射登记 |
| `tests/test_module_i2c_probe.py` | 19 条契约（接口三件事 / 只读出参两分 / 内部件身份 / 两平台生成 / 代码守卫 / ping 同向 / 检测页注记 / I2C_0 存活与裁剪） |

### 验收读数（反证项 9 要的读数就在这儿）

真编译矩阵（`python .scratch/hwcheck-unknown-device/compile_matrix.py`，原始日志
`.scratch/hwcheck-unknown-device/matrix-logs/i2c_probe-{mspm0,stm32}.log`）：

```
[i2c_probe/mspm0] exit=0 passed=True warnings=0     ← SysConfig CLI + gmake（tiarmclang 4.0.4.LTS）
[i2c_probe/stm32] exit=0 passed=True warnings=0     ← Keil UV4：0 Error(s), 0 Warning(s).
```

`I2C_0` 端到端活着的落点证据：落盘 `mspm0.syscfg` 有
`I2C_0.peripheral.sdaPin.$assign = "PA0";` 与 `sclPin = "PA1";`，SysConfig CLI 生成的
`Debug/ti_msp_dl_config.h` 里有 `#define I2C_0_INST I2C0`——**没有它 `i2c_probe.c` 根本编不过**，
所以「编译 0 错」本身就是这条链的判据。stm32 侧 `uvprojx` 真收编
`i2c_probe_stm32.c`（不是只落盘不编译）。

**反证读数**（`python .scratch/hwcheck-unknown-device/probe-01-c1-reverse.py`，
读数 `.scratch/hwcheck-unknown-device/probe-01-c1-reverse.txt`）——把
`INSTANCE_CONSUMERS["I2C_0"]` 里那一行登记拿掉、逐字节复原后复核 sha256 相等：

```
[2] 注入前（登记在）：  SURVIVES I2C_0.$name / sdaPin="PA0" / sclPin="PA1"
[4] 注入后（登记没了）：PRUNED   I2C_0.$name / sdaPin="PA0" / sclPin="PA1"
[5] 复原复核：sha256 与原文相等（e5cd1236c2eda86fdcdb1f399b88b5f6…）
[6] 复原后复跑：        SURVIVES 三条全回来
```

→ **登记行是 `I2C_0` 存活的唯一判据**：不登记 = 选中本模块时 `I2C_0_INST` 不存在 =
`i2c_probe.c` 编不过。验收项 9 成立。

测试面：`tests/test_module_i2c_probe.py` **19 passed**；全量 `python -m pytest -n auto -q`
**5101 passed + 1 skipped**；前端门禁 `node --test "tests/js/*.test.mjs"` **1702 passed / 0 fail**。

### 两处实现口径（实施时定的，后面三张工单要用到）

1. **ping 的线上字节：两平台刻意同向**。都是「START + 器件地址 + **读位** + 读 1 字节
   （丢弃）」，问的是「这个地址的**读方向**有没有东西应答」。第一版是 mspm0 读位 / stm32 写位
   ——评审指出：只应答写地址的从机会在 mspm0 说通、在 stm32 说不通，而 ping 的判定直接写进
   学生看到的结论（「器件没应答」vs「应答了但寄存器不对」）。改同向后两平台口径一致；
   **代价如实记在 manifest notes**：这类从机（罕见）两平台都判无应答，要更进一步用
   `read_reg` 走一整条读写事务。mspm0 侧不用 0 长度突发（SDK 虽写长度范围含 `0x00`，
   但没有用法先例，赌不起——ping 静默永远无应答 = 把「线/供电没接好」误报成真相）。
2. **读寄存器 = 重复起始**（mspm0 `STOP_DISABLE` 后接第二段；stm32 两次 START 一个 STOP）。
   这是与 `mpu_port.c`「两段各自带停止条件」**刻意偏离**的一处——停止条件会让一部分器件复位
   寄存器指针、读回错值，而本件面对的恰恰是不认识的器件。偏离理由写在 manifest notes 与两份
   头文件里。

### code-review 两轴结论与整改

- **Standards 轴**：无硬违规的代码本体；**3 条「文件自述与行为不符」**已全部修
  （`compile_matrix.py` docstring 的日志目录、`probe-01-c1-reverse.py` docstring 的读数文件名、
  `verify-01-readings.txt` 里指向 `matrix/` 的日志路径——三条都是改路径时漏改文档）。
  1 条坏味道已提取（mspm0 的 RX-FIFO 等待原本在 `ping` 与 `read_reg` 里近乎逐字重复 →
  收成 `i2c_probe_receive_byte` 单点）。另：矩阵脚本第一版把工具汇总行 `0 Warning(s)`
  数成了 1 条告警，过滤规则已修，重跑读数两平台 `warnings=0`。
- **Spec 轴**：9 个验收项逐条判定——整改前 7 满足 / 项 8 部分 / 项 9 程序上部分；
  三条整改后全满足：① 读数与反证写进本工单正文（本节）＋复选框勾上；② 补一条判据把
  「检测页可见处」从「恰好有基础设施」钉成事实（`hwcheck_board_view` 上 PA0/PA1 的
  `pin_note` 与 `board_shares` 逐条断言）；③ 两平台 ping 同向（见上「实现口径 1」），
  并把这条同向本身也判据化（改回写位即红）。
- 评审同时更正了一处先例误述：mspm0 notes 原写「照 mpu_port.c 先例……`ADDR_ACK` 判地址应答」，
  实际 `mpu_port.c` 从不读 `ADDR_ACK`（只看 `ERROR`）——已改成如实分工：轮询/timeout 部分是
  先例，`ADDR_ACK`+`ERROR` 双位判据是本件按 SDK 文档新写的。

### 范围外 / 留给后面的工单

- 本件**只**提供总线原语，不进检测页的渲染链路：探测小节怎么渲染、`hwcheck_recipes.json`
  给不给它配方、串口命令台怎么分配字符——都是 03/04/06 的事。
- **未上板**：编译矩阵只证「能编译」，不证器件真能应答（真机口径见 spec：没跑过就写未上板）。
  真机若出现偶发误判，先核对 mspm0 的起始沉降 `I2C_PROBE_SETTLE_LOOPS` 与 stm32 的半周期
  `I2C_PROBE_HALF_PERIOD_US`（两处都是单点可调）。
