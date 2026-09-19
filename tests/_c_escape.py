# -*- coding: utf-8 -*-
"""渲染产物里的 C 转义 → 人能读的文本（**测试共用的解码器**）。

## 为什么单独一件

检测程序把非 ASCII 字面量转义成 ASCII 转义序列（`hwcheck_recipe.escape_c_string`：
ARMCC 5.06 按本地代码页解析源文件，原样中文串会把收尾引号吞掉、整份 main.c 编不过）。
于是"产物里到底说了什么"这件事，测试得先把转义还原再断言。工单 04 起两个测试文件
各带一份**逐字相同**的解码器（`test_hwcheck.py` 的 `unescape_c_string` 与
`test_hwcheck_recipe.py` 的 `_unescape_c`），工单 05 给两份都加八进制支持时第三份
（C 语义解码器）也冒出来了——三份同形代码，改一处漏两处只是时间问题（评审抓到）。
所以单源在这里，两个测试文件各自 thin 地引用。

## 语义（刻意保守）

只认**字节转义**：`\\xNN`（历史写法，04 的产物）、`\\NNN`（三位八进制，05 起）、
以及 `\\n` 这类常见转义。其余反斜杠序列**原样保留**——因为调用方常常把**整份
main.c** 丢进来（里面还有 `"\\n"` 这种要被当成"两个字符"看的源码文本），把它们
解成控制字符会让"产物里有没有这句话"的断言跟着变味。

判"编译器会读出什么"（含 `\\x` 贪婪的完整 C 语义）是**另一个量具**，只在
`tests/test_hwcheck_recipe.py::_decode_like_c` 用——那是给转义本身的逐字节红证用的，
不是给"产物说了什么"的断言用的。两者别混。
"""

from __future__ import annotations

__all__ = ["decode_c_string"]

_SIMPLE_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "0": "\0",
    '"': '"', "'": "'", "\\": "\\",
}


def decode_c_string(text: str) -> str:
    """把一段（可能含转义的）产物文本还原成人能读的字符。"""
    out = bytearray()
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char != "\\" or index + 1 >= length:
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        nxt = text[index + 1]
        if nxt == "x" and index + 3 < length:
            digits = text[index + 2:index + 4]
            try:
                out.append(int(digits, 16))
                index += 4
                continue
            except ValueError:
                pass
        if nxt in "01234567" and index + 3 < length:
            digits = text[index + 1:index + 4]
            if all(digit in "01234567" for digit in digits):
                out.append(int(digits, 8) & 0xFF)
                index += 4
                continue
        if nxt in _SIMPLE_ESCAPES:
            out.extend(_SIMPLE_ESCAPES[nxt].encode("utf-8"))
            index += 2
            continue
        out.extend(char.encode("utf-8"))
        index += 1
    return out.decode("utf-8", errors="replace")
