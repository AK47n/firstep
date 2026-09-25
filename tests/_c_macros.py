# -*- coding: utf-8 -*-
"""驱动级测试共用的 **C 源码机械解析器**：宏表 / 整数宏求值 / 顶层函数体。

## 为什么单独立一份

`driver-defect-fixes/01`（joystick）与 `03`（hx711）各自要"**独立复算**驱动里的常量、
按函数体断言行为"，于是两份测试文件里各写了一份逐字相同的 `_c_defines` / `_c_int`
（`_c_functions` 先只在 joystick 那份里）——双轴评审当场点名「Duplicated Code，
仓库已有共用助手位」。

单源在这里，两个测试文件各自 thin 地引用（照 `tests/_c_escape.py` 的先例：
那份也是三个文件各一份逐字相同的解码器之后抽出来的）。

## 语义（刻意保守）

* `c_defines` **只认单行 `#define`**（续行宏不解析——本仓驱动里的常量宏都是单行），
  行尾 `/* … */` 注释剥掉；重复定义后者覆盖前者。
* `c_int` 只解引用**同一个字典里**的宏名，十六进制/无符号后缀先归一，最后过一遍
  字符白名单（`0-9 + - * / ( )`）再 `eval`——喂进来的表达式只可能是四则运算。
  **它是给测试"自己算一遍"用的**，不是实现的复读机。
* `c_functions` 按**签名行**锚定顶层函数体（从签名到顶格 `}`），刻意不用
  `text.split(名字, 1)[1]` 那种取「名字之后的全部文本」的写法——那会让后面函数的
  断言被前面函数的文本喂绿（评审抓到过）。
"""
from __future__ import annotations

import re


def c_defines(*texts: str) -> dict[str, str]:
    """抓 C 源里 `#define NAME <表达式>`（行尾注释剥掉），供独立复算。"""
    found: dict[str, str] = {}
    for text in texts:
        for match in re.finditer(
            r"^[ \t]*#define[ \t]+([A-Za-z_]\w*)[ \t]+(.+?)[ \t]*$", text, re.MULTILINE
        ):
            found[match.group(1)] = match.group(2).split("/*")[0].strip()
    return found


def c_int(defines: dict[str, str], name: str, rounds: int = 8) -> int:
    """把 `#define` 的整数算术表达式算成整数（**测试自己算**，不照抄实现）。"""
    expr = defines[name]
    for _ in range(rounds):
        for ident in sorted(defines, key=len, reverse=True):
            if ident != name:
                expr = re.sub(rf"\b{ident}\b", f"({defines[ident]})", expr)
    expr = re.sub(
        r"\b0[xX][0-9A-Fa-f]+[uUlL]*",
        lambda m: str(int(m.group(0).rstrip("uUlL"), 16)),
        expr,
    )
    expr = re.sub(r"(?<=[0-9])[uUlL]+\b", "", expr).replace(" ", "")
    assert re.fullmatch(r"[0-9+\-*/()]+", expr), f"{name} 的表达式不是纯算术：{expr!r}"
    return int(eval(expr))  # noqa: S307 —— 上面已白名单校验，只可能喂算术字面量


def c_functions(text: str) -> dict[str, str]:
    """按函数名切出**顶层函数体**（从签名行到顶格 `}`）。"""
    found: dict[str, str] = {}
    for match in re.finditer(
        r"^[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;{]*\)\s*\{", text, re.MULTILINE
    ):
        end = text.find("\n}", match.end())
        if end != -1:
            found[match.group(1)] = text[match.start():end]
    return found
