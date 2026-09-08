# 01 — 词表挂接补全：核心器件标注「库内已有」+ 内部件判据入测试

**要做什么：** 舵机、步进电机、OLED 屏、MPU6050、LED、蜂鸣器、声光组合、按键这些用户会单独采购的器件，在买件指引里标出「库内已有对应模块」；内部件（adc/delay/filter/uart/config/各 uart）明确不挂，且这个判据被测试守住。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 缺口器件模块补上带 `lib_modules` 的选购方案：`servo`、`step_motor`、`oled`、`ml_mpu6050`、`led`、`beep`、`led_beep`、`key` 八个 slug 至少各被一个方案引用。
- [x] 新方案与既有方案风格一致（名称是用户买得到的器件名、`recommended` 语义正确、`lib_modules` 只写库内真实 slug）。
- [x] 内部件不挂：`adc`、`delay`、`filter`、`uart`、`config`、`debug_uart`、`digit_uart`、`imu_uart`、`zigbee_uart`、`zigbee_uart_key`、`huidu`、`ntb_time` 不被任何选购方案引用。
- [x] 新增测试钉住上述两侧：器件类被挂接、内部件类不挂（新增器件入库时按判据归位）。
- [x] `wordlist.json` 加载仍通过（`lib_modules` 的 slug 存在性机械校验）。
- [x] 库审计 `[词表] 未被任何选购方案引用的模块` 从 20 个降到 ≤ 12 个（收窄量 = 本轮挂接的器件数）。
- [x] 既有词表 / 买件指引相关测试全绿。

## Comments

**改动**：`src/contest_generator/wordlist.json`（新增 5 条方案 + 1 条挂接扩充 + 2 处 models 补词）、`tests/test_wordlist.py`（新增 2 用例）。

| 器件 slug | 挂接方案（新增/扩充） | 所在组 |
|---|---|---|
| `led` | LED 指示灯（板载 / 外接）**新增** | 声光提示器件 |
| `beep` | 有源蜂鸣器模块（低电平触发）**新增** | 声光提示器件 |
| `led_beep` | LED + 蜂鸣器 声光组合套件**新增** | 声光提示器件 |
| `servo` | PCA9685 16 路舵机板（既有方案扩充 `lib_modules`，其 note 本就写明与 servo 互补） | 执行机构 |
| `step_motor` | 脉冲式步进电机 + 驱动板（细分可调）**新增**（models 补「步进电机」） | 执行机构 |
| `oled` | 0.96 寸 OLED 单色屏（SSD1306，I2C/SPI）**新增** | 显示模块 |
| `ml_mpu6050` | MPU6050 六轴姿态模块（GY-521）**新增**（models 已有 MPU6050） | 感知传感器 |
| `key` | 独立轻触按键模块（带上拉）**新增** | 感知传感器 |

「声光提示器件」组此前 `models` 有 LED/蜂鸣器但 `solutions` 为空——2026C「声光提示」类题面命中该行后一条挂接都带不出来，正是 backlog 5.3 点出的缺口。

**红证（先红后绿）**：把 `wordlist.json` 临时回退（`git stash push -- src/contest_generator/wordlist.json`）后跑新用例：

```
E  AssertionError: 器件类模块未被任何选购方案挂接：servo、step_motor、oled、ml_mpu6050、led、beep、led_beep、key
FAILED tests/test_wordlist.py::test_default_wordlist_device_modules_are_hooked
1 failed, 1 passed
```

恢复后 `tests/test_wordlist.py` 17 passed（内部件反向守卫用例在回退态也绿——它守的是「不挂」，与本次新增挂接无关）。

**审计收窄**：`python -X utf8 .scratch/library-audit/audit.py` 的 `[词表] 未被任何选购方案引用的模块` 从 **20 个降到 12 个**（剩余 12 个全是内部件：adc、config、debug_uart、delay、digit_uart、filter、huidu、imu_uart、ntb_time、uart、zigbee_uart、zigbee_uart_key）——正是本工单判据认可「不挂」的那批。

**判据落地方式**：测试里两份名单（`_DEVICE_SLUGS` / `_INTERNAL_SLUGS`）显式列出并带注释说明口径——器件 = 用户会单独采购的件，内部件 = 库内以头文件/工具形态存在的件。新器件入库时按此归位；两向都有守卫（该挂的没挂红、不该挂的挂了也红）。
