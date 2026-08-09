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
from typing import TYPE_CHECKING, Sequence

from .clex import (
    iter_c_regions,
    match_bracket,
    next_significant,
    strip_code_fences,
    strip_comments,
)
from .manifest import ModuleManifest

if TYPE_CHECKING:
    # 仅类型注解用（skeleton 是纯文本模块，运行时导入 llm 会把整条 LLM 栈
    # 拉进生成流程的 import 图——master.py 同规先例，工单 C3 链收敛）
    from .llm import LLM

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


def is_header_path(rel: str) -> bool:
    """头文件路径判定单源：`.h` endswith（大小写不敏感）。

    骨架接口块筛选与生成语料 kind 分类共吃同一判定——两处曾各抄一份
    `.h` 分支，改一处忘另一处即分叉。
    """
    return rel.lower().endswith(".h")


def read_module_sources(
    manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> tuple[list[tuple[str, str, str, Path]], list[tuple[str, str]]]:
    """有平台条目的模块文件读盘单原语：骨架与生成语料共吃。

    present = (slug, rel, 文本, 完整路径)（路径给调用方做 own_dir =
    path.parent）；missing = (slug, rel)（声明了但读不到，存在性由生成
    门禁报告，这里不 raise）。编码 errors="replace" 与门禁同策略——
    模块文件非 UTF-8 时替换字符继续，不再崩（骨架从崩变不崩是刻意对齐）。
    返回顺序 = manifests 序 / entry.files 序不变。
    """
    present: list[tuple[str, str, str, Path]] = []
    missing: list[tuple[str, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for rel in entry.files:
            path = library_dir / manifest.slug / rel
            if not path.is_file():
                missing.append((manifest.slug, rel))
                continue
            present.append(
                (
                    manifest.slug,
                    rel,
                    path.read_text(encoding="utf-8", errors="replace"),
                    path,
                )
            )
    return present, missing


def build_skeleton_interfaces(
    manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> list[str]:
    """按目标平台收集所选模块头文件内容，格式化为 LLM 骨架生成输入块。

    顺序与 manifests 一致（调用方应先按依赖展开）；每个模块的平台条目里
    的 .h 文件内容逐块给出。头文件缺失跳过（文件齐全由生成器硬校验兜底）；
    模块无平台版本或纯 .c 实现时给出占位块，LLM 仍知道它被选中。
    读盘归 read_module_sources（编码 errors="replace" 单源，与门禁同读法）、
    形态判断归 is_header_path、块格式化归 format_interface_blocks（生成
    门禁用语料文本走同一格式化）。
    """
    blocks: list[str] = []
    present, _missing = read_module_sources(manifests, platform, library_dir)
    headers = [
        (slug, rel, text)
        for slug, rel, text, _path in present
        if is_header_path(rel)
    ]
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            blocks.append(f"### 模块 {manifest.slug}（无平台 {platform} 版本，无接口）")
            continue
        declared_headers = [rel for rel in entry.files if is_header_path(rel)]
        if not declared_headers:
            blocks.append(f"### 模块 {manifest.slug}（无头文件接口）")
            continue
        if not any(h[0] == manifest.slug for h in headers):
            blocks.append(f"### 模块 {manifest.slug}（头文件缺失，无接口）")
    blocks.extend(format_interface_blocks(headers))
    return blocks


def format_interface_blocks(
    headers: Sequence[tuple[str, str, str]],
) -> list[str]:
    """接口块格式化唯一实现：(slug, rel, 头文件文本) → 每模块一个接口块。

    骨架流程（build_skeleton_interfaces 读盘后）与生成门禁（语料文本）共用
    同一份格式化——接口块长什么样只有这里知道。占位块（无平台版本 / 无头
    文件接口 / 头文件缺失）由调用方按形态判断，这里只管"有内容的头文件"。
    每个模块一块：同模块多 rel 的块内容以换行相连（与读盘版行为一致）。
    """
    blocks: list[str] = []
    for slug in dict.fromkeys(h[0] for h in headers):  # 保序去重
        parts: list[str] = []
        for s, rel, text in headers:
            if s == slug:
                parts.append(f"### 模块 {slug}（{rel}）")
                parts.append(text)
        blocks.append("\n".join(parts))
    return blocks


def extract_header_functions(interfaces: Sequence[str]) -> set[str]:
    """从接口块提取函数名与函数式宏名（自检的已知集合）。"""
    functions: set[str] = set()
    for block in interfaces:
        functions |= _decl_or_macro_names(strip_comments(block))
    return functions


def verify_main_c_interfaces(
    main_c: str, interfaces: Sequence[str]
) -> tuple[str, ...]:
    """静态自检：main.c vs 已格式化接口块（骨架流程与生成门禁共用）。

    接口块来自 build_skeleton_interfaces（骨架阶段）或生成语料文本（门禁，
    不重读盘）——自检只认喂给 LLM 的同一套接口。"""
    return find_undefined_calls(main_c, extract_header_functions(interfaces))


def find_undefined_calls(
    main_c: str, known_functions: Sequence[str] | set[str]
) -> tuple[str, ...]:
    """静态自检：main.c 调用了、但不在所选模块头文件接口里的函数名。

    注释、字符串里的"调用"不算；main.c 自己定义/声明/宏定义的函数不算；
    控制关键字（if/while/return/…）不算。结果按名字排序，保证确定性。
    """
    stripped = strip_comments(main_c)
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
    意图。随后 while(1) 死循环后不可达的 return 语句同样注释占位（Keil
    #111-D 判例）。返回（改写后的 main.c, 实际被拦截的调用名）；没有
    不存在调用且无不可达 return 时原样返回、拦截列表为空。
    """
    undefined = set(find_undefined_calls(main_c, known_functions))
    fixed, blocked = (
        _replace_undefined_calls(main_c, undefined) if undefined else (main_c, ())
    )
    return _strip_unreachable_return(fixed), blocked


def _replace_undefined_calls(
    code: str, undefined: set[str]
) -> tuple[str, tuple[str, ...]]:
    """逐个替换 code 中 undefined 里的调用；注释、字符串与 # 行透传。

    遍历 clex.iter_c_regions（词法唯一出处）：非 code 区域（注释 / 字符串 /
    预处理行）原样透传，code 区域内做标识符 + 调用形态识别——语义判断（名字
    后跟 ( 是不是调用、语句位置）仍在本模块。
    """
    out: list[str] = []
    hits: set[str] = set()
    for kind, start, end in iter_c_regions(code, preprocessor_indented=True):
        if kind != "code":
            out.append(code[start:end])
            continue
        i = start
        while i < end:
            char = code[i]
            if not _is_ident_start(char):
                out.append(char)
                i += 1
                continue
            j = i + 1
            while j < end and (code[j].isalnum() or code[j] == "_"):
                j += 1
            name = code[i:j]
            k = j
            while k < end and code[k].isspace():
                k += 1
            if name in undefined and k < end and code[k] == "(":
                close = match_bracket(code, k, "(", ")")
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
    return "".join(out), tuple(sorted(hits))


def _is_statement_start(code: str, name_pos: int) -> bool:
    """名字前的非空白字符是 { ; } 或注释结尾 */ 或行首 → 该调用是独立语句。

    上一行是注释时（如"/* OLED 显示缓冲初始化 */\nstrcpy(...)"），回退跳过
    空白停在 */ 的 / 上——若只认 {;} 会误判为表达式位置、走 0 占位分支，
    独立语句替换成 `0;` 报 #174-D expression has no effect（判例：2021F
    骨架第一处 strcpy 占位）。/ * 相连只可能是块注释边界（无空格的
    a/*p 即注释，除法接解引用必有空格或括号），判断安全。
    """
    j = name_pos - 1
    while j >= 0 and code[j].isspace():
        j -= 1
    return (
        j < 0
        or code[j] in "{;}"
        or (j >= 1 and code[j] == "/" and code[j - 1] == "*")
    )


def _next_nonspace(code: str, pos: int) -> str:
    j = pos
    while j < len(code) and code[j].isspace():
        j += 1
    return code[j] if j < len(code) else ""


_WHILE_ONE_BLOCK_RE = re.compile(r"while\s*\(\s*1\s*\)\s*\{")


def _strip_unreachable_return(code: str) -> str:
    """while(1) 死循环块之后紧跟的独立 return 语句注释占位（Keil #111-D 判例）。

    LLM 常在 while(1){...} 之后补 return 0; —— 死循环后不可达。只处理
    while(1){...} 块闭合后紧跟（跳过空白与注释）的独立 return 语句；
    循环体内的 return、非死循环后的 return 不动。一个文件多处死循环时
    全部处理（替换后从循环块末尾继续扫描）。
    """
    pos = 0
    out: list[str] = []
    while True:
        m = _WHILE_ONE_BLOCK_RE.search(code, pos)
        if m is None:
            out.append(code[pos:])
            return "".join(out)
        close = match_bracket(code, m.end() - 1, "{", "}")
        if close == -1:  # 循环体不配平（代码残缺）：整段透传
            out.append(code[pos:])
            return "".join(out)
        nxt = next_significant(code, close + 1)
        rm = re.match(r"return\b", code[nxt:])
        if rm is None:
            out.append(code[pos : close + 1])
            pos = close + 1
            continue
        semi = code.find(";", nxt)
        if semi == -1:  # return 语句残缺：整段透传
            out.append(code[pos:])
            return "".join(out)
        stmt = code[nxt : semi + 1].strip()
        out.append(
            code[pos : close + 1]
            + "\n"
            + f"/* TODO: {stmt} —— while(1) 死循环后不可达，已注释占位 */"
        )
        pos = semi + 1


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
    raw = strip_code_fences(raw)  # LLM 偶发用围栏包裹 → 剥离后再自检（判例见函数文档）
    return sanitize_skeleton(raw, extract_header_functions(interfaces))


def _extract_calls(code: str) -> set[str]:
    return {name for name in _IDENT_CALL_RE.findall(code)} - _CONTROL_KEYWORDS


def _known_local(code: str) -> set[str]:
    """main.c 自己定义/声明/宏定义的函数名——调用它们不算未定义。"""
    return _decl_or_macro_names(code) | set(_DEFINE_RE.findall(code))


def _decl_or_macro_names(code: str) -> set[str]:
    """名字带声明/定义或函数式宏形态的标识符集合。"""
    return set(_DECL_OR_DEF_RE.findall(code)) | set(_MACRO_DEF_RE.findall(code))
