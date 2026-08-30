"""K230 视觉副控 .py 渲染 —— CSV 帧契约单源 + 模板渲染纯函数。

K230 侧发送脚本与主控侧解析（library/modules/coord_detect/code/
coord_detect_stm32.c 的 parse_coord_line、library/modules/digit_uart/code/
digit_uart.c 的 parse_digit_line）吃同一份 CSV 帧契约：字段顺序 / 分隔符 /
无检测帧 / 波特率**只在此定义一处**——.py 渲染从这里取，不与主控侧解析各
抄一份（防漂移测试从 C 源机械提取字段序与本模块常量比对，tests/
test_k230_artifact.py，改 C 不改这里或反之即红）。模块 manifest 的
python_artifact 模板（工单 k230-vision-copilot/01）只引用占位符，不重抄
帧格式；渲染 = 占位符 ← 契约值的纯字符串替换。

纯函数层：不碰盘、不 import 生成流程——generator 写侧调用，测试内存直构。
"""

from __future__ import annotations

# 坐标检测帧字段顺序（与 coord_detect_stm32.c parse_coord_line 的 get_field 序
# 严格一致：1=cx 2=cy 3=confidence 4=x1 5=y1 6=x2 7=y2）
COORD_FRAME_FIELDS = ("cx", "cy", "confidence", "x1", "y1", "x2", "y2")

# 帧前缀 / 无检测帧 / 串口波特率（C 侧 ml_uart.c 全库角色约定 115200）。
# 前缀值 "B" 是历史协议字节（模块重命名 coord-detect-rename/01 不改线上协议）：
# 协议字节与模块名是两套命名空间，digit_uart 的 "--- frame ---" 帧头也不跟模块
# 名绑定——改前缀属于协议变化，超出「重命名」范围。
COORD_FRAME_PREFIX = "B"
NO_DETECT_FRAME = "N"
UART_BAUDRATE = 115200

# B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2> —— 由字段序派生（单源）
COORD_FRAME_FORMAT = COORD_FRAME_PREFIX + "," + ",".join(
    "{" + field + "}" for field in COORD_FRAME_FIELDS
)

# 数字识别帧（AI 检测，工单 k230-digit-vision/01）——与 digit_uart 双平台
# （stm32 digit_uart.c / mspm0 digit_uart_mspm0.c）parse_digit_line 的
# get_field 序同源：解析端只消费槽位 0/1/6/7 = label/confidence/cx/cy
# （DIGIT_FRAME_CONSUMED_INDICES），其余字段（x1/y1/x2/y2/w/h）为契约
# 占位——索引按逗号位置数，缺一不可。帧头以 "---" 开头（解析端
# line_buf[0..2]=='-' 判帧界），数据行结束帧尾为空行；一次 parse 可能跨
# 多帧，解析端取目标数最多的最佳帧（count=0 的无检测帧不参与比较）。
DIGIT_FRAME_HEADER = "--- frame {n} | {m} targets ---"
DIGIT_FRAME_LINE_FIELDS = (
    "label", "confidence", "x1", "y1", "x2", "y2", "cx", "cy", "w", "h",
)
# 数据行格式由字段序派生（COORD 同模式）：confidence 两位小数特殊化
# {:.2f}，其余字段 {}——改字段序不同步格式即 CSV 列错位，派生保证
# 位置↔字段名映射始终一致（解析端按逗号位置消费）。
DIGIT_FRAME_LINE_FORMAT = ",".join(
    "{" + field + (":.2f" if field == "confidence" else "") + "}"
    for field in DIGIT_FRAME_LINE_FIELDS
)
# 解析端消费槽位（CSV 按逗号位置数）：label/confidence/cx/cy
DIGIT_FRAME_CONSUMED_INDICES = (0, 1, 6, 7)
# 无检测帧：帧头 m=0 + 空行帧尾；count=0 帧不参与批量最佳帧比较
# （best_count > 0 才替换），无检测帧永不污染对端结果。
DIGIT_FRAME_NO_DETECT_COUNT = 0


def render_coord_frame(
    cx: int, cy: int, confidence: float, x1: int, y1: int, x2: int, y2: int
) -> str:
    """坐标检测帧文本：字段按 COORD_FRAME_FIELDS 契约序落位。"""
    return COORD_FRAME_FORMAT.format(
        cx=cx, cy=cy, confidence=confidence, x1=x1, y1=y1, x2=x2, y2=y2
    )


def render_no_detect_frame() -> str:
    """无检测帧文本。"""
    return NO_DETECT_FRAME


def render_digit_frame_header(n: int, count: int) -> str:
    """DIGIT 帧头文本：n = 帧序号（发送侧自增），count = 目标数；
    count = DIGIT_FRAME_NO_DETECT_COUNT（0）即无检测帧——解析端 count=0
    帧不参与批量最佳帧比较，空行帧尾结束本帧（语义锁见防漂移测试）。"""
    return DIGIT_FRAME_HEADER.format(n=n, m=count)


# 模板占位符词汇表（渲染唯一实现）：{{name}} ← 契约值。字符串 replace 而非
# str.format——COORD_FRAME_FORMAT / DIGIT_FRAME_HEADER 本身含 {} 花括号
# （format 字段），format 替换会二次解释破坏花括号，replace 不解释。
_TEMPLATE_VARS: dict[str, str] = {
    "coord_frame_format": COORD_FRAME_FORMAT,
    "no_detect_frame": NO_DETECT_FRAME,
    "uart_baudrate": str(UART_BAUDRATE),
    "digit_frame_header": DIGIT_FRAME_HEADER,
    "digit_frame_line": DIGIT_FRAME_LINE_FORMAT,
}


def render_python_artifact(template: str) -> str:
    """python_artifact 模板渲染：{{coord_frame_format}} / {{no_detect_frame}} /
    {{uart_baudrate}} / {{digit_frame_header}} / {{digit_frame_line}} ← 契约值；
    无占位符 = 原样透传（纯文本模板逐字节不变）。"""
    rendered = template
    for name, value in _TEMPLATE_VARS.items():
        rendered = rendered.replace("{{" + name + "}}", value)
    return rendered
