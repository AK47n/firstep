# 02 — OLED 双平台共同小写 API（旧 API 保留）

**What to build:** 新增 `oled_show_text(line, column, text)` / `oled_show_number(line, column, number, length)` / `oled_refresh()` 三件套：stm32 落在母版 ml_oled（包一层，逐飞 OLED 写入即显示 refresh 为空实现），mspm0 落在 oled.c/h（映射到 16×8 字号、像素坐标）。旧 OLED_* 接口不动。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

- [x] stm32 母版 ml_oled.c/h 增三个包装函数
- [x] mspm0 oled.c/h 增三个包装函数（column→x*8、line→y*16、size=16）
- [x] 测试：两平台头都有三件套 + 旧 API 仍在
- [x] 真机双平台编译 0 错（stm32 UV4 + mspm0 gmake，编译矩阵 41/41 PASS）
- [x] pytest 全绿 + mypy src 干净

## Comments

- stm32 母版 ml_oled 可能是 GBK 编码：包装函数以 ASCII 追加，原文件字节不动。
- 共同 API 映射约定：line 0..3、column 0..15；mspm0 映射 x=column*8、y=line*16、字号 16。
- 编译矩阵 41/41 PASS（stm32 UV4 0 error/0 warning，mspm0 gmake 0 error，UART 模块仅 syscfg ovsRate 基线 warning）。
