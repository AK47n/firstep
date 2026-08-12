# 05 — lock_control / zone 决策剥离（2026C 数字钥匙，可解散）

**What to build:** 2026C 数字钥匙双模块按 ADR 0009 处理：决策层移出——lock_control 的 zone/event 状态机 + 迎宾声光时序、zone 的感应/迎宾/解锁区域划分（题定义）→ 骨架；驱动层评估去留：lock_control 剩余 = LED 三色 + 蜂鸣器驱动，与 led_beep 模块重叠 → **优先解散**（驱动并入 led_beep 或功能库，模块删除，决策进骨架）；zone 剩余 = 测距/方位数据处理驱动 → 评估并入 uwb 类模块或解散。解散与否实施时按代码定细界，结果与理由记录在工单。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 lock_control/zone 后必须删除注册表对应两条目（不删 = 存量校验红）。注意：2026C 生成链路（generate_check.py 真机验收脚本）引用这两模块——解散后需同步检查生成用例（红证/绿证）。**

**Status:** resolved

## 实施（细节实施会话定）

1. 决策剥离：lock_control.c 状态机/时序/事件 → 骨架（2026C 题生成时 AI 写）；zone.c 区域划分 → 骨架。
2. 驱动评估：LED 三色 + 蜂鸣器 → led_beep 模块（当前 mspm0 版，评估加 stm32 平台条目）或 stm32 功能库 gpio 直用；测距/方位处理 → uwb 类模块或解散。
3. 解散动作：模块目录删除 + manifest 清理（若被推荐/生成引用需登记，2026C 骨架的 deps 改由保留模块承担）。
4. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 lock_control / zone 两条目——不删 = 存量校验红；解散（目录删除）也必须删条目。
4. generate_check.py / 真机用例同步：2026C 生成 → UV4 编译验证。

## 文件边界

- library/modules/lock_control/*、library/modules/zone/*
- library/modules/led_beep/*（若并入 stm32 条目）
- 交叉：2026C 生成链路（generate_check.py 用例、推荐引用）
- **不动**：uwb_uart / zigbee_uart / config 模块内容

## 验收

- [x] stm32 UV4 编译 0 错（2026C 全管线：推荐 → 骨架 → 生成 → 构建，模块保留或解散后的新形态）。
- [x] 结构测试绿（lock_control / zone 不再命中黑名单；解散则无此二模块扫描对象）。
- [x] 解散/保留决定有记录（工单写明结果与理由）。
- [x] 2026C 生成用例同步过（生成不引用已删模块）。
- [x] EXCEPTION_REGISTRY 已删 lock_control / zone 条目（解散则随目录删除一并删），删后全库测试仍绿。
- [x] 工单补实施记录 + 验收勾选，Status resolved。

## 实施记录（2026-08-12）

### 决定：lock_control / zone 全部解散（目录删除）

**lock_control → 解散。** 决策层（LOCK_OPEN/CLOSED 状态机、zone/event 事件系统、迎宾声光时序、区域切换锁动作）占绝对主体 → 归骨架：2026C 生成时 AI 写进 main.c（真机产物已验证：main.c 内联 s_zone_state 状态区，System_GPIO_Init 直接用 config.h 宏 + 母版 ml_gpio 完成 LED 三色/蜂鸣器/DIP 初始化）。驱动残留（LED 三色 + 有源蜂鸣器非阻塞响铃）**不并入 led_beep**——按代码定细界的三条硬约束：

1. led_beep 是双平台活跃模块（2024H mspm0 真机选中、2021F stm32 真机选中，见 .scratch/real-run/check_2024H.log / green_2021F_stm32.log），而 manifest 依赖是模块级、无平台粒度；
2. stm32 版引脚唯一正源 = config.h（2026C 集中配置头，工单明确不动）：若 led_beep 加 dep config → mspm0 选 led_beep 时依赖展开出无 mspm0 条目的 config → 生成门禁 MissingModuleFilesError 直接失败（2024H 线即破）；
3. 若 led_beep_stm32 自含引脚 → 与 config.h"所有硬件引脚集中定义、方便改线"的单源约定冲突。

残留驱动仅 3×gpio_init + 3×gpio_set + 1 脉冲，低于"纯驱动切片"成模块的下限——走工单备选 **"stm32 功能库 gpio 直用"**：骨架 AI 以 config.h 宏 + 母版 ml_gpio 内联承担。led_beep 保持现状（mspm0 PA14 + stm32 占位走母版 ml_led），21F / 2024H 双线既有行为零改动。

**zone → 解散。** zone.c 全部 = 题定义区域划分（Zone_t 枚举 + zone_determine 带滞回判定 + zone_name），纯计算无硬件访问，无驱动残留 → 全部归骨架（AI 以 config.h 的 THR_*/FOV_HALF_ANGLE 宏内联实现；真机产物 main.c 已含判定阈值注释段）。"测距/方位数据处理"实际分布于保留模块 uwb_uart（0x2001 帧解析）+ filter（滑动滤波），zone 仅是消费方，无独立驱动切片可并入 uwb 类。

### 动作

- `git rm` library/modules/lock_control/、library/modules/zone/（manifest + code 各 3 文件）。
- debug_uart（保留，注册表条目不动）：manifest dependencies ["lock_control"] → ["config"]；debug_uart.c 的 r/y/g/o 命令改内联 gpio_set（config.h 的 LED_PORT/LED_RED_PIN/LED_YELLOW_PIN/LED_GREEN_PIN 宏），b<N> 蜂鸣命令改 gpio_set + delay_ms 阻塞实现（原非阻塞关闭依赖 lock_control_update 每轮轮询，模块删除后无可轮询处；调试命令场景可接受），include 换 config.h。
- tests/test_module_universality.py：EXCEPTION_REGISTRY 删 lock_control / zone 两条目；红证 docstring 与"已清理移除"注释同步（五模块 02~05 全部清理完毕）。
- ~/.contest_generator/modules 过期镜像副本同删（服务已指仓库内库 library/modules，generate_check 的未知 slug 检查读主目录副本——保留会让已删模块的检查假过）。

### 验证

- pytest 全量 **1095 绿**；结构测试 6 例绿（lock_control/zone 目录已删 = 无扫描对象；注册表条目已删 = 无残留条目）。
- mypy 干净。
- 真机 2026C stm32 全管线（generate_check.py：推荐 → 骨架 → 生成 → UV4）通过：
  - 推荐收敛（补问 0 轮）→ 模块 {zigbee_uart_key, zigbee_uart, uwb_uart, filter, config}——lock_control / zone 不再出现；
  - 骨架 main.c 6664 字符，幻觉调用拦截 0 处；
  - 产物门禁全过（产物树语料重建，与生成同源）；
  - UV4 **0 Error(s)**、4 Warning(s)——警告 = LLM 骨架 main.c 的未使用变量声明（s_lock_state / s_welcome_state / s_zone_state / s_expect_id，第 29~32 行），AI 内联状态区时的残留声明，非解散回归；
  - 生成物（main.c + modules/）无任何 lock_control / zone 引用；区域判定与状态机决策已内联进 main.c（s_zone_state 状态区 + 阈值 TODO 注释段 + gpio 直用初始化）。
