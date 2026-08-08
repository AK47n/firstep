"""C 源码词法层 —— 机械切分文本，不判语义。

围栏剥离 / 注释与字符串切分 / 引号 include 提取 / 顶层 #define 扫描的唯一
出处。接口全部是"字符串进、字符串出（或元组列表出）"，不碰盘上文件——
骨架自检与生成门禁共用同一份实现，杜绝逐字重复（判例：围栏正则曾两处定义、
注释剥离器两义并存，改一处忘另一处即分叉）。

不做的事：调用形态识别（"名字后跟 ( 是不是函数调用"）是骨架自检的语义
判断，归 skeleton.py（_DECL_OR_DEF_RE 等）；这里只做任何 C 源文本都需要
的机械切分。
"""

from __future__ import annotations

import re

# Markdown 代码围栏行（``` / ~~~，可带语言标注）：LLM 输出最常见的传输层包裹
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})[a-zA-Z0-9_-]*\s*$")

# 引号 include 提取（对 strip_comments(keep_preprocessor=True) 后的文本匹配）
_INCLUDE_QUOTED_RE = re.compile(r'#\s*include\s*"([^"]+)"')


def strip_code_fences(code: str) -> str:
    """剥离 LLM 输出的首尾代码围栏行（```lang / ~~~），其余原样。

    提示词要求输出纯 C，但模型偶尔仍用围栏包裹（判例：骨架带 ```c 围栏直接
    落盘 main.c，Keil 报 unrecognized token，连锁炸掉整个编译）。只剥首尾
    各一行围栏；无围栏原样返回；中间位置的围栏行不动（不是包裹形态，剥了
    反而丢信息）。
    """
    lines = code.splitlines(keepends=True)
    if not lines:
        return code
    if _FENCE_LINE_RE.match(lines[0]):
        lines = lines[1:]
    if lines and _FENCE_LINE_RE.match(lines[-1].rstrip("\r\n")):
        lines = lines[:-1]
    return "".join(lines)


def fence_line_indices(code: str) -> list[tuple[int, str]]:
    """含围栏的行：(1 起行号, 行文本（已 strip）)。

    与 strip_code_fences 同源：剥离看"首尾包裹形态"，这里看"任意围栏行"
    （生成门禁对绕过骨架阶段的 main.c 逐行报错，判例见 FencedMainCError）。
    """
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(code.splitlines(), 1):
        if _FENCE_LINE_RE.match(line):
            hits.append((i, line.strip()))
    return hits


def strip_comments(code: str, *, keep_preprocessor: bool = False) -> str:
    """去掉 C 注释（行/块）与字符串/字符字面量，只留代码形态。

    keep_preprocessor=True 时，行首 # 打头的预处理行整行原样保留（不剥其中
    字符串）——include 的文件名在引号里，普通字符串剥离会把它当字符串吞掉
    （判例：include 门禁扫描失败）。行首判定必须严格"i==0 或前一字符是换行"，
    不能用回退跳过空白的方式——第 2 行起的 # 行会被误判为不在行首（判例：
    pid.c 第 2 行 #include 被当字符串剥掉，include 门禁漏检）。默认
    keep_preprocessor=False 时 # 行按普通文本处理（调用形态提取用，注释 /
    字符串照剥）。
    """
    out: list[str] = []
    i = 0
    length = len(code)
    while i < length:
        char = code[i]
        nxt = code[i + 1] if i + 1 < length else ""
        if char == "/" and nxt == "/":  # 行注释
            end = code.find("\n", i)
            i = length if end == -1 else end + 1
        elif char == "/" and nxt == "*":  # 块注释（跨行一并跳过）
            end = code.find("*/", i + 2)
            i = length if end == -1 else end + 2
        elif keep_preprocessor and char == "#" and (i == 0 or code[i - 1] == "\n"):
            # 预处理行透传：整行原样保留（含引号里的头文件名 / 宏体）
            end = code.find("\n", i)
            end = length if end == -1 else end + 1
            out.append(code[i:end])
            i = end
        elif char in ('"', "'"):  # 字符串 / 字符字面量（含转义）
            quote = char
            i += 1
            while i < length and code[i] != quote:
                if code[i] == "\\":
                    i += 1
                i += 1
            i += 1
        else:
            out.append(char)
            i += 1
    return "".join(out)


def extract_quoted_includes(stripped: str) -> list[str]:
    """引号 include 的头文件名（对 strip_comments(keep_preprocessor=True)
    后的文本用——# 行透传后这里才找得到文件名）。"""
    return _INCLUDE_QUOTED_RE.findall(stripped)


def top_level_defines(code: str) -> dict[str, tuple[str, int]]:
    """无条件顶层 #define 清单：{宏名: (规范化值, 行号)}。

    只收不在任何 #if/#ifdef/#ifndef 块内的 #define——include guard 的定义
    在 #ifndef 块内（深度 1）天然排除；条件块里可能生效也可能不生效的宏
    跳过（宁可放过、不可误杀，编译器的 warning 兜底）。同一文件 #undef
    后再定义的不收（合法覆盖模式）。函数宏名字取到左括号前，参数表并入
    值参与文本比较。反斜杠续行在预处理行内合并。
    """
    stripped = strip_comments(code, keep_preprocessor=True)
    lines = stripped.split("\n")
    defines: dict[str, tuple[str, int]] = {}
    undefed: set[str] = set()
    depth = 0
    i = 0
    while i < len(lines):
        text = lines[i].strip()
        lineno = i + 1
        if not text.startswith("#"):
            i += 1
            continue
        while text.endswith("\\") and i + 1 < len(lines):  # 续行合并
            i += 1
            text = text[:-1] + " " + lines[i].strip()
        if text.startswith("#if"):
            depth += 1
        elif text.startswith("#endif"):
            depth = max(0, depth - 1)
        elif text.startswith("#undef"):
            m = re.match(r"#\s*undef\s+([A-Za-z_]\w*)", text)
            if m:
                undefed.add(m.group(1))
        elif text.startswith("#define") and depth == 0:
            m = re.match(r"#\s*define\s+([A-Za-z_]\w*)", text)
            if m:
                name = m.group(1)
                if name not in undefed:
                    value = re.sub(r"\s+", " ", text[m.end():].strip())
                    defines[name] = (value, lineno)
        i += 1
    return defines
