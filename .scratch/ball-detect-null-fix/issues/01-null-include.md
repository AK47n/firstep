# 01 — ball_detect 模块 NULL 未定义（UV4 必 8 错，模块库数据修复）

**What to build:** `library/modules/ball_detect/code/ball_detect_stm32.c` 使用 `NULL`（9 处）但未包含定义它的头文件——仅引 `headfile.h`（不含 NULL，已核实）与 `ball_detect_stm32.h`。今日 13:55 `98f8b0a`（mspm0 补录）给 `library/modules/pid/manifest.json` 加了 `ball_detect` 依赖后，任何选 pid 的 stm32 生成必拉入 ball_detect → Keil UV4 编译必 8 错。静态 include 检查只验"include 能否解析"、抓不到"漏 include"（UV4 真编译按设计抓到门禁）。修复：补 `#include <stddef.h>`（最小、只补 NULL 定义）。

**Status:** resolved（2026-08-11，验收闭环）

## 验收记录（2026-08-11）

- 复现红：`generate_check.py 2021F --platform stm32 --clarify clarify_2021F.json`
  真机全流程（DeepSeek 推荐 4 轮 done，6 模块 digit_uart/motor/pid/led_beep/
  zigbee_uart/zigbee_uart_key + pid 依赖拉入 ball_detect），UV4 编译 8 错全在
  ball_detect_stm32.c（:52,144,147,150,153,156,159,162 NULL 未定义），log 存
  `.scratch/real-run/keil_build_red_2021F.log`（尾行 8 Error(s), 1 Warning(s)）。
- 修复：`ball_detect_stm32.c` 首行补 `#include <stddef.h>`（仅此 1 行，含注释说明）。
- 复验绿：重生成同场景，UV4 全工程 **0 Error(s), 0 Warning(s)**，log 存
  `.scratch/real-run/keil_build_green_final.log`（ball_detect_stm32.c 在编译
  列表内无错警）。模块级独立对照：ARMCC `--c99 -DSTM32F10X_MD`（UV4 DFP 同参）
  编译该文件 8 错→0 错 0 警。
- pytest 1052 全绿 + `mypy src` 干净（基线 1052 同数，无回归）。
- 双平台不回归：mspm0 侧 ball_detect.c 未动；stm32 全量库清单未动（仅 .c 首行
  include）；`#include <stddef.h>` 在门禁 EXTERNAL_HEADERS 白名单内，include
  解析检查过。
- 补充：clarify_2021F.json +2 条（本次模型补问"装载/卸载检测方式"与"双车无线
  通信模块"，如实作答：题面未指定、按光电检测 + NRF24L01 处理，不影响选型）。
- 遗留发现（超工单边界，未动）：zigbee_uart 与 zigbee_uart_key 两模块文件同名
  （均 code/zigbee_uart.c）且都定义 zigbee_uart_init，双车协同场景模型双选时
  UV4 L6200E multiply defined（本次绿跑实测，drop 其一即过）——静态 include
  检查同盲区（两文件独立可解析），建议另立工单。绿证工程 main.c 两处 LLM 产物
  缺陷（:25 块注释内嵌套 /*、:12-13 未用 filter 变量）已脚手架修补后编译，门禁
  均已正确拦截（块注释嵌套属 generate_check 已查断言）。

## 现状（已核实）

- `ball_detect_stm32.c:1-2` 只 include `headfile.h` + `ball_detect_stm32.h`；`NULL` 出现于 `:52,144-162` 等 9 处（`get_field` 返回值判空）。
- `library/masters/stm32/ml_libs/headfile.h:4-15` 只 include 各 ml_*.h + stm32f10x.h，无 stddef.h / 无 NULL 定义（已 grep 核实）。
- 触发链：`library/modules/pid/manifest.json` `dependencies` 含 `ball_detect`（98f8b0a 加入）→ 2021F stm32 选 pid 必拉入 ball_detect 源文件 → UV4 编译 8 错（C 库下 `NULL` 未声明）。
- 与参考注入无关：工单 03 真机隔离跑（无 refs）同样 8 错；含 refs 跑同样 8 错。
- 门禁行为正确：这是静态 include 检查的盲区被 UV4 真编译补上，不是门禁 bug。
- 属模块库数据目录提交：`library/modules/` 走 `data:` 前缀惯例（见记忆 project-engineering-tool.md）。

## 实施（建议 tdd：先写 UV4 编译断言复现红，再改）

1. 复现（红）：选 pid 的 2021F stm32 生成 → UV4 编译，记录 8 错（错误内容含 `NULL` undeclared）。
2. 修复：`ball_detect_stm32.c` 第 1 行前补 `#include <stddef.h>`（最小改动；不选 headfile.h 收口方案——那是母版共享头，牵动面大）。
3. 复验（绿）：重生成同工程 → UV4 编译 0 错 0 警；`python -m pytest` 全绿（回归，模块库已有结构/清单测试应仍过）+ `mypy src` 干净。
4. 提交：`data:` 前缀（如 `data: ball_detect 补 stddef.h 定义 NULL（工单 ball-detect-null-fix/01）`）。

## 验收

- 修复前：选 pid 的 2021F stm32 生成工程 UV4 编译 8 错（记录 log 入库路径）。
- 修复后：同工程 UV4 编译 0 错 0 警（生成门禁产物检查 + include 解析全过）。
- pytest 全绿 + mypy src 干净。
- 双平台不回归：mspm0（ball_detect 的 mspm0 侧文件存在则编译路径照旧）、stm32 全量库清单照旧。

## 文件边界

`library/modules/ball_detect/code/ball_detect_stm32.c`（仅加一行 include）

**明确不动的：** `library/modules/pid/manifest.json`（依赖声明正确，不动）；headfile.h 及母版库；webapp.py / generate_check.py / 门禁逻辑；其余模块库文件。

## 关联

发现自工单 recommend-contract-parity/01 验收记录（2026-08-11，遗留发现），工单文件 `.scratch/recommend-contract-parity/issues/01-contract-parity.md`。
