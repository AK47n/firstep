# 01 — 数字帧契约单源扩展

**要做什么：** k230_render.py 增加 DIGIT 数字识别帧契约常量（帧头 / 数据行字段序 / 无检测行为）与对应模板占位符，让数字模板只引用占位符、不重抄字面量；防漂移测试从 digit_uart.c（stm32 + mspm0 双平台）机械提取解析字段序比对锁定——任何一侧改动不同步即红（与 B 帧先例同构）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `DIGIT_FRAME_HEADER` / `DIGIT_FRAME_LINE_FIELDS` 契约常量在 k230_render.py 单源定义（帧头含 `{}` 序号占位、数据行 10 字段 label,confidence,x1,y1,x2,y2,cx,cy,w,h，字段 0/1/6/7 为解析消费位）
- [x] `{{digit_frame_header}}` / `{{digit_frame_line}}` 加入模板变量词汇表（replace 渲染不二次解释花括号，波特率复用 `{{uart_baudrate}}`）
- [x] 防漂移测试：从 digit_uart.c（stm32 + mspm0 双平台版本）机械提取 get_field 序 → 与契约字段序比对（(0,1,6,7) = label/confidence/cx/cy）
- [x] 渲染函数行为测试：占位符渲染后帧文本可被真实解析逻辑对齐（帧头 `---` 前缀 + 空行帧尾语义）
- [x] 既有 B 帧测试全部保持绿（契约/防漂移/渲染零回归）

**实现备注（code-review 双轴驱动，2026-08-30）：**

- `DIGIT_FRAME_LINE_FORMAT` 由字段序派生（COORD 同模式），confidence `{:.2f}` 特殊化——spec 评审指出手写字面量与 FIELDS 不同步会导致 CSV 列错位且无测试捕获，派生 + 位置映射测试（占位符序列 == 字段序列）锁死。
- 新增 `DIGIT_FRAME_CONSUMED_INDICES = (0,1,6,7)` 消魔法索引（standards 评审 Primitive Obsession）；主锁测试按该常量取契约槽位。
- 无检测帧单源：`DIGIT_FRAME_NO_DETECT_COUNT = 0` + `render_digit_frame_header(n, count)`（count=0 即无检测帧）；C 侧语义防漂移锁：帧头重置 count=0 → 空行帧尾 → 批量最佳帧只替换 `best_count > 0` 的帧（无检测帧永不污染对端）。
- `_parse_fn_body(source, signature)` 共享切片 helper 替换 coord/digit 两份重复体（standards 评审 Duplicated Code）。
- 全部 49 用例绿（含既有 B 帧契约/防漂移/生成层零回归）；全量测试 2912 passed。
