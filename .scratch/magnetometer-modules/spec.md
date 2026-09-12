# 磁力计模块双件（HMC5883L / QMC5883L）— firstep 正式模块入库

## 问题陈述

做题用户在「电子罗盘 / 航向角」类需求（定向跟随、航向保持、找北、磁偏角、与 UWB/AOA 配合的绝对朝向）上，库内**没有任何磁力计模块**——AI 选型时只能回「需自备」。

同时，仓库里已经躺着一份**有硬伤的实现**：`ml_hmc5883l.c/.h` 在 `sources/contest/2021F`、`2026H`、桌面 `stm32base` 三处**逐字节相同**（sha256 前 12 位 `52537c752973`），但它从未被登记为模块（`library/modules/` 下无 `hmc5883l`/`qmc` 条目）。该实现存在至少五处确定性缺陷（见「实现决策」），直接抄进库等于把坑固化。

此外 HMC5883L **已停产**（原厂 Honeywell 停产多年），市面上能买到的「HMC5883L 电子罗盘模块」绝大多数实为 **QMC5883L**（同封装、同 I2C 引脚、寄存器与地址完全不同，且寄存器写错会立刻把器件切进另一套语义）——只做一件会让用户拿到另一种芯片时静默读出垃圾数据。

## 方案

新增**两个独立模块**（互替件，各一套寄存器），双平台（mspm0 + stm32），全 API（读数 + 航向角 + 硬铁偏移校准入参 + 启动验 ID）：

- `library/modules/hmc5883l`：Honeywell HMC5883L（7 位地址 0x1E，写 0x3C / 读 0x3D），含 **ID 寄存器（0x0A）自检**；
- `library/modules/qmc5883l`：QST QMC5883L（7 位地址 0x0D，写 0x0D / 读 0x0E），含 **Chip ID 寄存器（0x00）自检**（须读回 0xFF）。

两者 API 同名同语义，用户换模块只改头文件名；两件在生成页互写「互替件」说明。软 I2C 挂载（照 `aht10`/`bh1750`/`sht20`/`sht30` 先例）：mspm0 侧 GPIO 位操作 + 运行时切换 SDA 方向，stm32 侧并入既有软 I2C 总线。

## 用户故事

1. 作为做题用户，我选中 `hmc5883l`（或 `qmc5883l`）后，工具自动分配默认脚，生成的工程打开即可编译。
2. 作为做题用户，我调用 `xxx_init()` 后能收到明确的失败返回——**接线错、器件型号不符（把 QMC 当 HMC）当场报错**，而不是静默读出垃圾数。
3. 作为做题用户，我调用 `xxx_read(&x, &y, &z)` 拿到三轴磁场原始值（16 位有符号，含符号扩展）。
4. 作为做题用户，我调用 `xxx_read_heading(&deg)` 拿到航向角（0–360°，可叠加我自己的硬铁偏移）。
5. 作为做题用户，我把实测硬铁偏移（`x_off/y_off/z_off`）作为入参传进去，现场磁干扰下不改一行代码即可重定标。
6. 作为维护者，我查看 manifest 能看到手册来源、原实现缺陷清单与修正、与库内同类件（`ml_mpu6050` 姿态 / `imu_uart` / 互替件）的分工与默认脚重叠理由。
7. 作为维护者，我跑 `tests/test_module_hmc5883l.py` / `test_module_qmc5883l.py` 能钉住「缺陷不回潮」——每一条原实现缺陷都有对应断言。

## 实现决策

### 素材与「手册来源」的诚实交代（重要，不掩饰）

- 库内**没有** HMC5883L / QMC5883L 的移植手册：lckfb 地猛星 41 篇、地阔星 43 篇 sensor 页里**都没有磁力计页**（已全库检索确认）。
- 故本批的寄存器表**来源 = 官方数据手册**（HMC5883L Datasheet 900405 Rev E；QMC5883L Datasheet 1.0），并在 manifest：
  - `source_url` 指向**器件原厂/官方数据手册页面**（不是不存在的移植页——不编造 wiki 链接）；
  - `notes` 明确写「**手册来源 = 官方数据手册 + 原实现**」，并记「库内无移植手册页」这一事实。
