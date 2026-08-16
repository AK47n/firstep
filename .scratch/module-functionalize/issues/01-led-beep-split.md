# 01 — led / beep 拆分（双平台）+ led_beep 组合化

**What to build:** `led`、`beep` 两个独立模块（双平台统一 API），原 `led_beep` 保留为组合模块（deps led+beep+delay，只做同时控制）；stm32 led 实现内嵌母版 ml_led；mspm0 led 随模块（LED_BEEP 实例消费方改为 led）；LLM 围栏兜底升级为全剥。

**Blocked by:** 无（spec `.scratch/module-functionalize/spec.md` 已定稿）

**Status:** resolved（2026-08-15）

- [x] led 模块双平台：stm32 空条目（母版 ml_led 升级统一 API）+ mspm0 随模块（PA15，引脚角色 led.LED）
- [x] beep 模块双平台：stm32 用 BUZZER 宏 + mspm0 占位
- [x] led_beep 组合模块：deps [led,beep,delay]，led_beep_init/on/off/alarm
- [x] syscfg_instances LED_BEEP 消费者 = led；pin 测试同步（led_beep.LED_BEEP_LED → led.LED）
- [x] clex.strip_all_code_fences + skeleton 出稿全剥围栏（真机三重围栏判例）
- [x] pytest 全绿 + mypy src 干净 + stm32/mspm0 真机编译回归（slugs 含 led/beep/led_beep）

## Comments

- **真机留痕**：mspm0 led 首版用 LED_BEEP_LED_PORT 编译失败——SysConfig 单端口 GPIO 组只生成 `<INSTANCE>_PORT`（LED_BEEP_PORT）+ `<INSTANCE>_<NAME>_PIN`，已改。stm32 led_init 与母版 ml_led led_init(void) 撞符号——按内嵌母版先例把 ml_led 升级为统一 API，led 模块 stm32 侧空条目。
- 验收：stm32 冒烟/参考 UV4 0 错 0 警；mspm0 冒烟/参考 gmake 0 错 1 警（基线内）。
