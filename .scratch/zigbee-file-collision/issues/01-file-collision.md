# 01 — zigbee_uart / zigbee_uart_key 同名文件与符号冲突（双选 UV4 L6200E）

**What to build:** 双车协同场景模型同时选中 zigbee_uart + zigbee_uart_key 时，两模块文件同名（均 `code/zigbee_uart.c` / `code/zigbee_uart.h`）且都定义 `zigbee_uart_init` —— 生成工程 UV4 编译 L6200E multiply defined（绿跑实测，drop 其一即过）；静态 include 检查同盲区。目标：双选可编译，单选照旧。

**Status:** resolved（2026-08-11，验收闭环）

## 验收记录（2026-08-11）

- **方案定重命名**（工单决策规则）：两模块为收发两端实现（锁端 RX 状态机 vs 钥匙端 TX 发送），非"同源 + 按键逻辑"，且验收要求"两个模块条目健康"指向保留两条目。key 版文件/符号唯一化，锁端不动。
- 修复内容：`zigbee_uart_key/code/zigbee_uart.{c,h}` → `zigbee_uart_key.{c,h}`；符号 `zigbee_uart_init`→`zigbee_uart_key_init`、`zigbee_send_id`→`zigbee_uart_key_send_id`；头保护宏 `_key_fob_zigbee_uart_h_`→`_zigbee_uart_key_h_`；manifest files 同步。锁端 `zigbee_uart`（`zigbee_uart_init`/`zigbee_rx_handler`）全库唯一，不动。
- 测试（`tests/test_module_collision.py`，4 用例）：全库跨模块重复路径不变量 + 双选生成（真实库+真实母版，产物文件/定义符号/uvprojx 注册三断言）+ 单选回归 parametrize 两模块。红证：模拟重命名前数据形态，守卫全部拦截（重复路径 `code/zigbee_uart.c/.h` + `zigbee_uart_init` 重复定义）。
- **pytest 1056 全绿**（基线 1052 + 新增 4，无回归）；`mypy src` 干净（32 文件，src 零改动）。
- **真机 UV4 命令行构建三工程全 0 Error(s) 0 Warning(s)**（UV4 `-j0 -b`，日志存 `.scratch/real-run/keil_build_zigbee_*.log`）：
  - `out_zigbee_dual`（config+zigbee_uart+zigbee_uart_key 双选）：0/0，日志确认 `compiling zigbee_uart.c...` 与 `compiling zigbee_uart_key.c...` **两个源文件都在编译列表**——正是修复前 L6200E 的场景，修复后全过。
  - `out_zigbee_uart_single`（单选锁端）：0/0；`out_zigbee_key_single`（单选钥匙端）：0/0。
- AI 校验（真实 DeepSeek，`validate_description` 直调、指向仓库内 `library/modules`）：zigbee_uart 2/2 一致；zigbee_uart_key 3 跑 2 绿 1 黄（首次对"简介题面语境 vs 泛用发送代码"边界判黄，简介未改动、复跑连绿——非本工单引入）。
- 不动 `library/backfill_2026c.py`（历史一次性补录脚本：指向 ADR 0008 迁移前的 `~/.contest_generator/modules` 旧库路径 + skip-on-exist，工单边界外）。
- 遗留观察（超出本工单边界，未动）：①生成器五道静态门不查跨模块同名文件/符号，同类冲突值得生成侧兜底（manifest files 跨模块查重即可实现），见下方"观察"；②key 版注释写 "UART1" 与共用 config 宏 `ZIGBEE_UART=UART_3` 不符（源材料 key_fob 另立 config.h 覆盖为 UART1），库内语义未定，config 模块边界外未动。

## 现状（已核实）

- 出处：ball_detect-null-fix 工单验收遗留（2026-08-11 绿跑实测，见该工单验收记录）。
- 两模块库内目录：`library/modules/zigbee_uart/` 与 `library/modules/zigbee_uart_key/`，各自 manifest.json 声明 `code/zigbee_uart.c`（+ `.h`）——**相对路径同名**，生成器复制进同一工程即互相覆盖、符号重复定义。
- 函数符号 `zigbee_uart_init` 两模块都有定义；头文件同名 `zigbee_uart.h` 同覆盖。
- 静态门禁（include 解析校验）只验 `#include` 能解析，不验同名文件/符号冲突——与 ball_detect 漏 include 同盲区。
- 双车协同 = 主从双车各带一块无线模块（该场景出现于 2026C 数字钥匙题），模型双选是真实路径。

## 实施

1. **先探查再定方案**（读两模块 `code/` 全部文件 + manifest）：判断 key 版与 uart 版代码关系——同源（key 版 = uart 版 + 按键逻辑）→ 首选**合并为单模块**（如 zigbee_uart 加按键能力开关，或删 key 版让 uart 版补按键，只留一份 manifest，双车同模块）；实现差异大 → **重命名**（key 版文件 + 内部符号统一 `_key` 后缀，两模块各自唯一）。**→ 已定：重命名**（两模块为收发两端实现：锁端 RX 状态机 vs 钥匙端 TX 发送，非同源；见验收记录）。
2. 方案确定后按仓库惯例改库（数据改动 + 模块简介一致性，结构校验走既有 add/save_manifest 路径），生成侧不改。
3. 测试：生成用例覆盖双选（两模块同选 → 产物无同名文件、符号唯一）；单选回归。
4. 若选择重命名路径且认为同类冲突值得生成侧兜底，可在工单评论记录观察（本工单不扩生成器范围）。**→ 已记录（见下方"观察"）**。

## 观察（本工单不扩生成器范围）

生成器五道静态门（_check_module_files / _check_main_calls / _check_module_self_include / _check_unresolved_includes / _check_macro_conflicts）不查**跨模块**同名文件与重复符号——本工单的冲突就是全部门禁静默通过、UV4 链接期才炸（L6200E）。若后续扩生成侧兜底，成本最低的形态：`resolve_selection` 后对所选 manifests 的 (platform, files 相对路径) 集合查重（manifest files 已是库内单源），符号级查重需轻量 C 词法、收益有限（同类冲突大概率同时撞文件名）。库内防回退已由 `tests/test_module_collision.py` 的不变量测试守住。

## 验收

- 真机（或 ARMCC 对照，参 ball_detect 经验：`--c99 -DSTM32F10X_MD`）：双选 zigbee_uart + zigbee_uart_key 生成工程 UV4 **0 Error(s) 0 Warning(s)**；单选各模块照旧 0 错。
- pytest 全绿 + mypy src 干净（若只动库数据与测试，src 零改动）。
- 库内两个模块条目健康（AI 校验/结构校验过，简介与代码一致）。

## 文件边界

`library/modules/zigbee_uart/`、`library/modules/zigbee_uart_key/`、`tests/`（新增生成用例）

**明确不动的：** 生成器/门禁/静态检查逻辑（本工单只修库内冲突）；其他模块。