- **实施第一单必须先取得数据手册文本**（HMC5883L 已停产：原厂页下线，走厂商存档/公开镜像文档站；QMC5883L 走厂商公开手册）。取不到就在 notes 写明「寄存器表依据 = 通用公开寄存器表 + 原实现交叉核对」，并把不确定项标为待上板验证——**绝不假装有权威手册**。

### 寄存器表（两件各一套，实施时以手册复核）

**HMC5883L**（写 0x3C / 读 0x3D）：

| 寄存器 | 地址 | 本件写入值 | 语义 |
|---|---|---|---|
| CRA | 0x00 | 0x70 | 8 次平均、15Hz、正常测量 |
| CRB | 0x01 | 0x20 | 增益 ±1.3Ga（1090 LSB/Gauss） |
| MR | 0x02 | 0x00 | 连续测量 |
| 数据 | 0x03..0x08 | — | **X(0x03/04)、Z(0x05/06)、Y(0x07/08) 各 16 位大端有符号**（注意器件寄存器序号是 X-Z-Y 而非 X-Y-Z） |
| ID | 0x0A..0x0C | — | 必须读回 `'H','4','3'`（0x48/0x34/0x33） |

**QMC5883L**（写 0x0D / 读 0x0E）：

| 寄存器 | 地址 | 本件写入值 | 语义 |
|---|---|---|---|
| 数据 | 0x00..0x05 | — | **X、Y、Z 各 16 位小端有符号** |
| 状态 | 0x06 | — | bit0 DRDY、bit1 OVL、bit2 DOR |
| 控制1 | 0x09 | 0x1D | OSR=512、RNG=±8G、ODR=10Hz、MODE=连续 |
| 控制2 | 0x0A | 0x40 | 中断使能（本件轮询，置位后不使用中断脚） |
| SET/RESET 周期 | 0x0B | 0x01 | 推荐值 |
| Chip ID | 0x0D | — | 读回 **0xFF** |

> ⚠️ HMC5883L 与 QMC5883L 的**寄存器语义完全不同**（0x09 在 HMC 是状态寄存器、在 QMC 是控制1；0x0B 在 HMC 是 ID 尾字节、在 QMC 是 SET/RESET 周期）。把 HMC 的初始化序列发给 QMC 会写坏它的控制字——这正是「两件分开 + 每件启动验 ID」的理由。

### 原实现（`ml_hmc5883l.c/.h`）缺陷清单与本件修正（每条对应一条测试断言）

| # | 原实现 | 缺陷 | 本件 |
|---|---|---|---|
| 1 | `uint8_t HMC5883L_Read(uint8_t addr)`：写地址 `HMC5883L_ADDR`(0x3C) 发寄存器，再发 `HMC5883L_ADDR \| 0x01`(0x3D) 读回 1 字节 | **读地址被当成寄存器地址**（`\| 0x01` 而非读位语义，且 0x3D 已被 OR 进地址字） | 读用 0x3D、写用 0x3C，显式 `HMC5883L_ADDR_WRITE` / `HMC5883L_ADDR_READ` 两个宏 |
| 2 | `#define HMC5883L_DOXMR 0x03 … DOZMR 0x05 … DOYMR 0x07` | 寄存器序 X-Z-Y 被注释成 X-Y-Z，易误用 | 宏名与器件手册一致（DOX/DOZ/DOY），注释标明「器件序 = X-Z-Y」 |
| 3 | `hmc_x = data_l \| (data_h << 8)` | **缺符号扩展**，负磁场（南向/反向）读成 32768+ 的大正数 | 统一走 `int16_t` 拼装（`(int16_t)((hi << 8) \| lo)`），读数出参为 `int16_t` |
| 4 | `float yaw_hmc;` 声明后**从未赋值** | 航向角功能名义存在、实际不可用 | `xxx_read_heading(&deg)`：`atan2f` 出 0–360°，north 朝 +X / east 朝 +Y、顺时针；入参含硬铁偏移 |
| 5 | 初始化写 `CRA=0xf8`、`CRB=0x20`、`MR=0x00` | `0xF8` 落在 CRA 保留位区间（手册 CRA 合法组合为 0x70/0x78 等），取值来源不明 | CRA=0x70（8 平均/15Hz/正常）、CRB=0x20、MR=0x00，逐条注释依据 |
| 6 | init 从不读 ID、所有 I2C 原语**忽略 ACK** | 器件拔了/接错/换成 QMC 也「初始化成功」，后续静默读垃圾 | init：写后读回配置（或 ID 校验），ID 不符 → 返回 2（器件不符）；总线无 ACK → 返回 1（通信失败） |

