# 01 — 重命名 ball_detect → coord_detect（坐标检测）

**What to build:** `ball_detect` 模块整体重命名为 `coord_detect`（坐标检测），解析逻辑与协议一字不改、不合并 `digit_uart`。重命名后全库 `grep ball_detect` 只应剩「刻意保留」的三类历史位置（sources / references / adr）与新 CHANGELOG 条目，生成 `[coord_detect]` / `[k230]` 双平台产物正常。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] `library/modules/ball_detect/` → `coord_detect/`（git mv 保留历史），文件 `ball_detect_stm32.{c,h}`/`ball_detect.{c,h}` → `coord_detect_*`，manifest slug 同步
- [x] C 符号全改（stm32 + mspm0 两版）：`BallResult`→`CoordResult`、`ball_result`→`coord_result`、`ball_detect_{init,flush,rx_handler,parse}`→`coord_detect_*`、`ball_rx_{byte_count,overflow,error}`→`coord_rx_*`、`BALL_RX_BUF_SIZE`→`COORD_RX_BUF_SIZE`、`parse_ball_line`→`parse_coord_line`；静态助手 `get_field`/`my_atoi`/`my_atof`/`rx_buf`/`rx_head`/`rx_tail` 保持
- [x] 引脚宏/角色：`BALL_DETECT_UART*` → `COORD_DETECT_UART*`（stm32 pin_config.h + manifest pins id/macros，mspm0 syscfg 实例名 DIGIT_UART 不动）
- [x] 契约单源 `k230_render.py`：`BALL_FRAME_FIELDS`→`COORD_FRAME_FIELDS`、`BALL_FRAME_FORMAT`→`COORD_FRAME_FORMAT`、`BALL_FRAME_PREFIX`→`COORD_FRAME_PREFIX`（**值 `"B"` 保持**，注释说明「协议字节与模块名解耦」）、`render_ball_frame`→`render_coord_frame`、占位符 `ball_frame_format`→`coord_frame_format`
- [x] `k230/code/main.py`：占位符 `{{ball_frame_format}}`→`{{coord_frame_format}}`、`BALL_THRESHOLD`→`COLOR_THRESHOLD`、注释 `ball_detect`→`coord_detect`
- [x] 引用同步：`k230/manifest.json` 依赖 → `["coord_detect"]`；`digit_uart`/`pid` manifest notes；`pinwriter.py` `("BALL_DETECT_UART","ball_detect_rx_handler")`→coord 版；`syscfg_instances.py` `("digit_uart","ball_detect")`→`("digit_uart","coord_detect")`；母版 `stm32/isr.c`（rx_handler 调用）+ `mspm0/mspm0.syscfg`（注释）
- [x] 测试同步：`test_k230_artifact.py`（防漂移锁源路径 + 符号 + 生成断言）、`test_webapp.py`、`test_pins.py`、`test_syscfg_prune.py`、`test_pin_unlock_mspm0_same.py`、`test_syscfg_model.py`、`test_module_protocol_mspm0.py`、`test_default_layout.py`、`test_pin_unlock_uart.py`、`test_module_universality.py`、`tests/js/format-res-modules.test.mjs`
- [x] 全量 Python 测试绿 + mypy 干净 + node:test 绿；CONTEXT.md 词条同步 + CHANGELOG 新条目；`grep -ri ball_detect`（排除 .scratch/sources/references/docs）零命中

## 实施记录（2026-08-17）

- 分支 `coord-detect-rename`（基于最新 main）。git mv 目录 + 4 文件（rename 全识别）。
- 全量 1776 绿（52s）、`python -m mypy src` 46 文件干净、`node --test tests/js/*.test.mjs` 17 绿。
- 验收 grep：ball_detect / BallResult / BALL_DETECT / BALL_FRAME / BALL_RX / parse_ball_line / render_ball_frame / ball_frame_format / BALL_THRESHOLD 在 src / tests / library（除 references）/ 根 md 零命中；残留仅 references（保真区）+ 新 CHANGELOG 条目 + 陈旧缓存文件（.pyc/.mypy_cache/.pytest_cache，gitignore 内）。
- 保真决策：C 文件内「钢珠检测结果/钢珠中心坐标」注释保留（历史数据语义，照帧前缀 'B' 同口径——spec 只枚举符号改名，未列注释改写）；`coord_detect_stm32.c` 首行「工单 ball-detect-null-fix/01」连字符引用保留（.scratch 历史目录名不动，grep ball_detect 不命中连字符形式）。
- 已提交 2473391（+ post-commit 钩子自动 CHANGELOG a372eca），PR #105 已开（https://github.com/AK47n/firstep/pull/105）。
