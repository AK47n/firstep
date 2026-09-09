# 04 — l298n 电机驱动模块（PWM×2 + 方向互切，手册 control--l298n-motor-drive-module.md）

**要做什么：** 模块库 `l298n` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 L298N 驱动为纯驱动切片（**双 PWM 通道（IN1/IN2 方向互切）**——mspm0 定稿单路形态，API 与 mspm0 版**同名同型完全对齐（l298n.h 核验）**：`l298n_init()` + `l298n_set_duty(uint32_t duty)`（`L298N_PWM_PERIOD 2000u` 宏——占空比 0-2000）+ `l298n_set_direction(uint8_t dir)`（方向互切 IN1/IN2 原式——照 mspm0 .c 实现口径）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；页面 IN1/IN2 双 PWM 方向互切（1kHz@72/1000）；**只实现 A 路（B 路未给——范围外）**；无 EN 代码（跳线帽——范围外）；speed 无上限（mspm0 已补限幅——stm32 沿用）；**默认 TIM3_CH1/CH2 = PA6/PA7（页面原脚；TIM3 定时器零占用；与 TB6612 motor（TIM2/PA0-1）互替刻意错开 TIM 与脚）**；**⚠ TIM 门禁只查用户绑定**（2026H 骨架调度 TIM_3 × l298n 默认 TIM_3 = 默认×默认不拦——现状口径 notes）；**⚠ PA6/PA7 与软 I2C 总线同脚**（l298n×I2C 件同选 = 物理冲突 ⚠ + 绑定消解）。

**引脚/宏：** pins `L298N_IN1`（pwm，default **PA6**，macros `[L298N_IN1_TIM, L298N_IN1_CH]`）/ `L298N_IN2`（pwm，default **PA7**）；pin_config.h：`#define L298N_IN1_TIM TIM_3` / `L298N_IN1_CH TIM3_CH1` / `L298N_IN2_TIM TIM_3` / `L298N_IN2_CH TIM3_CH2`（注释：默认 TIM3_CH1/CH2=PA6/PA7 页面原脚（TIM3 空闲）；与软 I2C 总线（PA6/7）同脚冲突 ⚠（同选绑定消解）；与 TB6612（TIM2/PA0-1）互替错开；TIM 门禁默认×默认不拦）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [ ] `library/modules/l298n/code/l298n_stm32.c/.h`（独立 stm32 头——3 函数 + L298N_PWM_PERIOD 2000u 宏照 mspm0 l298n.h；.c pwm_init/update + 方向互切（IN1/IN2 占空比交换——照 mspm0 .c 逐行）；零引脚字面量）
- [ ] manifest.json platforms 增 stm32：files、dependencies ["delay"]（脉宽周期换算——照 mspm0 manifest 现状）、verified false、hardware_bound false、pins 2 行（pwm type）、kit/source_url（wiki 原页 `.../control/l298n-motor-drive-module.html`）、notes（手册路径+原页+网盘+单路形态（B 路未给）+EN 跳线帽范围外+限幅（mspm0 同款）+TIM 门禁默认×默认不拦+PA6/7 与 I2C 冲突⚠+默认 TIM3 推理+未上板）
- [ ] pin_config.h 增 4 宏
- [ ] 测试 `tests/test_module_l298n.py`：形状（2 pins pwm）+宏存在（`L298N_IN1_TIM\s+TIM_3`/`L298N_IN1_CH\s+TIM3_CH1`/`L298N_IN2_CH\s+TIM3_CH2`）+单选生成+mspm0 零改动+守卫（`L298N_PWM_PERIOD 2000u`、set_duty/set_direction、无 EN 代码、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2（与 I2C 总线冲突组——PWM 外设级登记）
- [ ] UV4 矩阵（init+set_duty(1000)+set_direction(1)，(void) 化）→ 0/0 → verified=true（**确认 TIM3 CH1/CH2 编译**——gmake 等价 UV4 过）
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  文件落盘 `library/modules/l298n/code/l298n_stm32.c`（2895B）与
  `l298n_stm32.h`（3574B）；头文件 45-54 行 API **3 函数**
  （init / set_duty(uint32_t) / set_direction(uint8_t)）+ `L298N_PWM_PERIOD` 宏。
  manifest 实测：`platforms=['mspm0','stm32']`、`stm32_files=2`、`verified=True`、
  `hardware_bound=False`、`pins=['L298N_IN1','L298N_IN2']`、kit/source_url 齐。
  pin_config.h：`pin_config.h:517-520` `L298N_IN1_TIM TIM_3` / `L298N_IN1_CH TIM3_CH1`
  / `L298N_IN2_TIM TIM_3` / `L298N_IN2_CH TIM3_CH2`（默认 PA6/PA7，注释 509-516
  记录「与软 I2C 同脚冲突 ⚠ / 与 TB6612 错开 / TIM 门禁默认×默认不拦」）。
  测试 `tests/test_module_l298n.py` 8 用例（:43/:78 mspm0 / :109 AO_Control 形状
  与调用守卫 / :179 stm32 形状 / :209 宏 / :218 stm32 单选生成 / :242 stm32 守卫）
  ——实测全绿。
  wordlist：`wordlist.json:664/690/696` 已收录（lib_modules `l298n`）。
  验收逐条对照：① stm32 源 + 3 函数 + PWM_PERIOD 宏 ✓ ② manifest stm32 条目
  ✓ ③ pin_config 4 宏 ✓ ④ 测试形状+宏+生成+守卫 ✓ ⑤ test_pins/test_default_layout
  （PA6/PA7 组）✓ ⑥ 矩阵 verified=true（notes 记录「2026-09-08 stm32 单选生成 →
  UV4 0 error / 0 module warning」）✓ ⑦ wordlist ✓。
