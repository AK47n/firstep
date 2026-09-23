# 11 — mspm0 引脚符号重名：任选两件就编不过，而门禁一声不吭

**要做什么：** 选中集的 mspm0 工程里，**同一趟出现的两个实例不许再有同名引脚符号**——要么母版把重名的引脚改名，要么生成前把它判成冲突并给出可执行的出路（照既有的 400 文案口径）。今天的状态是：SysConfig 直接报错、工程编不过，而**检测页与赛题页都没有任何提示**。

**被谁阻塞：** 无——可立即开始（发现于工单 04 的两平台编译矩阵，与 04 的改动无关）

**状态：** ready-for-agent

- [ ] 母版 `mspm0.syscfg` 里 14 组重名引脚符号盘点清楚，逐组判"同趟真会撞"还是"结构上不可能同趟"（候选清单见下）
- [ ] 判据进**生成前**：选中集里两个实例的同名引脚 → 大声失败（400 中文，出路照检测页那三条）或自动改名，二选一，不许"生成了、编译时才炸"
- [ ] 真编译矩阵复跑：至少 `oled + jy61p`（今天 4 个 error）、`led_beep + gp2y1014au`（`LED` 重名）、`rc522 + nrf24l01`（`MISO`/`MOSI`/`CLK` 重名）三格 0 error / 0 warning，或按上面的裁决被生成前拦下
- [ ] 既有守卫不破：`syscfg_pin_conflict_report`（同脚冲突那条）判据与文案不变；母版实测读数不受影响（改了 `.syscfg` 要复跑既有编译矩阵）
- [ ] 反证：把改名/拦截拿掉 → 对应用例变红（读数记进本工单）

---

## 现场（发现于工单 04 的编译矩阵，2026-09-23）

**最小复现**（`.scratch/hwcheck-unknown-device/tmp-diag-dupname.py` 就是它，跑完可删）：
检测页 mspm0、只勾 OLED + JY61P（**没有自建件、没有 i2c_probe**）→ 生成成功（200）
→ 点「编译」→ gmake 退出 2：

```
error: JY61P(/ti/driverlib/GPIO) associatedPins[0].$name: Duplicate name: 'SCL'
       also exists on instance(s) of MSPM0 GPIO Pin
error: OLED_SPI(/ti/driverlib/GPIO) associatedPins[0].$name: Duplicate name: 'SCL' ...
error: JY61P(/ti/driverlib/GPIO) associatedPins[1].$name: Duplicate name: 'SDA' ...
error: OLED_SPI(/ti/driverlib/GPIO) associatedPins[1].$name: Duplicate name: 'SDA' ...
4 error(s), 0 warning(s)
```

**母版里 14 组重名**（扫描脚本 `.scratch/hwcheck-unknown-device/tmp-diag-names.py`）：

| 引脚符号 | 出现在哪些实例 |
|---|---|
| `SCL` / `SDA` | ADS1115、AGS10、AHT10、AT24C02、BH1750、BMP180、HMC5883L、**JY61P**、LCD、MLX90614、MS5611、**OLED_SPI**、PCA9685、QMC5883L、SGP30、SHT20、SHT30、TCS34725（**17 件**） |
| `CS` | LCD、MAX7219、OLED_SPI、RC522、TP_XPT2046 |
| `OUT` | HUMAN_IR、IR_BEAM、IR_REMOTE、IR_TX、MICROWAVE、RELAY |
| `CLK` / `DIN` | MAX7219、NRF24L01(=CLK)、TP_XPT2046 |
| `MOSI` / `MISO` | NRF24L01、RC522 |
| `DATA` | DHT11、DS18B20 |
| `DC` / `RES` | LCD、OLED_SPI |
| `LED` | GP2Y1014、LED_BEEP |
| `SCK` | HX711、RC522 |
| `TX` | JQ8900、SYN6288 |

**为什么现在没被发现**：`syscfg_pin_conflict_report`（生成门禁与检测页共用的那条判据）
判的是**同一个脚被两个实例占用**（`$assign` 的 pin 值重复），**不判引脚符号 `$name`
重名**——后者是 SysConfig 的另一条全局唯一约束。于是"装了、编不过"这条路一路畅通，
而 `SPEC` 里那条"落盘后的 mspm0.syscfg 有没有冲突"的守卫对它天生失明。

**影响面**：`SCL`/`SDA` 那一组最要命——库内 17 件 I2C 器件**任选两件**（如 OLED + 任意
传感器）在地猛星上就是 4 个 error。这不是冷门组合，是检测页的日常用法。

**修法候选**（动手前先判，别直接挑）：

1. **母版改名**：把 `<实例>.associatedPins[n].$name` 改成实例前缀（`OLED_SPI_SCL`、
   `JY61P_SDA`…）——母版里本来就有这一形态（`STEP_MOTOR.RST2` / `DC_MOTOR.AIN1`
   是前缀式的），一致。代价：**是跨模块的共享面**，要看有没有模块代码引用这些
   生成出来的符号（`SCL` / `SDA` 这类裸名进 C 代码会很危险），并复跑全部 mspm0 编译矩阵；
2. **判据前移**：在 `syscfg_pin_conflict_report` 里加一条"同名引脚"检查，撞上就
   400 并给检测页那三条出路——与既有"装不下"同形，代价是**缩小了可用组合**
   （OLED + 传感器仍然不能同选，只是从"编不过"变成"生成前说清"）；
3. 两者都做（先拦后治）：短期 2、长期 1。

**与工单 04 的关系**：04 的验收线是"自建件探测程序两平台 0 error / 0 warning"，
这条缺陷**独立于自建件**（最小复现里一个自建件都没有），故不在 04 内修；04 的
编译矩阵把 `all-library` 那一格记为"已知受限形态"，读数与本条互指。
