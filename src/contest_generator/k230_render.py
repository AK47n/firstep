"""K230 视觉副控 .py 渲染 —— CSV 帧契约单源 + 模板渲染纯函数。

K230 侧发送脚本与主控侧解析（library/modules/coord_detect/code/
coord_detect_stm32.c 的 parse_coord_line）吃同一份 CSV 帧契约：字段顺序 /
分隔符 / 无检测帧 / 波特率**只在此定义一处**——.py 渲染从这里取，不与主控
侧解析各抄一份（防漂移测试从 C 源机械提取字段序与本模块常量比对，tests/
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


# 模板占位符词汇表（渲染唯一实现）：{{name}} ← 契约值。字符串 replace 而非
# str.format——COORD_FRAME_FORMAT 本身含 {} 花括号（format 字段），format
# 替换会二次解释破坏花括号，replace 不解释。
_TEMPLATE_VARS: dict[str, str] = {
    "coord_frame_format": COORD_FRAME_FORMAT,
    "no_detect_frame": NO_DETECT_FRAME,
    "uart_baudrate": str(UART_BAUDRATE),
}


def render_python_artifact(template: str) -> str:
    """python_artifact 模板渲染：{{coord_frame_format}} / {{no_detect_frame}} /
    {{uart_baudrate}} ← 契约值；无占位符 = 原样透传（纯文本模板逐字节不变）。"""
    rendered = template
    for name, value in _TEMPLATE_VARS.items():
        rendered = rendered.replace("{{" + name + "}}", value)
    return rendered
