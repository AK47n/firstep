## Problem Statement

`ball_detect`（球检测）这个命名绑定「球」这个具体视觉对象，但它实际是「主控侧解析 K230 串口坐标帧」的接收端。k230 视觉副控特性（PR #101-104）落地后，k230 模块依赖它，读起来是「k230 视觉副控 → ball_detect 球检测」，命名过窄、暴露身份错位——它输出的是一帧目标的中心坐标 + 边界框，与检测对象是球还是别的无关。

## Solution

单纯重命名 `ball_detect` → `coord_detect`（坐标检测），内容与解析逻辑一字不改、不合并 `digit_uart`。命名反映「检测目标并输出坐标」的通用职责。

## Implementation Decisions

- **slug / 目录**：`ball_detect` → `coord_detect`（`library/modules/coord_detect/`）
- **文件**：`ball_detect_stm32.{c,h}` → `coord_detect_stm32.{c,h}`、`ball_detect.{c,h}` → `coord_detect.{c,h}`（mspm0 版）
- **C 符号**：`BallResult` → `CoordResult`、`ball_result` → `coord_result`、`ball_detect_{init,flush,rx_handler,parse}` → `coord_detect_*`、`ball_rx_{byte_count,overflow,error}` → `coord_rx_*`、`BALL_RX_BUF_SIZE` → `COORD_RX_BUF_SIZE`、`parse_ball_line` → `parse_coord_line`；静态通用助手（`get_field`/`my_atoi`/`my_atof`/`rx_buf`/`rx_head`/`rx_tail`）保持
- **引脚宏与角色**：`BALL_DETECT_UART*` → `COORD_DETECT_UART*`（pin_config.h + manifest pins id/macros）
- **契约单源**（`src/contest_generator/k230_render.py`）：`BALL_FRAME_FIELDS` → `COORD_FRAME_FIELDS`、`BALL_FRAME_FORMAT` → `COORD_FRAME_FORMAT`、`render_ball_frame` → `render_coord_frame`、占位符 `ball_frame_format` → `coord_frame_format`、`BALL_FRAME_PREFIX` → `COORD_FRAME_PREFIX`
- **帧前缀 `'B'` 保持不动**——协议字节与模块 slug 是两套命名空间（digit_uart 的 `--- frame ---` 帧头也不跟模块名绑定）；改帧前缀是协议变化，超出「重命名」范围。`COORD_FRAME_PREFIX` 的值仍为 `"B"`，注释说明「历史协议字节，重命名不改线上协议」
- **main.py 模板**：占位符 `{{ball_frame_format}}` → `{{coord_frame_format}}`；`BALL_THRESHOLD` → `COLOR_THRESHOLD`（它是色块追踪的颜色阈值，非「球」专属，语义同步修正）；注释 `ball_detect` → `coord_detect`
- **依赖与引用**：`k230/manifest.json` 的 `dependencies` → `["coord_detect"]`；`digit_uart`/`pid` manifest notes 提及 `ball_detect` → `coord_detect`；`pinwriter.py` 的 `("BALL_DETECT_UART", "ball_detect_rx_handler")` → coord 版；`syscfg_instances.py` 的 `DIGIT_UART` 消费者 `("digit_uart", "ball_detect")` → `("digit_uart", "coord_detect")`
- **母版**：`stm32/pin_config.h`（BALL_DETECT_UART 宏）、`stm32/isr.c`（ball_detect_rx_handler 调用）、`mspm0/mspm0.syscfg`（DIGIT_UART 实例注释）同步
- **不改（保真）**：`sources/contest/**`、`library/references/**`、`docs/adr/**` 里的历史 ball_detect 引用（历史工程源 / 参考 / 决策记录）

## Testing Decisions

- 机械重命名，测试断言随引用同步：`tests/test_k230_artifact.py`（契约防漂移锁 + 生成断言）、`test_webapp.py`、`test_pins.py`、`test_syscfg_prune.py`、`test_pin_unlock_mspm0_same.py`、`test_syscfg_model.py`、`test_module_protocol_mspm0.py`、`test_default_layout.py`、`test_pin_unlock_uart.py`、`test_module_universality.py`、`tests/js/format-res-modules.test.mjs`
- 防漂移锁的「从 C 源机械提取 parse_coord_line 字段序」逻辑不变，只改符号名与源文件路径
- 验收 = 全量 Python 测试绿 + mypy 干净 + node:test 绿；生成侧 `[coord_detect]` / `[k230]` 双平台产物断言通过

## Out of Scope

- 合并 ball_detect + digit_uart 为一个统一 K230 串口解析模块
- 帧前缀 `'B'` 的协议变化（改 `'C'` 等）
- digit_uart 重命名（数字识别语义准确，保持）
- sources / references / adr 历史文件的改名

## Further Notes

- 用 `git mv` 改目录与文件，保留 git 历史（rename 识别）
- 全量 `grep ball_detect` / `BallResult` / `BALL_DETECT` 应只剩「刻意保留」的三类历史位置（sources/references/adr）与新 CHANGELOG 条目
