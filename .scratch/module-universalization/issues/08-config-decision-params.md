# 08 — config 模块决策参数剥离（工单 06 遗留，注册表清空后的结构性尾款）

**What to build:** 工单 06 真实 AI 校验实证：config 模块代码侧带 ADR 0009 判据④ 所禁的"专用判定参数"——config.h 的 `THR_UNLOCK_ENTER/EXIT`（近区阈值 130/140cm）、`THR_WELCOME_ENTER/EXIT`（远区阈值 230/240cm）、`THR_SENSING_MAX`（430cm）、`TAGID_MASK`、`FOV_HALF_ANGLE`、`ZIGBEE_TIMEOUT_MS`、`TAG_TIMEOUT_MS` 是 2026C 门禁场景的决策参数（真实 AI issues 原文见工单 06 实施记录），按 ADR 0009 应剥离进生成骨架；模块只保留纯驱动形态的集中外设引脚配置。工单 06 已把全部代码注释中性化（近区/远区/标签，机械黑名单全库=空），本工单处理结构性尾款——config 简介过真实 AI 校验（判据④ 代码侧）。

**Status:** resolved

## 实施（细节实施会话定）

1. 界定保留/剥离：引脚映射 + 通用参数（UWB/OLED/LED/蜂鸣器/DIP 引脚宏、滤波窗口）留 config；区域判定阈值 / FOV / 超时等 2026C 决策参数剥离——目标 = 生成骨架（2026C 生成时 AI 按题面写）或母版/参考文件库。
2. 2026C 生成链路同步：真机骨架 main.c 当前引用 config.h 的 THR_* 宏（05 真机验证产物，`s_zone_state` 状态区 + 阈值注释段），剥离后生成用例需同步（红证/绿证 + UV4 复验）。
3. 剥离后 config 简介真实 AI 全流程校验通过（判据①③④），注册表已空不需动。

## 文件边界

- library/modules/config/*
- 2026C 生成链路（generate_check.py 用例、母版、参考文件库）
- **不动**：其他模块、src/* 生成机制本身

## 实施记录（2026-08-12，worktree config-decision-params，主提交 64935e6）

**剥离界定（代码侧）**：config.h 删 7 组 2026C 决策参数——`THR_UNLOCK_ENTER/EXIT`、`THR_WELCOME_ENTER/EXIT`、`THR_SENSING_MAX`、`TAGID_MASK`、`FOV_HALF_ANGLE`、`ZIGBEE_TIMEOUT_MS`、`TAG_TIMEOUT_MS`（41 行改动，含"区域判定参数"节整体删除）；保留纯驱动形态：全部引脚映射（UWB/OLED/LED/蜂鸣器/DIP/Zigbee 串口宏）+ 通用参数（`OLED_UPDATE_MS`/`EVENT_SHOW_MS`/`FILTER_WIN_SIZE`/`FILTER_AZ_WIN_SIZE`/`DIST_MAX_STEP`/`AZ_MAX_STEP`）。依赖方核查：四模块（debug_uart/uwb_uart/zigbee_uart/zigbee_uart_key）只消费保留的 `UWB_UART/BAUD`、`ZIGBEE_UART/BAUD`，零波及。顺带中性化 LED 注释（"远区指示"→无角色注释）。

**简介改写（判据①③④，update_module_description 全流程真实 AI 校验）**：
- **红证**：剥离后旧简介（"区域判定阈值"）PUT /api/modules/config/description → HTTP 400，AI 精确判不一致："简介中提到'区域判定阈值'，但实际代码中未定义任何区域判定阈值相关宏；代码仅包含引脚映射、时间参数和滤波参数"——判据① 一致性成立，代码侧剥离被 AI 实证。
- **绿证**：新简介"集中外设配置头文件：硬件引脚映射（UART/GPIO/LED/蜂鸣器/DIP 拨码）与通用显示、滤波参数统一集中定义，供各模块与主程序统一调用；适用于 UWB 定位、OLED 显示、LED/蜂鸣器指示等多外设联调场景。" → HTTP 200 入库（能力方向点明，无题绑定）。

**2026C 生成链路同步（generate_check.py 真机全管线，真实 DeepSeek）**：
- 前置：仓库 `library/topics/2026C/topic.md` 仍是修复前题面（上批修复只进了 `~/.contest_generator`，服务端 topic 链按 topic_id 重读题库题面——不同步会收敛退化），同步补录修复（要求表第2项）随主提交入库。
- 首跑遇补问 2 条（手机能否作本体 / 精度静止 vs 移动测量），按题面 + 参考工程（用户实际参赛实现 = 自制 STM32 钥匙；题面说明第2条定点测量）自洽作答预置 clarify 映射重跑。
- **4 轮收敛 → done**（模块 7：zigbee_uart_key / zigbee_uart / uwb_uart / config / led_beep / oled / filter，auto 参考注入 ALX 套件例程 1 条）→ 骨架 main.c 4388 字符、幻觉拦截 0 → 生成 47 文件 → 产物门禁全过 → **UV4 编译 0 Error(s)**（2 Warning = 骨架未用变量声明 g_zone/g_door_state，LLM 骨架固有非回归，05 真机同款）。
- **决策参数由骨架承担实证**：产物 `modules/config/code/config.h` 决策参数残留 = 0；骨架 main.c 按题面写 FOV ±45° 内联（`ABS(az_f) <= 45`）+ 区域阈值注释进 TODO 状态机区（`dist_f <= 100cm 开锁区 / <=200 迎宾区 / <=300 感应区 / >300 无效`，题面 1m/2m/3m 边界），ID 掩码由 DIP 4 位天然承担——剥离闭环。

**验证**：pytest 全量 1095 绿（test_module_universality 6 通过——剥离后 config.h 词表零命中）；mypy src 32 文件干净。

## 验收

- [x] config 简介真实 AI 校验通过（判据④ 无题绑定在代码侧成立，update_module_description 全流程）——红证 400（旧简介 vs 剥离代码，AI 判"区域判定阈值未定义"）+ 绿证 200
- [x] 2026C 真机全管线 UV4 编译通过，产物无回归（决策参数由骨架承担）——4 轮收敛 → 生成 → 门禁全过 → UV4 0 Error(s)；产物 config.h 残留 0，骨架按题面承担 FOV/区域阈值
- [x] 工单补实施记录 + 验收勾选，Status resolved
