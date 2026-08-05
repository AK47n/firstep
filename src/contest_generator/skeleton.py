"""main.c 骨架生成输入与静态自检。

流程：LLM 基于所选模块在目标平台的头文件接口（build_skeleton_interfaces 的
输出块）生成 main.c 骨架 → 静态自检（find_undefined_calls）→ 不存在的调用
改写为注释占位（sanitize_skeleton，语句保持可编译）。自检只认喂给 LLM 的
同一份接口块，保证 AI 引用的每个函数都在所选模块头文件中真实存在，骨架可编译。
生成器在落盘前还会做一次同样的静态校验，任何漏网的调用明确报错。

函数识别是文本级启发式：声明/定义要求类型名前缀（void/int/自定义 _t/…），
调用提取排除控制关键字、main.c 自建函数与宏。函数指针调用、强制转换等
生僻形式不在识别范围内（生成的骨架不会用到）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from .llm import LLM
from .manifest import ModuleManifest

# 控制关键字与 main：这些"名字("不是模块函数调用
_CONTROL_KEYWORDS = frozenset(
    {
        "if", "for", "while", "switch", "case", "default", "return", "do",
        "else", "goto", "sizeof", "typedef", "main",
    }
)

_TYPE_TOKENS = (
    r"void|char|short|int|long|float|double|bool|size_t|[A-Za-z_]\w*_t"
    r"|struct\s+\w+|enum\s+\w+"
)

# 调用形态：名字紧跟 (。强制转换 (uint8_t)(x) 的名字后是 ) 而非 (，
# 天然不会匹配；if (foo()) 这类条件里的调用必须能匹配。
_IDENT_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

# 声明/定义：类型名前缀 + 名字 + (…)+ ; 或 {。类型前缀要求排除了普通调用
# 语句（foo(); ）——它们前面不是类型名。
_DECL_OR_DEF_RE = re.compile(
    r"(?<![\w(])(?:(?:extern|static|inline|const|volatile|unsigned|signed|register)\s+)*"
    r"(?:" + _TYPE_TOKENS + r")\s*[*\s]+"
    r"([A-Za-z_]\w*)\s*\([^;{}()]*(?:\([^;{}()]*\))?[^;{}()]*\)\s*[;{]"
)

# 函数式宏：#define 名( —— 名后紧跟 ( 才算（C 标准：函数式宏的 ( 紧随名字）
_MACRO_DEF_RE = re.compile(r"#define\s+([A-Za-z_]\w*)\(")

# 任意 #define 定义的名字（对象宏；定义行上"名 ("可能被调用形态误报）
_DEFINE_RE = re.compile(r"#define\s+([A-Za-z_]\w*)")


def build_skeleton_interfaces(
    manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> list[str]:
    """按目标平台收集所选模块头文件内容，格式化为 LLM 骨架生成输入块。

    顺序与 manifests 一致（调用方应先按依赖展开）；每个模块的平台条目里
    的 .h 文件内容逐块给出。头文件缺失跳过（文件齐全由生成器硬校验兜底）；
    模块无平台版本或纯 .c 实现时给出占位块，LLM 仍知道它被选中。
    """
    blocks: list[str] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            blocks.append(f"### 模块 {manifest.slug}（无平台 {platform} 版本，无接口）")
            continue
        parts: list[str] = []
        for rel in entry.files:
            if not _is_header_path(rel):
                continue
            path = library_dir / manifest.slug / rel
            if not path.is_file():
                continue
            parts.append(f"### 模块 {manifest.slug}（{rel}）")
            parts.append(path.read_text(encoding="utf-8"))
        if not parts:
            blocks.append(
                f"### 模块 {manifest.slug}"
                + ("（头文件缺失，无接口）" if any(_is_header_path(rel) for rel in entry.files) else "（无头文件接口）")
            )
        else:
            blocks.append("\n".join(parts))
    return blocks


def extract_header_functions(interfaces: Sequence[str]) -> set[str]:
    """从接口块提取函数名与函数式宏名（自检的已知集合）。"""
    functions: set[str] = set()
    for block in interfaces:
        functions |= _decl_or_macro_names(_strip_comments_and_strings(block))
    return functions


def verify_main_c(
    main_c: str, manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> tuple[str, ...]:
    """静态自检：main.c 调用了、但不在所选模块头文件接口里的函数名（排序）。

    与 generate_skeleton 共用同一份接口块（build_skeleton_interfaces 的
    输出）——自检只认喂给 LLM 的同一套接口，不存在的调用由调用方决定
    改写（sanitize_skeleton）或明确报错（生成器兜底）。
    """
    interfaces = build_skeleton_interfaces(manifests, platform, library_dir)
    return find_undefined_calls(main_c, extract_header_functions(interfaces))


def find_undefined_calls(
    main_c: str, known_functions: Sequence[str] | set[str]
) -> tuple[str, ...]:
    """静态自检：main.c 调用了、但不在所选模块头文件接口里的函数名。

    注释、字符串里的"调用"不算；main.c 自己定义/声明/宏定义的函数不算；
    控制关键字（if/while/return/…）不算。结果按名字排序，保证确定性。
    """
    stripped = _strip_comments_and_strings(main_c)
    calls = _extract_calls(stripped)
    local = _known_local(stripped)
    unknown = calls - local - set(known_functions)
    return tuple(sorted(unknown))


def sanitize_skeleton(
    main_c: str, known_functions: Sequence[str] | set[str]
) -> tuple[str, tuple[str, ...]]:
    """把调用不存在接口的函数改写为注释占位，保持语句仍可编译。

    语句位置的整段调用替换为"注释 + 空语句"；表达式（赋值 / 条件 / 实参）
    里的调用替换为 0 占位。原调用文本留在 TODO 注释里，用户能看到 AI 的
    意图。返回（改写后的 main.c, 实际被拦截的调用名）；没有不存在的调用
    时原样返回、拦截列表为空。
    """
    undefined = set(find_undefined_calls(main_c, known_functions))
    if not undefined:
        return main_c, ()
    return _replace_undefined_calls(main_c, undefined)


def _replace_undefined_calls(
    code: str, undefined: set[str]
) -> tuple[str, tuple[str, ...]]:
    """逐个替换 code 中 undefined 里的调用；注释、字符串与 # 行透传。"""
    out: list[str] = []
    hits: set[str] = set()
    i = 0
    n = len(code)
    while i < n:
        char = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if char == "/" and nxt == "/":  # 行注释透传
            end = code.find("\n", i)
            end = n if end == -1 else end + 1
            out.append(code[i:end])
            i = end
        elif char == "/" and nxt == "*":  # 块注释透传
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(code[i:end])
            i = end
        elif char in ('"', "'"):  # 字符串透传
            end = _skip_string(code, i)
            out.append(code[i:end])
            i = end
        elif char == "#" and _at_line_start_after_ws(code, i):  # 预处理行透传
            end = code.find("\n", i)
            end = n if end == -1 else end + 1
            out.append(code[i:end])
            i = end
        elif _is_ident_start(char):
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] == "_"):
                j += 1
            name = code[i:j]
            k = j
            while k < n and code[k].isspace():
                k += 1
            if name in undefined and k < n and code[k] == "(":
                close = _match_paren(code, k)
                if close == -1:  # 括号不配平（多半被注释截断）：整段透传
                    out.append(code[i:])
                    break
                call = code[i : close + 1]
                hits.add(name)
                if _is_statement_start(code, i) and _next_nonspace(code, close + 1) == ";":
                    out.append(
                        f"/* TODO: {call} —— 调用了所选模块接口中不存在的函数 {name}，"
                        f"已注释占位，请改用真实接口或自行实现 */"
                    )
                else:
                    out.append(
                        f"/* TODO: {call} —— 调用了所选模块接口中不存在的函数 {name}，"
                        f"已改为 0 占位，请改用真实接口或自行实现 */ 0"
                    )
                i = close + 1
            else:
                out.append(code[i:j])
                i = j
        else:
            out.append(char)
            i += 1
    return "".join(out), tuple(sorted(hits))


