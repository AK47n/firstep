"""C 源码词法层 —— 机械切分文本，不判语义。

围栏剥离 / 注释与字符串切分（iter_c_regions）/ 括号配对（match_bracket）/
空白注释跳读（next_significant）/ 引号 include 提取 / 顶层 #define 扫描的
唯一出处。接口全部是"字符串进、字符串出（或元组列表出）"，不碰盘上文件——
骨架自检与生成门禁共用同一份实现，杜绝逐字重复（判例：围栏正则曾两处定义、
注释剥离器两义并存，改一处忘另一处即分叉；skeleton 曾手写第二套注释/字符串
切分与括号配对，工单 C 深化吸收）。

不做的事：调用形态识别（"名字后跟 ( 是不是函数调用"）是骨架自检的语义
判断，归 skeleton.py（_DECL_OR_DEF_RE 等）；这里只做任何 C 源文本都需要
的机械切分。
"""

from __future__ import annotations

import re
from typing import Iterator, Literal

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


def strip_all_code_fences(code: str) -> str:
    """剥离 LLM 输出中**全部**围栏行（``` / ~~~，可带语言标注）。

    与 strip_code_fences 分工：那个只剥首尾包裹形态（中间围栏可能是原文信息，
    契约由 test_clex 钉死）；本函数剥全部围栏行——生成的 main.c 里任何围栏行
    都是 LLM 传输层噪声，C 代码本体不可能合法出现（skeleton 出稿兜底，
    判例：LLM 偶发三重围栏，strip_code_fences 剥首尾后仍残留一行，生成门禁
    400 阻断生成）。
    """
    return "".join(
        line
        for line in code.splitlines(keepends=True)
        if not _FENCE_LINE_RE.match(line.rstrip("\r\n"))
    )


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


# 词法区域类型：line_comment / block_comment / string / char /
# preprocessor（行首 # 整行）/ code（其余普通字符的连续段）
_RegionKind = Literal[
    "line_comment", "block_comment", "string", "char", "preprocessor", "code"
]


def _at_preprocessor_line_start(code: str, pos: int, indented: bool) -> bool:
    """'#' 位置是否行首。indented=True 允许前导空格/制表（骨架替换走查的
    透传语义——缩进 # 行里的宏体不能被当普通文本扫调用）；注意前导空白只能
    是空格/制表，不能跨换行——'\n'.isspace() 为 True，用 isspace 回退会把
    上一行行尾当空白吞掉（旧 skeleton 的 _at_line_start_after_ws 即因此
    只在文件首行生效）。False 严格"i==0 或前一字符是换行"（strip_comments
    的 pid.c 判例语义，见其 docstring）。
    """
    if indented:
        j = pos
        while j > 0 and code[j - 1] in (" ", "\t"):
            j -= 1
        return j == 0 or code[j - 1] == "\n"
    return pos == 0 or code[pos - 1] == "\n"


def _skip_literal(code: str, start: int) -> int:
    """从字符串/字符字面量起点跳到闭合引号之后（跳过转义；不闭合吃到结尾）。"""
    quote = code[start]
    i = start + 1
    n = len(code)
    while i < n and code[i] != quote:
        if code[i] == "\\":
            i += 1
        i += 1
    return min(i + 1, n)


