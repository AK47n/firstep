# -*- coding: utf-8 -*-
"""硬件检测的**交互式串口命令台**（工单 module-hwcheck/06）。

## 这一层是什么

spec「板上行为与判据」：程序形态 = **上电自动跑一遍**，之后进**串口命令交互**
——复测不用重烧。本模块是那半"命令"的所有者，与 `hwcheck_recipe.py` 的分工是：

* 配方（`console` 段，库内数据）声明**每一件用哪个字符复测**；
* 本模块把配方命令 + **固定的帮助命令**汇成一张表（`build_console_table`），
  解析学生敲进来的一行（`parse_console_command`），并把它渲染成 C 侧的分派。

全程零 LLM、纯函数（字符串进 / 字符串出），所以判据全部可在内存里直测。

## 既有五条命令：语义一个字节不动

库内 `debug_uart` 模块早有一个接线检测台（`debug_cmd_poll()`：`r` 红灯 /
`y` 黄灯 / `g` 绿灯 / `o` 全灭 / `b<N>` 蜂鸣 N 毫秒），**已上过板**。本单
**不重写也不接管它**：

* 那五条字符在 `LEGACY_COMMANDS` 里登记为**保留字**，配方不得占用；
* 生成的 `main()` 主循环里**原样保留 `debug_cmd_poll()` 调用**——那五条命令
  走的还是库内那份代码（两个平台各自的原样：stm32 点灯 / 蜂鸣，mspm0 回显）；
* 命令台只**追加**：`debug_cmd_peek()` 看一眼收到的字符，是配方命令或帮助才
  处理并 `debug_cmd_consume()` 消费掉，**其余一律不碰**，留给 `debug_cmd_poll()`。

这样"既有语义一个字节不动"不是一句承诺，而是**结构上不可能被改**：这里没有
任何一行重写那五条命令的代码（守卫用例还逐字符核对本模块的保留字与库内
`debug_uart.c` 的分派分支一致，见 `tests/test_hwcheck_console.py`）。

## 字符冲突 = 构建期大声失败

两件抢同一个字符（或抢了库内既有字符 / 帮助字符）= `HwCheckError`（→ 400
中文，点名两件与那个字符）。为什么不运行时静默覆盖：那会让"复测第二件"
永远测到第一件，而页面上两件都写着"有命令"——正是 spec 要防的"看着测了
其实没测"。

## 命令的粒度是"首字符"

与库内既有命令同一口径：`debug_cmd_poll()` 也只看 `cmd_buf[0]`（所以 `r50`
就是红灯、`b50` 才把数字当参数）。配方命令是单字符，多打的尾巴忽略——
解析与渲染两侧都按首字符分派，免得"手滑多敲一个字符 = 命令不认"。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .hwcheck_errors import HwCheckError
from .hwcheck_recipe import RecipeSection, c_string

__all__ = [
    "CONSOLE_HINT_NONE",
    "CONSOLE_HINT_SERIAL",
    "CONSOLE_HINT_SERIAL_NO_COMMAND",
    "HELP_COMMAND",
    "LEGACY_COMMANDS",
    "RESERVED_COMMANDS",
    "ConsoleCommand",
    "ConsoleEntry",
    "ConsoleTable",
    "build_console_table",
    "console_hint",
    "console_payload",
    "parse_console_command",
    "render_console_runtime",
]


# 固定的帮助命令（票面："每件声明的命令字符 + 固定的帮助命令"）。
# 取 `?` 是因为库内既有命令的**未知命令提示**本来就是 `? r/g/y/o/b<N>`
# ——学生已经习惯用问号问"有什么命令"，这里沿用同一个字符，不另发明一个。
HELP_COMMAND = "?"

# 库内既有的五条命令（`library/modules/debug_uart/code/debug_uart.c` 的
# `debug_cmd_poll()`，已上过板）：**保留字**，配方不得占用。
# 每条 = (字符, 人话含义)。含义只用于帮助文案与检测页展示。
#
# ⚠ 这张表是**镜像**：真身在库内 C 源码里。`tests/test_hwcheck_console.py`
# 有一条 parity 守卫逐字符核对两边（库改了命令集而这里没跟上 → 当场红），
# 因为"保留字漏登记"的后果是配方抢走一条既有命令、学生敲 r 不再点灯。
LEGACY_COMMANDS: tuple[tuple[str, str], ...] = (
    ("r", "红灯亮，其余灭"),
    ("y", "黄灯亮，其余灭"),
    ("g", "绿灯亮，其余灭"),
    ("o", "全灭"),
    ("b", "蜂鸣器响 N 毫秒（如 b50）"),
)

# 配方**不许**占用的字符：既有五条 + 帮助命令（大小写不敏感，见 _normalize）。
RESERVED_COMMANDS: frozenset[str] = frozenset(
    command for command, _meaning in LEGACY_COMMANDS
) | {HELP_COMMAND}

# 既有命令的**比较键**（归一后）——解析时分派用，免得每次重建集合。
_LEGACY_KEYS: frozenset[str] = frozenset(
    command.lower() for command, _meaning in LEGACY_COMMANDS
)

# 帮助里每行列几条既有命令：判据是**行缓冲**（`hwcheck_line[128]`，框架的溢出
# 保护），中文一字 3 字节——两条一排实测最长 60 字节上下，留足余量（工单 07 的
# `test_every_reported_line_fits_the_line_buffer` 是全产物级的那道守卫）。
_LEGACY_PER_HELP_LINE = 2


def _normalize(command: str) -> str:
    """命令字符的**比较形态**：小写（库内既有命令也是 `r` / `R` 两写都收）。

    判据与渲染都用它：`l` 与 `L` 在表里是同一个命令，学生按了 Caps Lock 也认。
    """
    return command.lower()


# 固定命令的说明缺省句（配方没写 description 时用）——**单源**：它同时进板上回显、
# 帮助文案、检测页命令表与产物文件头，四处各写一份就会漂成两种措辞（评审抓过）。
DEFAULT_COMMAND_DESCRIPTION = "按这一件的配方重跑一遍检测小节"


@dataclass(frozen=True)
class ConsoleEntry:
    """一条配方命令：字符 + 哪一件 + 一句说明。

    `description` 来自配方（`console.description`），进帮助文案与检测页；
    `echo_title` / `echo_what` 是**复测回显**的前两段（第三段"结论 / 数值"
    要到板上跑这一节才算得出来，见 `tests/test_hwcheck_console.py` 的格式锁）。
    """

    command: str
    slug: str
    description: str = ""

    @property
    def detail(self) -> str:
        """复测这一件到底做什么（配方说明缺省时的兜底句也走这里，单源）。"""
        return self.description or DEFAULT_COMMAND_DESCRIPTION

    @property
    def echo_title(self) -> str:
        """回显第一段「这是哪件」（板书式小节头）。"""
        return f"[复测] {self.slug}"

    @property
    def echo_what(self) -> str:
        """回显第二段「测的是什么」——配方自己那句说明，改配方即改文案。"""
        return f"测的是：{self.detail}"


@dataclass(frozen=True)
class ConsoleTable:
    """这一趟检测程序认的**全部**串口命令：配方命令 + 固定的帮助命令。

    `entries` 保序（= 配方的顺序），`by_command` 是渲染期与解析共用的索引
    （键已归一成小写）。
    """

    entries: tuple[ConsoleEntry, ...] = ()
    help_command: str = HELP_COMMAND

    @property
    def by_command(self) -> dict[str, ConsoleEntry]:
        return {_normalize(entry.command): entry for entry in self.entries}

    def lookup(self, command: str) -> ConsoleEntry | None:
        """首字符 → 配方命令（大小写不敏感；没有 = None）。"""
        return self.by_command.get(_normalize(command))

    def help_lines(self) -> tuple[str, ...]:
        """帮助的每一行（**逐行**给，不拼成一个带 `\\n` 的大字符串）。

        为什么要逐行：这些字最终要经 `hwcheck_recipe.c_string` 落进 C 字面量，
        而 C 字符串字面量**不能跨行**（真换行会让整份 main.c 编不过，04 的
        真机判例就在文件头上写着）。逐行 + `hwcheck_newline()` 才是安全的形状。

        ⚠ **一行要短**：板上是 `hwcheck_line[128]` 的行缓冲（框架的溢出保护），
        超了会截断——中文在 UTF-8 下一字 3 字节，截在字中间就是半个乱码
        （工单 07 的行缓冲守卫实测抓到过：原来那行一条龙列五条既有命令，136
        字节，**已经超了**）。所以既有命令**每行两条**排下去，措辞一个字不改
        （那几句是镜像库内 `debug_uart.c` 的说明，改了就与库漂了）。
        """
        legacy_rows: list[str] = []
        row: list[str] = []
        for command, meaning in LEGACY_COMMANDS:
            row.append(f"{command} {meaning}")
            if len(row) == _LEGACY_PER_HELP_LINE:
                legacy_rows.append("    " + " / ".join(row))
                row = []
        if row:
            legacy_rows.append("    " + " / ".join(row))
        lines = [
            "[帮助] 可用命令（单字符 + 回车）：",
            "  既有（库内 debug_cmd_poll 原样执行）：",
            *legacy_rows,
        ]
        if self.entries:
            for entry in self.entries:
                lines.append(f"  {entry.command}  {entry.slug}：{entry.detail}")
        else:
            lines.append("  这一趟没有配方命令（配方里没声明复测字符）")
        lines.append(f"  {self.help_command}  显示这份帮助")
        return tuple(lines)

    def help_text(self) -> str:
        """帮助全文（检测页 / 测试用的人读形态）。"""
        return "\n".join(self.help_lines())


# 解析结果的四类（+ 空输入）。**没有第五类**：认不出来就是 `unknown`，
# 绝不猜成某一件——猜错会让学生以为"刚才那下测了那一件"。
KIND_EMPTY = "empty"
KIND_HELP = "help"
KIND_RETEST = "retest"
KIND_LEGACY = "legacy"
KIND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConsoleCommand:
    """一行输入解析出的**结果**（`parse_console_command` 的返回值）。

    `kind` 四类 + 空输入：

    | kind | 含义 | 谁执行 |
    |---|---|---|
    | `empty` | 空输入（没敲东西 / 只有回车） | 没人——什么都不做 |
    | `help` | 帮助命令 | 命令台自己印帮助 |
    | `retest` | 配方声明的复测命令 | 命令台跑那一件的小节（`entry`） |
    | `legacy` | 库内既有命令（`r/y/g/o/b<N>`） | **库内 `debug_cmd_poll()`**，命令台不碰 |
    | `unknown` | 不认识 | 命令台印完整帮助（含既有命令） |

    `command` = 归一后的**首字符**（空输入 = `""`）；`line` = 原始输入（回显 /
    报错时点名学生到底敲了什么，别让人对着"未知命令"猜）。
    """

    kind: str
    line: str = ""
    command: str = ""
    entry: ConsoleEntry | None = None

    @property
    def slug(self) -> str:
        """复测哪一件（只有 `retest` 有）；其余 = 空串。"""
        return self.entry.slug if self.entry is not None else ""


def parse_console_command(line: str, table: ConsoleTable) -> ConsoleCommand:
    """一行输入 → 解析结果（**纯函数**，字符串进 / 结果出）。

    判据按**首字符**（与库内既有命令同一口径，见模块头「命令的粒度」）：

    1. 空串 → `empty`（板上等价于"按键还没收到"：ISR 只在收到实字符时写缓冲）；
    2. 首字符是既有命令（`r/y/g/o/b`，大小写都收）→ `legacy`——**命令台不碰**，
       原样留给库内 `debug_cmd_poll()`（`b50` 这类多字符参数也整行交给它）；
    3. 首字符是帮助命令 → `help`；
    4. 首字符是配方声明的字符 → `retest`（认得出哪一件）；
    5. 其余 → `unknown`。

    先判既有命令再判帮助 / 配方，是因为既有命令的语义归库内那份代码；这里
    任何"顺手也认一下"的分支都是在重写它。

    ⚠ **不做 `strip()`**：C 侧看的是 `line[0]`（原样第一个字符），库内既有命令
    也是 `cmd_buf[0]`——Python 这边先 strip 会让 `" l"` 判成 `retest` 而板上判成
    `unknown`，两条实现就分家了（评审实测的错位）。空格也是字符。
    """
    if not isinstance(line, str) or not line:
        return ConsoleCommand(kind=KIND_EMPTY, line=line if isinstance(line, str) else "")
    head = line[0]
    key = _normalize(head)
    if key in _LEGACY_KEYS:
        return ConsoleCommand(kind=KIND_LEGACY, line=line, command=head)
    if key == _normalize(table.help_command):
        return ConsoleCommand(kind=KIND_HELP, line=line, command=head)
    entry = table.lookup(head)
    if entry is not None:
        return ConsoleCommand(kind=KIND_RETEST, line=line, command=head, entry=entry)
    return ConsoleCommand(kind=KIND_UNKNOWN, line=line, command=head)




def render_console_runtime(table: ConsoleTable) -> list[str]:
    """命令台的 C 运行时（缩进好的**文件作用域**语句，插进 main.c 的框架里）。

    产物两件（纯函数，可逐字断言）：

    * `hwcheck_console_help()`：逐行印帮助（既有五条 + 配方命令 + 帮助自己）；
    * `hwcheck_console_poll()`：`debug_cmd_peek()` 看一眼收到的字符 → `switch`：

      - 配方字符 → **三段固定回显**（① 小节头 `[复测] <slug>` ② `测的是：<配方说明>`
        ③ 跑 `hwcheck_check_<slug>()`，结论与数值由那一节自己在板上打印）后 `break`；
      - 帮助字符 → 印帮助后 `break`；
      - 既有 `r/y/g/o/b`（两种大小写）→ **只 `return`**，一个动作都不做：
        原样留给库内 `debug_cmd_poll()`（"语义一个字节不动"的结构证据）；
      - 其余 → 原样回显学生敲的那一行 + 印帮助后 `break`。

      只有走到 `break` 的（= 我们自己处理过的）才 `debug_cmd_consume()`——
      既有命令那条路已经 `return` 了，缓冲留给库内那份代码。

    ⚠ 字面量一律经 `c_string` 转义，且帮助**逐行**印（C 字符串字面量不能跨行，
    见 `ConsoleTable.help_lines`）。

    ⚠ 必须在逐件小节函数**之后**渲染：`switch` 里直接调 `hwcheck_check_<slug>()`，
    排在前面就是隐式声明（真机口径下 ARMCC 报 `#223-D`，验收线是 0 warning）。
    """
    out: list[str] = [
        "/* ---- 串口命令台（配方驱动的复测；工单 module-hwcheck/06）----",
        " * 既有 r/y/g/o/b 由库内 debug_cmd_poll() 原样执行：这里只 peek 一眼收到的",
        " * 字符，是配方命令 / 帮助才处理并 consume，其余一律不碰（既有语义一个字节",
        " * 不动）。复测不用重烧——边动线边看现象。 */",
        "static void hwcheck_console_help(void)",
        "{",
    ]
    for line in table.help_lines():
        out.append(f"    hwcheck_report({c_string(line)});")
        out.append("    hwcheck_newline();")
    out.extend([
        "}",
        "",
        "/** 主循环轮询：认领配方命令 / 帮助，其余留给库内 debug_cmd_poll()。 */",
        "static void hwcheck_console_poll(void)",
        "{",
        "    const char *line = debug_cmd_peek();",
        "    char cmd;",
        "",
        "    if (line[0] == '\\0')",
        "    {",
        "        return;   /* 没收到完整命令：什么都不做（心跳照跑） */",
        "    }",
        "    cmd = line[0];   /* 命令粒度 = 首字符，与库内既有命令同一口径 */",
        "    switch (cmd)",
        "    {",
    ])
    for entry in table.entries:
        out.append(f"    case '{entry.command}':")
        if entry.command.isalpha():
            out.append(f"    case '{entry.command.upper()}':")
        out.append(f"        /* {entry.slug}：{entry.detail} */")
        out.append(f"        hwcheck_section({c_string(entry.echo_title)});")
        out.append(f"        hwcheck_detail({c_string(entry.echo_what)});")
        out.append(f"        hwcheck_check_{entry.slug}();")
        out.append("        break;")
    out.append(f"    case '{table.help_command}':")
    out.append("        hwcheck_console_help();")
    out.append("        break;")
    legacy_labels: list[str] = []
    for command, _meaning in LEGACY_COMMANDS:
        for char in (command, command.upper()):
            if char not in legacy_labels:
                legacy_labels.append(char)
    out.append("    /* 既有命令：原样留给库内 debug_cmd_poll()——这里一个字都不动它 */")
    for char in legacy_labels:
        out.append(f"    case '{char}':")
    out.append("        return;")
    out.extend([
        "    default:",
        f"        hwcheck_report({c_string('[未知命令] ')});",
        "        hwcheck_report(line);   /* 原样回显学生敲的那一行，别让人猜 */",
        "        hwcheck_newline();",
        "        hwcheck_console_help();",
        "        break;",
        "    }",
        "    /* 只有我们处理过的才消费；既有命令在上面已经 return（留给库内那份） */",
        "    debug_cmd_consume();",
        "}",
    ])
    return out


# 检测页的「应看到什么」两句话（后端给文案，前端只渲染——照 OUTPUT_HINT_*
# 的既有分工）。无串口那句必须**明说不能交互式复测**（票面：不静默降级）。
CONSOLE_HINT_SERIAL = (
    "有串口 = 能交互式复测：程序跑完上电那一遍后进命令循环，"
    "敲下面任一个字符就复测那一件（不用重烧、边动线边看现象）；"
    f"敲 {HELP_COMMAND} 看全部命令（含既有的 r / y / g / o / b<N>）。"
)
CONSOLE_HINT_SERIAL_NO_COMMAND = (
    "有串口，但这一趟没有配方命令（选的器件没声明复测字符）："
    f"命令循环里敲 {HELP_COMMAND} 看帮助，既有的 r / y / g / o / b<N> 照旧可用。"
)
CONSOLE_HINT_NONE = (
    "**没有串口 = 不能交互式复测**：这一趟只跑上电那一遍"
    "（LED 心跳 + 逐件自报各一次），不能边动线边看现象。"
    "想反复复测，请在上面勾上「调试串口」再生成一次。"
)


def console_hint(debug_uart: bool, table: ConsoleTable) -> str:
    """检测页那句「这一趟能不能交互式复测 / 敲什么」（纯函数）。"""
    if not debug_uart:
        return CONSOLE_HINT_NONE
    return CONSOLE_HINT_SERIAL if table.entries else CONSOLE_HINT_SERIAL_NO_COMMAND


def console_payload(debug_uart: bool, table: ConsoleTable) -> dict:
    """检测页的命令台载荷（三个端点共用；前端只渲染，不重推判据）。

    字段就是页面要显示的全部：能不能复测（`available` + 那句 `hint`）、
    配方命令（`commands`，含与板上**同一句**回显文案 `echo`）、既有命令
    （`legacy`，给人看"r/y/g/o/b 还在"）、帮助字符。页面与板上读的是同一张
    表——页面说"敲 l 复测 led"，板上就一定认 `l`。
    """
    return {
        "available": bool(debug_uart),
        "hint": console_hint(debug_uart, table),
        "help_command": table.help_command,
        "commands": [
            {
                "command": entry.command,
                "slug": entry.slug,
                # 说明恒非空（缺省句走 entry.detail 单源）：前端不必再兜一次，
                # 否则就是"同一句话两处写、两种措辞"（评审抓过）
                "description": entry.detail,
                "echo": entry.echo_what,
            }
            for entry in table.entries
        ],
        "legacy": [
            {"command": command, "description": meaning}
            for command, meaning in LEGACY_COMMANDS
        ],
    }


def _require_command_shape(section: RecipeSection, command: str) -> None:
    """命令字符的形状判据：单个可打印 ASCII（不含空白、不含 `'` 与 `\\`）。

    形状在 `hwcheck_recipe` 的 `console` 段已经判过（必须单字符），这里再判
    一次是因为**校验的判据面不同**：那边判的是"配方文件写得对不对"，这里判的
    是"能不能当命令表的一格"（非 ASCII / 空白字符在串口上敲不出来，也不是
    命令）。两处都在，错的方向才安全。

    ⚠ **多排除 `'` 与 `\\`**（评审实测）：命令最终落成 C 字符字面量 `case 'x':`，
    这两个字符会渲染出 `case ''':` / `case '\\':`——**编译器直接报错**，而构建期
    那句中文判据却放它过去，等于把"配方写错当场红"的承诺在这两个字符上打了洞。
    转义当然也能治，但串口上敲单引号/反斜杠本来就够格当命令（判据刻意窄：
    字母 / 数字 / 常见符号里能用的都留着，只掐掉进不了 C 字面量的那两个）。
    """
    dangerous = "'" if command == "'" else ("\\" if command == "\\" else "")
    if len(command) != 1 or not command.isascii() or not command.isprintable() \
            or command.isspace() or dangerous:
        raise HwCheckError(
            f"{section.slug!r} 的控制台命令 {command!r} 不能当命令字符："
            "只能是**一个可打印的 ASCII 字符**（串口上敲得出来的那种，"
            "不要空白 / 中文 / 多字符），也不要单引号 `'` 与反斜杠 `\\`"
            "——这两个字符进不了 C 字符字面量（`case '\\'':` 编不过），"
            "渲染器不会为它们转义"
        )


def build_console_table(sections: Sequence[RecipeSection]) -> ConsoleTable:
    """逐件小节 → 命令表（纯函数）。冲突 / 形状不对 → `HwCheckError`（构建期）。

    三条判据（任一不满足即红，**不静默覆盖**）：

    1. 配方声明的字符不得是库内既有命令（`r/y/g/o/b`）或帮助命令（`?`）
       ——抢了它们的后果是"学生敲 r 不再点灯"，而那是已上过板的既有行为；
    2. 两件不得声明同一个字符（大小写不敏感）——静默覆盖会让第二件永远测不到；
    3. 字符必须是一个可打印 ASCII 字符（`_require_command_shape`）。

    表里的命令一律**规范化为小写**（声明 `L` 就是声明 `l`）：大小写不敏感是
    "同一个命令"而不是两个，规范化之后"判重"与"渲染 `case 'x': case 'X':`"
    才在同一个形态上成立（不规范化会出两个 `case 'L':` 重复标签，编不过）。

    没有 `console` 段的小节不进表（缺段 = 这一件没有复测命令，合法）。
    """
    entries: list[ConsoleEntry] = []
    seen: dict[str, ConsoleEntry] = {}
    for section in sections:
        console = section.console
        if console is None:
            continue
        command = console.command
        _require_command_shape(section, command)
        # 规范化到**小写**（判据与渲染共用的唯一形态）：声明 `L` 就是声明 `l`
        # ——大小写不敏感是"同一个命令"，不是两个。不规范化的后果是渲染器为它
        # 出 `case 'L': case 'L':` 两个**重复标签**（编译器直接报错），而表里
        # 又按小写判重（同一个字符能声明两次）。
        command = command.lower()
        key = _normalize(command)
        if key in RESERVED_COMMANDS:
            owner = dict(LEGACY_COMMANDS).get(key)
            origin = (
                f"库内既有命令（{command}：{owner}，已上过板）"
                if owner
                else "固定的帮助命令"
            )
            raise HwCheckError(
                f"{section.slug!r} 的控制台命令 {command!r} 与{origin}冲突："
                "既有命令的语义一个字节不动，配方命令只能**追加**——"
                "请换一个字符（检测页的帮助文案会列出现有命令）"
            )
        if key in seen:
            raise HwCheckError(
                f"控制台命令字符 {command!r} 被 {seen[key].slug!r} 与 "
                f"{section.slug!r} 同时声明——命令循环按字符分派，重复会让"
                "其中一件永远测不到（运行期静默覆盖，正是本单要防的）："
                "请给其中一件换一个字符"
            )
        entry = ConsoleEntry(
            command=command, slug=section.slug, description=console.description
        )
        seen[key] = entry
        entries.append(entry)
    return ConsoleTable(entries=tuple(entries))