def _is_statement_start(code: str, name_pos: int) -> bool:
    """名字前的非空白字符是 { ; } 或行首 → 该调用是独立语句。"""
    j = name_pos - 1
    while j >= 0 and code[j].isspace():
        j -= 1
    return j < 0 or code[j] in "{;}"


def _next_nonspace(code: str, pos: int) -> str:
    j = pos
    while j < len(code) and code[j].isspace():
        j += 1
    return code[j] if j < len(code) else ""


def _at_line_start_after_ws(code: str, pos: int) -> bool:
    j = pos
    while j > 0 and code[j - 1].isspace():
        j -= 1
    return j == 0 or code[j - 1] == "\n"


def _skip_string(code: str, start: int) -> int:
    """从字符串/字符字面量起点跳到闭合引号之后（跳过转义）。"""
    quote = code[start]
    i = start + 1
    n = len(code)
    while i < n and code[i] != quote:
        if code[i] == "\\":
            i += 1
        i += 1
    return min(i + 1, n)


def _match_paren(code: str, open_pos: int) -> int:
    """从 open_pos 的 ( 开始找配平的 ) 下标；不配平返回 -1（字符串/注释不计数）。"""
    depth = 0
    i = open_pos
    n = len(code)
    while i < n:
        char = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if char == "/" and nxt == "/":
            end = code.find("\n", i)
            i = n if end == -1 else end + 1
        elif char == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            if end == -1:
                return -1
            i = end + 2
        elif char in ('"', "'"):
            i = _skip_string(code, i)
        elif char == "(":
            depth += 1
            i += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return i
            i += 1
        else:
            i += 1
    return -1