### 通信形态与引脚

- **软 I2C**（照 aht10/bh1750/sht20/sht30 先例）：不占硬件 I2C 外设、不占 TIMER；半周期延时走 `delay` 模块（`dependencies: ["delay"]`）；SDA 方向运行时切换（写=输出、读=输入）；节点需模块自带上拉。
- **mspm0**：母版 `mspm0.syscfg` 新增 `HMC5883L` / `QMC5883L` 两个 GPIO 实例（各 SCL/SDA 两脚），manifest pins 类型 = `gpio_out`；
- **stm32**：并入既有 **PA6/PA7 软 I2C 总线共享组**（`tests/test_default_layout.py` 白名单登记，与七件既有件共总线——器件地址全异、多挂合法），pins 类型 = `i2c_scl`/`i2c_sda`，宏落母版 `pin_config.h`。
- **地址冲突已核**：HMC 0x3C/0x3D、QMC 0x0D/0x0E 与库内已知地址（0x1A/0x38/0x40/0x44/0x46/0x50/0x52/0x58/0x5A/0x90/0xD0/0xEE/0xEF）**零冲突**。
- **mspm0 默认脚（同选概率最低）**：

  | 件 | SCL | SDA | 重叠主体（同选概率最低） |
  |---|---|---|---|
  | `hmc5883l` | PB6 | PB7 | aht10（温湿度）+ pca9685（舵机驱动）——罗盘与温湿度/舵机阵列同框概率低 |
  | `qmc5883l` | PA23 | PA24 | bmp180（气压）——罗盘与气压同框概率低；互替件 ms5611（PA28/PA31）刻意错开 |

  注意基线（已读母版 manifest 实测数据）：`aht10` = PB6/PB7、**`pca9685` 也 = PB6/PB7**、`bh1750` = PA12/PA13、`bmp180` = PA23/PA24、`sht30`/`ms5611` = PA28/PA31、`at24c02` = PB24/PB8、`sgp30` = PA18/PB9、`mlx90614` = PA9/PA8、`sht20`/`ads1115` = PA16/PA17、`ags10` = PB18/PA14。**spec 早前「六件共 PB6/PB7」的说法与实测不符，以实测为准**；QMC 故不选 PB24/PB8（at24c02 存储件默认脚——罗盘+数据记录同框概率高于罗盘+气压）。
  **PA0/PA1 禁用**（既定事实：不可作 GPIO 输入，而 SDA 需输入）。

### 共有件注册（新实例 + 库元数据）

- `src/contest_generator/syscfg_instances.py` — `INSTANCE_CONSUMERS` 新增 `"HMC5883L": ("hmc5883l",)` 与 `"QMC5883L": ("qmc5883l",)`（否则 syscfg 裁剪不认识新实例；已核该表当前含 AHT10/BMP180 等条目）；
- `src/contest_generator/wordlist.json` — 就近分类补录两件（电子罗盘/磁力计；两件互写互替说明）；
- `tests/test_pins.py::MSPM0_DEFAULT_MAP`、`tests/test_pin_bindings.py`（刻意重叠表登记 PB6/PB7 与 PA23/PA24 两组）、`tests/test_default_layout.py`（PA6/PA7 软 I2C 总线共享组白名单、以及 mspm0 侧 PA23/PA24 的重叠断言）、`tests/test_syscfg_prune.py` — 随新实例与默认脚同步；
- **两件 IO 语义分工（ADR 0009 的职责边界）**：与既有软 I2C 件同构（SRAM 缓冲 + 阻塞收发），不新增任何 IO 机制。

