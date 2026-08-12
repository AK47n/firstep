# 06 — 六模块题词清理（工单 01 遗留，注册表尾款）

**What to build:** 工单 01 红证发现 2026C 题词污染面大于 5 个目标模块——以下 6 个模块的简介/代码仍带题词，靠 EXCEPTION_REGISTRY 登记才不红：`config`（"2026C 数字钥匙题专用：集中配置头"）、`debug_uart`（"2026C 门锁端调试串口"）、`zigbee_uart`（"2026C 门锁端 Zigbee"）、`zigbee_uart_key`（"2026C 钥匙端 Zigbee"）、`filter`（"出身 2026C 题"）的 manifest.description，以及 `uwb_uart` 代码注释（"旧钥匙数据"）。任务：五条简介按判据四要素重写（能力方向点明、去题号/年份/题名），uwb_uart 代码注释清理；完成后删除 `tests/test_module_universality.py` EXCEPTION_REGISTRY 中对应 6 条（不删 = 存量校验红）。注册表清空 = 全库无题词，普适化目标在存量侧闭环。

**Status:** resolved

## 实施（细节实施会话定）

1. **rewrite 五条简介**（走 update_module_description，判据④机械预检 + AI 校验④会拒绝任何残留题词的提交——正好当验收）：
   - `config`：能力方向 = 集中外设配置宏头（去"2026C 数字钥匙题专用"）
   - `debug_uart`：能力方向 = 调试串口 + 单字符命令（去"2026C 门锁端"）
   - `zigbee_uart` / `zigbee_uart_key`：收发两端实现——**端侧语义保留但换通用表述**（"锁端/钥匙端" → "接收端/发射端"，或按硬件形态"手持端"），**"钥匙""锁""2026C"必须去**（判据④禁题词；注意 zigbee_uart_key 的 slug 与符号名是 _key 后缀，不在简介扫描面）
   - `filter`：能力方向 = 数据滤波（去"出身 2026C 题"）
2. **uwb_uart 代码注释**："旧钥匙数据"类注释清理为中性表述（如"旧帧数据"），零逻辑改动。
3. **删注册表**：EXCEPTION_REGISTRY 删除 6 条；全库测试跑绿。
4. **CONTEXT.md**：无词表变更预期（词表单源未动）；如 rewrite 中碰到词表误伤（能力词被误禁）→ 按白名单机制补 CAPABILITY_WORDS，记工单。

## 文件边界

- library/modules/config / debug_uart / zigbee_uart / zigbee_uart_key / filter 的 manifest.json（description）
- library/modules/uwb_uart/code/* 注释（仅注释）
- tests/test_module_universality.py（删 6 条注册表条目）
- **不动**：src/* 生成链路、其他模块内容

## 实施记录（2026-08-12）

**简介重写（5 条，update_module_description 全流程——判据④ 机械预检 + AI 校验当门禁）**：按四要素重写，去题号/年份/题名，能力方向点明，提交批 7bfd72d（config）/ 67a9475（filter）/ b78a334（zigbee_uart_key）/ 2215206（zigbee_uart）/ 474ae9f（debug_uart），仅 manifest description 行：
- `config`：集中外设配置头——引脚映射（UART/GPIO/LED/蜂鸣器/DIP）、中断阈值/超时、滤波窗口统一声明（去"2026C 数字钥匙题专用"）
- `debug_uart`：调试串口 + 单字符命令（去"2026C 门锁端"）
- `zigbee_uart` / `zigbee_uart_key`：收发两端实现——"门锁端/钥匙端"→"接收端/发射端"，端侧语义保留换通用表述，"钥匙""锁""2026C"全去（_key 后缀 slug/符号不在简介扫描面）
- `filter`：数据滤波（去"出身 2026C 题"）

**代码注释中性化（6 模块，随 474ae9f，零逻辑改动）**：uwb_uart（"旧钥匙数据"→"旧帧数据"）+ zigbee_uart / zigbee_uart_key（"门锁端/钥匙端"→"接收端/发射端"、"钥匙端 DIP-4 值"→"发射端 DIP-4 值"）——30 插入/30 删除全注释行，git diff 确认无代码行变更。

**EXCEPTION_REGISTRY 清空（本批工作区）**：tests/test_module_universality.py 删除 config / debug_uart / zigbee_uart / zigbee_uart_key / filter / uwb_uart 六条，docstring 更新为"02~06 清理"并补"已清理移除"记录；注册表空 = 全库无题词，工单 01 红证初始 11 条全部出清，普适化目标存量侧闭环。

**验证**：
1. pytest 全量 1095 绿（test_module_universality 6 通过——注册表空条目不变量 + find_topic_word_hits 全库 description + .c/.h 零命中）。
2. mypy src 32 文件干净。
3. 五条简介提交即过 update_module_description 全流程（机械预检 + AI 校验，2026-08-12 提交批）。

**遗留 → 工单 08（本批入库）**：config 简介 AI 校验通过后，代码侧实证 2026C 决策参数（判据④ 禁的专用判定参数）：config.h `THR_UNLOCK_ENTER/EXIT`（130/140cm）、`THR_WELCOME_ENTER/EXIT`（230/240cm）、`THR_SENSING_MAX`（430cm）、`TAGID_MASK`（0x0F）、`FOV_HALF_ANGLE`（45°）、`ZIGBEE_TIMEOUT_MS`（500ms）、`TAG_TIMEOUT_MS`（3000ms）为 2026C 门禁场景决策参数，按 ADR 0009 应剥离进生成骨架，模块只留纯驱动形态集中引脚配置——另立工单 08-config-decision-params。

## 验收

- [x] pytest 全绿：EXCEPTION_REGISTRY 6 条已删、全库无题词命中（`find_topic_word_hits` 全库扫描 = 空）、其余测试无回归。
- [x] mypy src 干净。
- [ ] 五条简介判据四要素齐（能力方向在、无题号/年份/题名），update_module_description 全流程通过（机械 + AI）。
- [ ] uwb_uart 仅注释改动，编译不受影响（stm32 线任意一产物编译验证可选——注释零风险，至少确认无代码行变更）。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