def iter_c_regions(
    code: str,
    *,
    start: int = 0,
    preprocessor: bool = True,
    preprocessor_indented: bool = False,
) -> Iterator[tuple[_RegionKind, int, int]]:
    """注释/字符串/预处理行感知的机械切分：逐个产出 (kind, start, end)。

    六类区域：line_comment（// 到行尾含换行，不闭合吃到结尾）/ block_comment
    （/* */，不闭合吃到结尾）/ string / char（含转义，不闭合吃到结尾）/
    preprocessor（行首 # 打头的整行含换行）/ code（其余普通字符的连续段）。
    所有下游（注释剥离 / 括号配对 / 跳读 / 替换走查）共用这一份切分——
    skeleton 曾手写第二套（_match_paren / _match_brace / _skip_ws_and_comments
    等约 160 行），工单 C 深化后全部消费本原语。

    preprocessor=False 时不识别预处理行（# 行按普通文本，其字符串照剥——
    strip_comments 默认轴的语义）。行首宽容度见 _at_preprocessor_line_start。
    """
    i = start
    n = len(code)
    while i < n:
        char = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if char == "/" and nxt == "/":  # 行注释
            end = code.find("\n", i)
            end = n if end == -1 else end + 1
            yield ("line_comment", i, end)
            i = end
        elif char == "/" and nxt == "*":  # 块注释（跨行一并跳过）
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            yield ("block_comment", i, end)
            i = end
        elif preprocessor and char == "#" and _at_preprocessor_line_start(
            code, i, preprocessor_indented
        ):
            # 预处理行透传：整行原样保留（含引号里的头文件名 / 宏体）
            end = code.find("\n", i)
            end = n if end == -1 else end + 1
            yield ("preprocessor", i, end)
            i = end
        elif char in ('"', "'"):  # 字符串 / 字符字面量（含转义）
            end = _skip_literal(code, i)
            yield ("string" if char == '"' else "char", i, end)
            i = end
        else:  # 普通字符段：拼到下一个区域边界
            j = i + 1
            while j < n:
                c = code[j]
                c2 = code[j + 1] if j + 1 < n else ""
                if c == "/" and (c2 == "/" or c2 == "*"):
                    break
                if preprocessor and c == "#" and _at_preprocessor_line_start(
                    code, j, preprocessor_indented
                ):
                    break
                if c in ('"', "'"):
                    break
                j += 1
            yield ("code", i, j)
            i = j


def strip_comments(code: str, *, keep_preprocessor: bool = False) -> str:
    """去掉 C 注释（行/块）与字符串/字符字面量，只留代码形态。

    keep_preprocessor=True 时，行首 # 打头的预处理行整行原样保留（不剥其中
    字符串）——include 的文件名在引号里，普通字符串剥离会把它当字符串吞掉
    （判例：include 门禁扫描失败）。行首判定必须严格"i==0 或前一字符是换行"，
    不能用回退跳过空白的方式——第 2 行起的 # 行会被误判为不在行首（判例：
    pid.c 第 2 行 #include 被当字符串剥掉，include 门禁漏检）。默认
    keep_preprocessor=False 时 # 行按普通文本处理（调用形态提取用，注释 /
    字符串照剥）。

    实现 = iter_c_regions 单源切分：非 code 区域整段跳过 / 保留（预处理行）。
    """
    out: list[str] = []
    for kind, start, end in iter_c_regions(code, preprocessor=keep_preprocessor):
        if kind == "code":
            out.append(code[start:end])
        elif keep_preprocessor and kind == "preprocessor":
            out.append(code[start:end])
    return "".join(out)


def match_bracket(code: str, open_pos: int, open_ch: str, close_ch: str) -> int:
    """从 open_pos 的 open_ch 起找配平的 close_ch 下标；不配平返回 -1。

    括号内注释 / 字符串 / 预处理行不计数（iter_c_regions 同源切分）——
    main.c 骨架的 while(1){...} 块闭合与调用实参截断共用（skeleton 的
    _match_paren / _match_brace 第二套词法唯一替代）。
    """
    depth = 0
    for kind, start, end in iter_c_regions(code, start=open_pos):
        if kind != "code":
            continue
        for j in range(start, end):
            if code[j] == open_ch:
                depth += 1
            elif code[j] == close_ch:
                depth -= 1
                if depth == 0:
                    return j
    return -1


def next_significant(code: str, pos: int) -> int:
    """从 pos 跳到下一个有效字符位置（跳过空白与行/块注释）。

    用于"块后紧跟 return"这类形态判断（skeleton 的 _skip_ws_and_comments
    唯一替代）；字符串/字符字面量是有效内容，不跳（区域起点原样返回）。
    """
    for kind, start, end in iter_c_regions(code, start=pos):
        if kind in ("string", "char"):
            return start
        if kind != "code":
            continue
        j = start
        while j < end and code[j].isspace():
            j += 1
        if j < end:
            return j
    return len(code)


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
