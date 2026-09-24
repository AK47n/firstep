# 02 — 母版 mspm0 引脚符号去重：让「OLED 屏 + 任意 I2C 器件」真的能同选

**要做什么：** 学生在地猛星上勾着「OLED 屏」输出通道、再选一件库内 I2C 器件（AHT10 / BH1750 / SHT30 / JY61P…），
今天**生成前必被拦下**，出路只有"去掉一件"。撞的不是脚，是**引脚符号名**：母版把 OLED 的 SPI 变体两个脚
也叫 `SCL` / `SDA`，而库内 17 件 I2C 传感器实例逐字同名——SysConfig 要求同工程引脚符号唯一，
已实测**换四种引脚绑定 `name_count` 恒为 2**（改绑解不开）。本工单要把母版这一层解开，
让这类组合能同选、能生成、能真编译；并给"以后新增实例又撞名"留一道构建期守卫。

> 上游关系：`.scratch/hwcheck-unknown-device/issues/11-mspm0-pin-name-collision.md` 已经把"判据前移 +
> 如实拦下 + 说清出路"做完了，并在结论里**明写留了一条尾巴**：「母版改名（让"OLED + 传感器"这类组合真的能用）
> 没有做……要真正放开得另开一单（母版 `.syscfg` 的 `$name` 改名 + 别处对该符号的引用排查 + 全 mspm0 编译矩阵复跑）」。
> 本工单就是那条尾巴。

**被谁阻塞：** 无——可立即开始（与 01 互不阻塞，可并行）

**状态：** ready-for-agent

- [ ] **先量影响面**（进 Comments，不许跳过）：改名会改掉哪些**生成的宏名**、哪些模块源码引用了它们
      （已知一例：`oled.c` 引用 `OLED_SPI_SCL/SDA_PORT` 与 `_PIN`）。量出的清单决定"改哪一侧面更窄"
- [ ] **裁决表**：工单 11 盘出的重名组（至少含 `SCL`/`SDA`=17 件 I2C 器件 × 显示件、`LED`=gp2y1014au × led_beep、
      `MISO`/`MOSI`=nrf24l01 × rc522、`CLK`=max7219 × nrf24l01 × tp_xpt2046）逐组给出"改名放开"还是"保留并如实拦下"，
      并写清判据（改名的代价 vs 该组合出现的概率）。**`SCL`/`SDA` 这一组必须在"改名放开"之列**
- [ ] 解开后的组合生成 200 且真编译 **0 error / 0 warning**：至少 `mspm0 + OLED 通道 + jy61p`（pilot 里的单平台 I2C 件）、
      `+ aht10`、`+ bh1750`、`+ sht30`，以及 `led-beep + gp2y1014au`（若裁决为放开）
- [ ] **构建期守卫**：母版 `.syscfg` 新增一个与既有实例同名的引脚符号 → 当场红。判据**复用既有**的落盘冲突报告
      （`syscfg_pin_conflict_report` 的 `name_lines` / `name_count`），不另造一套
- [ ] **反证探针**：把改名撤回（或再注入一个撞名实例）→ 守卫与组合用例必须变红；探针逐字节复原 + sha256 复核
      （照工单 11 的 `probe-11-guard-strength.py` 先例）
- [ ] stm32 侧**零变化**（软 I2C 共挂同一条总线本来就合法，别把那边的判定带跑）
- [ ] 母版改动后复跑既有 mspm0 编译矩阵（改了 `.syscfg` 就要重跑，工单 11 的既有纪律）
- [ ] 同批更正 `CONTEXT.md`「硬件检测」「syscfg 文件模型」里"撞名改绑解不开、只能去掉一件"的措辞

---

## Comments

### 2026-09-24 立项依据

本仓 HEAD 实测（`.scratch/hwcheck-acceptance/probe-page.py`，读数 `exit-aht10.txt` 与 `probe-page.txt`）：

```
mspm0 + OLED 通道 + aht10  → 400（SCL/SDA：aht10(AHT10) × oled(OLED_SPI)）
mspm0 + OLED 通道 + bh1750 → 400（同上）
mspm0 + OLED 通道 + sht30  → 400（同上）
mspm0 + OLED 通道 + jy61p  → 400（同上；jy61p 是 pilot 10 件之一）
同上把 OLED 通道关掉        → 全部 200
```

而页面上「OLED 屏」**默认就是勾选的**，指南栏也建议"至少勾一个输出通道"——
所以最自然的一次上板（"我要屏幕看结果 + 我新买的那件传感器"）正好落在墙上。

根因定位（本仓 `library/masters/mspm0/mspm0.syscfg`）：`OLED_SPI.associatedPins[0].$name = "SCL"`、
`[1] = "SDA"`，而 `AHT10` / `BH1750` / `SHT30` / `JY61P` / `HMC5883L` / `AT24C02` / `ADS1115` /
`MLX90614` / `TCS34725` 等每个实例也都把自己的两个脚叫 `SCL` / `SDA`。
