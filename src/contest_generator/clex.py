"""C 源码词法层 —— 机械切分文本，不判语义。

围栏剥离 / 注释与字符串切分（iter_c_regions）/ 括号配对（match_bracket）/
空白注释跳读（next_significant）/ 引号 include 提取 / 顶层 #define 扫描 /
顶层函数定义形态扫描（top_level_functions）的唯一出处。接口全部是"字符串进、
字符串出（或元组列表出）"，不碰盘上文件——骨架自检与生成门禁共用同一份实现，
杜绝逐字重复（判例：围栏正则曾两处定义、注释剥离器两义并存，改一处忘另一处
即分叉；skeleton 曾手写第二套注释/字符串切分与括号配对，工单 C 深化吸收）。

不做的事：调用形态识别（"名字后跟 ( 是不是函数调用"）是骨架自检的语义
判断，归 skeleton.py（_DECL_OR_DEF_RE 等）；top_level_functions 也只判
"定义形态"（ident ( … ) { 括号深度 0），不判语义（返回类型 / 参数表校验
一概不看）。
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Literal

# Markdown 代码围栏行（``` / ~~~，可带语言标注）：LLM 输出最常见的传输层包裹
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})[a-zA-Z0-9_-]*\s*$")

# 引号 include 提取（对 strip_comments(keep_preprocessor=True) 后的文本匹配）
_INCLUDE_QUOTED_RE = re.compile(r'#\s*include\s*"([^"]+)"')

# C 标识符（ASCII 词法惯例，不放开 unicode）
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# 顶层函数形态扫描排除的关键字/宏：这些 ident 后跟 ( … ) 是控制流 / 运算符，
# 不是函数定义（top_level_functions 单处引用）
_FUNCTION_KEYWORDS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "case",
        "default",
        "return",
        "sizeof",
        "do",
        "else",
        "goto",
        "break",
        "continue",
        "static_assert",
        "_Static_assert",
    }
)


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


def quoted_include_lines(code: str) -> list[tuple[str, int]]:
    """引号 include 的 (头文件名, 行号) 清单（对**原始** C 文本用）。

    直接走 iter_c_regions(preprocessor=True) 的预处理行区域：行号 = 该 # 行
    在原文的 1 基行号——注释行里的伪装 include（`// #include "no.h"`）与
    字符串里的都不算；与 extract_quoted_includes（对 stripped 文本用）同一
    正则单源（_INCLUDE_QUOTED_RE）。
    """
    starts = _line_starts(code)
    hits: list[tuple[str, int]] = []
    for kind, start, end in iter_c_regions(code, preprocessor=True):
        if kind != "preprocessor":
            continue
        m = _INCLUDE_QUOTED_RE.search(code[start:end])
        if m:
            hits.append((m.group(1), _pos_line(starts, start)))
    return hits


def _line_starts(code: str) -> list[int]:
    """每行起始偏移表（首元素 0；第 k 行起点 = starts[k-1]）。"""
    starts = [0]
    for j, ch in enumerate(code):
        if ch == "\n":
            starts.append(j + 1)
    return starts


def _pos_line(starts: list[int], pos: int) -> int:
    """偏移 → 1 基行号（起点 ≤ pos 的行数；等价二分）。"""
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= pos:
            lo = mid + 1
        else:
            hi = mid
    return lo


def top_level_functions(code: str) -> list[dict[str, Any]]:
    r"""C 源顶层函数定义清单（机械法 best-effort，工单 code-viewer/03）：
    [{name, line}]（line 为 1 基源行号，取函数名所在行）。

    实现 = 掩码切分 + 单遍形态扫描：iter_c_regions(preprocessor=True) 的
    非 code 区域（注释 / 字符串 / 字符字面量 / 行首 # 预处理行）就地替换为
    空白（保留换行与字符数），得到与原文行列对齐的代码掩码；再在掩码上扫描
    花括号深度 0 处 `ident ( … ) {` 形态——ident 排除控制流关键字
    （_FUNCTION_KEYWORDS），(… ) 用 match_bracket 配平，跳过空白后仍是
    `{` 即函数定义（此时括号深度须为 0，防声明体内误收）。

    best-effort 边界（宁可放过、不可误杀）：
    - 多行宏的续行在掩码里仍是可读文本（如 `#define INIT() \` 后一行
      `static void init(void) { \` 会被收成函数）——按「前一行为反斜杠结尾」
      的续行标记整行跳过；续行不含 `\` 结尾（断续宏体）是已知误收风险，
      对「打开即看」场景可接受，以点击行为准。
    - 属性 / 限定符夹在 `)` 与 `{` 之间（如 __attribute__）与 K&R 旧式定义
      不识别；函数指针声明（`int (*p)(void)`）不匹配（ident 后是 `)`）。
    """
    n = len(code)
    mask = list(code)
    for kind, start, end in iter_c_regions(code, preprocessor=True):
        if kind != "code":
            for j in range(start, end):
                if code[j] != "\n":
                    mask[j] = " "
    masked = "".join(mask)

    # 行起始偏移表：line_of(pos) = 起点 ≤ pos 的行数（即 1 基行号）
    line_starts = _line_starts(code)

    def line_of(pos: int) -> int:
        return _pos_line(line_starts, pos)

    raw_lines = code.split("\n")

    def is_continuation(pos: int) -> bool:
        """本行是否为宏续行（前一行为反斜杠结尾，含 CRLF 的 \r 残留）。"""
        idx = line_of(pos) - 2  # 0 基前一行的行号
        if idx < 0:
            return False
        return raw_lines[idx].rstrip("\r").endswith("\\")

    funcs: list[dict[str, Any]] = []
    brace_depth = 0
    paren_depth = 0
    i = 0
    while i < n:
        ch = masked[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            paren_depth += 1
            i += 1
            continue
        if ch == ")":
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue
        if ch == "{":
            brace_depth += 1
            i += 1
            continue
        if ch == "}":
            brace_depth = max(0, brace_depth - 1)
            i += 1
            continue
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch == "_":
            if is_continuation(i):
                eol = code.find("\n", i)
                i = n if eol == -1 else eol  # 宏续行整行跳过（防 do{ / 宏体误收）
                continue
            m = _IDENT_RE.match(masked, i)
            if m is None:
                i += 1
                continue
            word = m.group(0)
            name_start = i
            i = m.end()
            j = i
            while j < n and masked[j].isspace():
                j += 1
            if (
                j < n
                and masked[j] == "("
                and word not in _FUNCTION_KEYWORDS
                and brace_depth == 0
                and paren_depth == 0
            ):
                close = match_bracket(masked, j, "(", ")")
                if close != -1:
                    k = close + 1
                    while k < n and masked[k].isspace():
                        k += 1
                    if k < n and masked[k] == "{" and brace_depth == 0:
                        funcs.append({"name": word, "line": line_of(name_start)})
            continue
        i += 1
    return funcs