### API 契约（两件同名同语义）

```c
/* 返回：0=成功；1=总线无应答/通信失败；2=器件 ID 不符（接错或型号不匹配） */
uint8_t xxx_init(void);
/* 三轴原始值（16 位有符号，已符号扩展）；返回 0=成功 / 1=读失败 */
uint8_t xxx_read(int16_t *x, int16_t *y, int16_t *z);
/* 航向角（0–360°，顺时针；硬铁偏移入参，传 NULL 或 0 表示不校正） */
uint8_t xxx_read_heading(float *deg, int16_t x_off, int16_t y_off);
```

- `z_off` 不入航向角公式（航向只用 x/y），故 `xxx_read_heading` 只收 x/y 偏移；`xxx_read` 出参三轴齐全供用户自行算法。
- 状态机/校准流程（如 8 字校准走位）**不入库**（ADR 0009）——校准只提供偏移入参，流程归生成骨架。

## 测试决策

- **最高既有接缝**：`pytest`（模块库结构+生成门禁）+ `tests/js`（无需新增，本批无前端改动）。照 `tests/test_module_bh1750.py` 模板，每件一个 `tests/test_module_<slug>.py`：
  1. manifest 形状（双平台文件齐、pins 类型/默认脚/macros、verified/hardware_bound/kit/source_url、notes 含「手册来源」与「未上板」）；
  2. stm32 宏落母版 `pin_config.h`；
  3. mspm0 新实例落母版 `mspm0.syscfg`；
  4. 双平台单选生成（stm32：uvprojx 注册 + pin_config.h 落盘 + 静态门禁；mspm0：syscfg 裁剪只留本件 + 模块文件落盘）；
  5. **代码守卫**（本批重点）：剥离注释后零 `printf`/`main`/标准库/母版 `ml_i2c` 调用；SDA 方向切换宏存在；**缺陷防回潮**——ID 校验存在、符号扩展存在、读地址 = `_ADDR_READ` 且不等于写地址、无 `yaw_hmc` 式死全局、CRA 不是 0x70/0x78 以外的值；
  6. **纯函数单测**：航向角换算（`atan2` 语义、0–360 归一、偏移入参生效、零向量边界）——把换算法收敛成模块内 `static` 之外的**可测纯函数**（`xxx_heading_from_xy`）暴露在头文件，测试直接调（比照 bmp180/ms5611 气压换算纯函数单测先例）。
- **编译矩阵**：照 `.scratch/wiki-modules-batch1/run_joystick_matrix.py` 改 slug，每件每平台跑「单选生成 → SysConfig CLI（mspm0）→ gmake / UV4（stm32）」，**0 error、0 module warning** 为硬门槛；`verified` 由 false 回写 true。
- 本批不做真机（无磁力计硬件）——两件 notes 与 spec 都如实写「未上板」，并把「ID 校验值依赖真机复核」列为已知项。

## 范围外

- 不做 8 字/椭球硬铁软铁拟合校准算法（只做偏移入参）；
- 不做磁偏角查表/经纬度输入（用户自行处理）；
- 不做中断脚（DRDY）驱动，QMC 的控制2 中断位置位但不使用；
- 不改 `ml_mpu6050`/`imu_uart`（姿态件与磁力计件分工写在 notes，代码零交叉）；
- 不动桌面 `stm32base` 与 `stm32-master` 里的旧副本（那是用户工作目录，且已录得缺陷清单）。

## 补充说明

- **塔克 R3 厂商资料不入库**（用户决策：防侵权）——本批素材完全来自官方数据手册与仓库内既有实现，不引入任何厂商受版权保护的教程物料。
- 原实现三处副本（`2021F`/`2026H`/`stm32base`）保留原样，不作修改；缺陷清单与新实现并列共存，manifest notes 指向原实现路径以便溯源。
- 若实施中发现手册取不到、或 ID 校验值与手册矛盾，**停止并按手册为准记录**——不猜。