def _is_ident_start(char: str) -> bool:
    return char.isalpha() or char == "_"


def generate_skeleton(
    llm: LLM,
    problem_text: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
) -> tuple[str, tuple[str, ...]]:
    """LLM 出稿 → 静态自检：返回（可写入工程的 main.c, 被拦截的调用名）。

    自检只认喂给 LLM 的同一份接口块，不存在的调用被改写为注释占位，
    main.c 骨架保证可编译。调用方如想"明确报错"而非占位，对拦截列表
    非空时自行抛错即可。
    """
    interfaces = build_skeleton_interfaces(manifests, platform, library_dir)
    raw = llm.generate_main_skeleton(problem_text, interfaces)
    return sanitize_skeleton(raw, extract_header_functions(interfaces))


def _is_header_path(rel: str) -> bool:
    return rel.lower().endswith(".h")


def _extract_calls(code: str) -> set[str]:
    return {name for name in _IDENT_CALL_RE.findall(code)} - _CONTROL_KEYWORDS


def _known_local(code: str) -> set[str]:
    """main.c 自己定义/声明/宏定义的函数名——调用它们不算未定义。"""
    return _decl_or_macro_names(code) | set(_DEFINE_RE.findall(code))


def _decl_or_macro_names(code: str) -> set[str]:
    """名字带声明/定义或函数式宏形态的标识符集合。"""
    return set(_DECL_OR_DEF_RE.findall(code)) | set(_MACRO_DEF_RE.findall(code))


def _strip_comments_and_strings(code: str) -> str:
    """去掉 C 代码里的注释与字符串/字符字面量，只留代码形态。"""
    out: list[str] = []
    i = 0
    length = len(code)
    while i < length:
        char = code[i]
        nxt = code[i + 1] if i + 1 < length else ""
        if char == "/" and nxt == "/":  # 行注释
            end = code.find("\n", i)
            i = length if end == -1 else end + 1
        elif char == "/" and nxt == "*":  # 块注释
            end = code.find("*/", i + 2)
            i = length if end == -1 else end + 2
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
