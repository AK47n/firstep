# 07 — oled 模块 SPI 总线变体（决策 B：扩展既有 oled，零回归接口）

**要做什么：** 扩展库内 `oled` 模块加 SPI 总线变体（0.96 SPI 单色屏 SSD1306 128×64，厂家目录 中景园电子ZJY096S0700WG01技术资料\02-0.96OLED程序源码.zip「SPI模块例程/STM32例程」，wiki 页 screen--0-96-single-spi-screen.md）。**零回归接口**：现 `OLED_Init()`（I2C1 硬件 I2C）与全部 `OLED_*`/`oled_*` 函数签名与 I2C 路径代码不动；新增 `OLED_SPI_Init(void)`（软 SPI 位操作 5 脚 SCL/SDA/DC/CS/RES——照 nrf24l01/max7219 先例不占硬件 SPI 外设/TIMER、忙等；vendor 页内 SPI 版 init 序列与 I2C 版同参，逐字核对 0xAE/0xA8/0x3F/0xD3… 序列差异）；`OLED_WR_Byte` 按模块内静态总线模式分发（I2C=现 DL_I2C 路径 / SPI=位操作路径），绘制/文本/显存 API 与 GRAM/Refresh 语义逐字节不变。母版 syscfg 新 GPIO 实例 `OLED_SPI`（5 脚全输出，CS/RES 初始 SET）+ INSTANCE_CONSUMERS `"OLED_SPI": ("oled",)`——**已知取舍**：oled 选中（任一总线）时 I2C1「OLED」实例保留（PB2/PB3 默认脚 SPI 模式下仍占用，需要时经绑定换脚消解，notes 记录）。**剩余核对项**：0.91 IIC（ZJY091I0400WG01，SSD1306 **128×32**）核验库内 oled 是否支持——不支持则加分辨率宏 `OLED_RES_128X32`（MUX 0x1F + COM 0x22 + Refresh 半高写入，顺带回归）记 spec/notes；0.96 IIC / 1.3 单色（ZJY096I0400WG01/ZJY130S0700WG01）仅核对（库内已覆盖同家族）不提炼。全量回归：test_module_oled.py 既有断言（I2C 零变化）+ 新增 SPI 断言（OLED_SPI_Init 存在 + 位操作无 DL_I2C 强依赖 + 0.91 核验结论守卫）+ 编译矩阵（I2C 变体重跑 + SPI 变体单选）0 error/0 warning → verified 回写（含 SPI 编译记录）→ 中文提交 → code-review（本件深审）。

**被谁阻塞：** 无（独立；实现顺序按 spec 建议在 01-06 后，oled 回归可与 01 并行观察）。

**状态：** resolved

**结论：** 2026-09-12 完成并提交。oled SPI 总线变体（决策 B）：OLED_SPI_Init（软 SPI 5 脚——母版新 OLED_SPI 实例，默认 PA28/PA31/PA13/PB18/PA22）+ OLED_WR_Byte 总线模式分发（s_bus_spi 静态态——I2C 路径零行为变化）+ 初始化序列公共化 oled_drv_init（厂家 SPI/I2C 例程序列同参逐字核对）；零回归：既有 API/签名/I2C 代码不动（回归断言 + I2C 变体编译矩阵重跑 PASS）；0.91 128×32 核验结论 = 原驱动 MUX 0x3F/COM 0x12 不适配 → 新增 oled_set_res(OLED_RES_128X32)（初始化前调用；GRAM 不变、超行面板忽略）；0.96 IIC/1.3 单色核对记录（同家族不提炼）；已知取舍：SPI 模式下 I2C1（PB2/PB3）保留（不引入变体感知裁剪）；SPI 变体矩阵 PASS（0 error/0 warning）；未上板。

**验收：**

- [x] oled.c/h：OLED_WR_Byte 总线模式分发（静态模式变量，OLED_Init → I2C 模式、OLED_SPI_Init → SPI 模式）；SPI 位操作（SCL/SDA/DC/CS/RES 宏参数化 `<实例>_<引脚>_PORT/PIN`）；init 序列 SPI 版逐字核对；OLED_* 既有 API 零改动
- [x] manifest.json：mspm0 pins 增 5 SPI 角色（oled 选中时两者共存——I2C 角色保留）；notes 补 SPI 变体说明 + 字段/已知取舍（PB2/PB3 占用）+ wiki 页（screen--0-96-single-spi-screen.md）+ 网盘 + 厂家目录；description 补 SPI 总线
- [x] 母版 syscfg OLED_SPI 实例 + INSTANCE_CONSUMERS「OLED_SPI」登记
- [x] 0.91 128×32 核验：查库内 oled.c init（0xA8 MUX/0xDA COM/Refresh 页数）——不支持则补 OLED_RES_128X32 宏分支（验证后 notes 记录核验结论）；0.96 IIC/1.3 单色核对记录 notes
- [x] 测试：test_module_oled.py 回归（I2C 零变化断言）+ SPI 变体断言 + 0.91 结论守卫；test_pins/test_pin_bindings/test_syscfg_prune 增断言
- [x] 编译矩阵：I2C 变体重跑 PASS + SPI 变体单选生成 → SysConfig CLI → gmake 0 error/0 warning；verified=true + notes；中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
