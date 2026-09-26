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

## 字符冲突 = 构建期大声失败（工单 hwcheck-specialize/01 起：先让位，让不开才红）

配方可以给一件声明**首选 + 候选**（`console.command` / `console.candidates`）：首选被
别的器件占了就按候选顺序**让位**（`_recipe_command`），学生勾两件传感器不再因为"两件
都想用同一个字符"而生成不出来。让不开（候选也用完）或声明了保留字 = `HwCheckError`
（→ 400 中文，点名哪一件排不上号、池子多大、已被谁占）。为什么不运行时静默覆盖：那会让
"复测第二件"永远测到第一件，而页面上两件都写着"有命令"——正是 spec 要防的"看着测了
其实没测"。**不带候选的老配方行为逐字不变**：首选被占时仍然当场红。

## 命令的粒度是"首字符"

与库内既有命令同一口径：`debug_cmd_poll()` 也只看 `cmd_buf[0]`（所以 `r50`
就是红灯、`b50` 才把数字当参数）。配方命令是单字符，多打的尾巴忽略——
解析与渲染两侧都按首字符分派，免得"手滑多敲一个字符 = 命令不认"。

## 自建件（库外件）的字符是**分出来的**（工单 hwcheck-unknown-device/06）

自建件没有配方、没人给它声明字符（「我的器件」的字段全是器件的事实，没有一个
字是"这个工具怎么用它"），所以命令空间**自己分**一个：候选顺序 = ① id 去掉
`mine_` 前缀后出现的字母 / 数字（保序去重，`mine_hall` → 先试 `h`，可记）
② 兜底池（`a`–`z`、`0`–`9`）。保留字（`r/y/g/o/b/?`）与已被配方占用的都跳过；
**一个都分不出来 = 构建期 `HwCheckError`**（不静默少一条——页面上写着"敲这个
复测"、板上却不认，正是这一层一路在防的那类坏法）。

分配是**纯函数**且只依赖输入（配方小节 + 自建件小节的顺序）：同一次装配里，
页面上的字符与产物里 `case 'x':` 的字符必然是同一个。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .hwcheck_custom import CUSTOM_TAG, CustomSection
from .hwcheck_errors import HwCheckError
from .hwcheck_recipe import RecipeSection, c_string
from .my_devices import DEVICE_ID_PREFIX

__all__ = [
    "COMMAND_POOL",
    "CONSOLE_HINT_NONE",
    "CONSOLE_HINT_SERIAL",
    "CONSOLE_HINT_SERIAL_NO_COMMAND",
    "CONSOLE_NO_COMMAND",
    "CUSTOM_COMMAND_FALLBACK",
    "HELP_COMMAND",
    "LEGACY_COMMANDS",
    "RESERVED_COMMANDS",
    "ConsoleCommand",
    "ConsoleEntry",
    "ConsoleTable",
    "build_console_table",
    "console_capacity_note",
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

# 自建件分字符时的**兜底池**（id 里挑不出可用的就按这个顺序往下找）。
# 只有 `a`–`z` 与 `0`–`9`：串口上敲得出来、进得了 C 字符字面量 `case 'x':`，
# 而且大小写不敏感（`A` 与 `a` 是同一个命令）——所以池子就是这 36 个，
# 保留字与配方占掉的那些再从中扣掉。
CUSTOM_COMMAND_FALLBACK = "abcdefghijklmnopqrstuvwxyz0123456789"

# **命令空间**（配方与自建件共用）：字母数字里除去保留字。`?` 本来就不在这 36 个
# 里面，所以池子 = 36 - 5 = 31 个。报错文案里的"池子多大"读它——分配的两条腿
# （配方让位 / 自建件分配）各算一遍，迟早有一边算漂。
COMMAND_POOL: tuple[str, ...] = tuple(
    char for char in CUSTOM_COMMAND_FALLBACK if char not in RESERVED_COMMANDS
)


def _pool_description() -> str:
    """报错文案里"池子多大"那半句——两条腿（配方让位 / 自建件分配）共用一处措辞。

    两处各写一遍的后果不是"啰嗦"：其中一个数改了、另一个没改，报错就会给出自相
    矛盾的读数（工单 06 评审已经抓过一次"只扣保留字、不扣已占用"的假读数）。

    ⚠ 这个数**必须是真能分配的字符数**（工单 hwcheck-hardening/05）：池子大小本身不等于
    可分配数——分配只能在各配方**声明过的**首选 / 候选里挑。本单之前池里 `4 5 6 7 8 9`
    六个字符没有任何配方声明过，于是这句话把可分配数说大了 6 个，正好把人往"还能再勾"引。
    今天两边的并集已经对齐，`tests/test_hwcheck_console.py` 有一条守卫盯着这层对齐。
    """
    return (f"可用字符一共 {len(COMMAND_POOL)} 个"
            f"（字母数字里除去既有命令 {'/'.join(sorted(RESERVED_COMMANDS))}）")


# 剩余多少个字符时开始**事前**提示（工单 hwcheck-hardening/05）。取 3：再勾两件就会排不上号，
# 而学生此刻在页面上还能改（去掉一件 / 换组合），不必等到按了生成才吃一个 400。
CONSOLE_CAPACITY_WARN_REMAINING = 3


def console_capacity_note(
    sections: Sequence[RecipeSection], custom: Sequence[CustomSection] = ()
) -> str:
    """还剩几个复测字符可用——接近上限时给一句**事前**提示（工单 hwcheck-hardening/05）。

    为什么要有它：字符分配失败是**生成前 400**（`build_console_table` 当场点名谁排不上号），
    而学生在这之前拿不到任何信号——只有按了「生成」才知道。页面需要的不是"能不能分配"，
    而是"离装不下还有多远"，所以这里报**剩余数**。

    三条口径：

    * 建得出表 → 剩余 = 池子 − 已占；超过阈值（`CONSOLE_CAPACITY_WARN_REMAINING`）返回空串
      （平时不吭声，别把一句警告常驻在页面上）；
    * **建不出表 → 返回空串**：那条路端点会给 400 的完整点名（谁排不上号、被谁占了、出路），
      页面再说一句就是两个口径；
    * 文案只报事实（占了几件 / 池子多大 / 还剩几个），出路交给 400 那份文案，不在这里重写。
    """
    try:
        table = build_console_table(sections, custom)
    except HwCheckError:
        return ""
    used = len(table.entries)
    remaining = len(COMMAND_POOL) - used
    if remaining > CONSOLE_CAPACITY_WARN_REMAINING:
        return ""
    return (
        f"⚠ 复测字符快用完了：这一趟 {used} 件已经占掉 {used} 个字符，"
        f"{_pool_description()}，只剩 {remaining} 个——再加器件可能排不上号"
        "（那时这一页会点名是哪一件，去掉它或者换一组再生成）。"
    )


@dataclass(frozen=True)
class ConsoleEntry:
    """一条命令：字符 + 哪一件 + 一句说明。

    两种来源共用这一个形状（工单 hwcheck-unknown-device/06）：

    | 来源 | 字符从哪来 | 复测入口 |
    |---|---|---|
    | 库内配方（`custom=False`） | 配方 `console` 段声明 | `hwcheck_check_<slug>()` |
    | 自建件（`custom=True`） | 命令空间分配（`_assign_custom_command`） | 自建件的小节函数 |

    `description` 来自配方（`console.description`）或自建件的"这一趟对它做什么"
    （`CustomSection.plan`），进帮助文案与检测页；`echo_title` / `echo_what` 是
    **复测回显**的前两段（第三段"结论 / 数值"要到板上跑这一节才算得出来，
    见 `tests/test_hwcheck_console.py` 的格式锁）。

    `name` 只有自建件有（用户填的人读名；配方件没有"另一个名字"）。
    `func_name` 空 = 配方件（按 slug 派生），自建件的名字**由 `hwcheck_custom`
    给**（`CustomSection.func_name`）——命名规则不在两处各写一遍。
    """

    command: str
    slug: str
    description: str = ""
    func_name: str = ""
    custom: bool = False
    name: str = ""

    @property
    def detail(self) -> str:
        """复测这一件到底做什么（配方说明缺省时的兜底句也走这里，单源）。"""
        return self.description or DEFAULT_COMMAND_DESCRIPTION

    @property
    def call_target(self) -> str:
        """板上复测时调的那个 C 函数。

        判别式**只有 `custom` 一个**（三处 `if entry.custom` 看的是同一个事实，
        不拿 `func_name` 是不是空串当第二个哨兵）：自建件调它自己的小节函数
        （名字由 `hwcheck_custom` 给），配方件调按 slug 派生的小节函数。
        """
        if self.custom:
            return self.func_name
        return f"hwcheck_check_{self.slug}"

    @property
    def label(self) -> str:
        """帮助 / 文件头里"哪一件"那一栏（前端那一格叫同名：`label`）。

        自建件带上标注词（`CUSTOM_TAG`）——板上与页面上都要能一眼看出哪些结论是
        库内验证过的、哪些只是"按你确认的事实试的"（spec 用户故事 8）。
        """
        return f"{self.slug}（{CUSTOM_TAG}）" if self.custom else self.slug

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
    """这一趟检测程序认的**全部**串口命令：配方命令（+ 自建件命令）+ 固定的帮助命令。

    `entries` 保序（= 配方顺序、自建件接在最后），`by_command` 是渲染期与解析共用
    的索引（键已归一成小写）。
    """

    entries: tuple[ConsoleEntry, ...] = ()
    help_command: str = HELP_COMMAND

    @property
    def by_command(self) -> dict[str, ConsoleEntry]:
        return {_normalize(entry.command): entry for entry in self.entries}

    def lookup(self, command: str) -> ConsoleEntry | None:
        """首字符 → 表里那一条命令（大小写不敏感；没有 = None）。"""
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
                lines.append(f"  {entry.command}  {entry.label}：{entry.detail}")
        else:
            # ⚠ 这一句（与 hint / 文件头那两句）**保持改动前的字面量**：自建件从不
            # 声明字符，所以"没有配方命令"在新世界里仍然为真；而票面第 5 条要求
            # "一件自建件都没有时命令台产物逐字与改动前一致"——统一措辞就得动它，
            # 动了就破票面（工单 06 评审提过"三处措辞不一"，判为不改，取舍记账在
            # 工单结论里；`test_a_run_without_custom_devices_keeps_the_old_console_text`
            # 把这几个字面量钉住了）。
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
        "/* ---- 串口命令台（配方驱动的复测）----",
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
        out.append(f"        /* {entry.label}：{entry.detail} */")
        out.append(f"        hwcheck_section({c_string(entry.echo_title)});")
        out.append(f"        hwcheck_detail({c_string(entry.echo_what)});")
        out.append(f"        {entry.call_target}();")
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


# 「这一趟一条命令都没有」那三句（板上帮助 / 检测页 hint / 产物文件头）**保持原样**
# ——自建件也会往表里放命令之后它们**仍然为真**（自建件从不声明字符），而票面第 5 条
# 要求"一件自建件都没有时命令台产物逐字与改动前一致"：统一措辞就得动这三句，动了
# 就破票面（工单 06 评审提过"三处措辞不一"，判为**不改**，取舍记在工单结论里）。

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
    "<strong>没有串口 = 不能交互式复测</strong>：这一趟只跑上电那一遍"
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
    命令（`commands`，含与板上**同一句**回显文案 `echo`）、既有命令
    （`legacy`，给人看"r/y/g/o/b 还在"）、帮助字符。页面与板上读的是同一张
    表——页面说"敲 l 复测 led"，板上就一定认 `l`。

    自建件那几行多两个键：`tag`（标注词，`hwcheck_custom` 单源）与 `name`
    （用户填的人读名）。**只在自建件那几行加**——既有那几行的形状是页面与用例
    的契约，动它就是动契约；前端按"有没有 `tag`"分两种画法（缺字段 = 库内件，
    与 `fx/module.js` 的旧载荷口径同一条）。
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
                **({"tag": CUSTOM_TAG, "name": entry.name} if entry.custom else {}),
            }
            for entry in table.entries
        ],
        "legacy": [
            {"command": command, "description": meaning}
            for command, meaning in LEGACY_COMMANDS
        ],
    }


def _require_command_shape(slug: str, command: str) -> None:
    """命令字符的形状判据：单个可打印 ASCII（不含空白、不含 `'` 与 `\\`）。

    形状在 `hwcheck_recipe` 的 `console` 段已经判过（必须单字符），这里再判
    一次是因为**校验的判据面不同**：那边判的是"配方文件写得对不对"，这里判的
    是"能不能当命令表的一格"（非 ASCII / 空白字符在串口上敲不出来，也不是
    命令）。两处都在，错的方向才安全。**自建件分出来的字符也过这一处**
    （工单 06：形状判据只有这一个出处，分配的池子将来改了也同样受它管）。

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
            f"{slug!r} 的控制台命令 {command!r} 不能当命令字符："
            "只能是**一个可打印的 ASCII 字符**（串口上敲得出来的那种，"
            "不要空白 / 中文 / 多字符），也不要单引号 `'` 与反斜杠 `\\`"
            "——这两个字符进不了 C 字符字面量（`case '\\'':` 编不过），"
            "渲染器不会为它们转义"
        )


def _custom_candidates(slug: str) -> tuple[str, ...]:
    """自建件分字符时的**候选顺序**：先 id 里出现的字母 / 数字，再兜底池。

    为什么先看 id：分出来的字符要**可记**——学生手里那件叫 `mine_hall`，命令台
    给它的字符就是 `h`，比"按顺序发一个 `a`"好记得多。id 里的字符都被占了才退到
    `CUSTOM_COMMAND_FALLBACK`（`mine_gyro` 恰好四个字母全是保留字 `g/y/r/o`，
    于是它拿兜底池的第一个可用字符——这条不是缺陷，是"保留字不许被抢"的必然）。

    判据与渲染共用一个形态：候选一律**小写**（大小写不敏感是"同一个命令"，
    与配方那一侧 `_normalize` 同一口径）。
    """
    stem = slug[len(DEVICE_ID_PREFIX):] if slug.startswith(DEVICE_ID_PREFIX) else slug
    candidates: list[str] = []
    for char in stem.lower():
        if char.isascii() and char.isalnum() and char not in candidates:
            candidates.append(char)
    for char in CUSTOM_COMMAND_FALLBACK:
        if char not in candidates:
            candidates.append(char)
    return tuple(candidates)


def _declared_command_characters(console: RecipeConsole) -> tuple[str, ...]:
    """一条配方声明的**首选 + 候选**（按声明顺序、按归一形态去重）= 让位顺序。

    归一后去重是必须的：`command = "t"` 与 `candidates = ["T"]` 是同一个命令
    （大小写不敏感），不去重就会"试两遍同一个字符"，白占一格让位机会。
    """
    ordered: list[str] = []
    keys: set[str] = set()
    for char in (console.command, *console.candidates):
        key = _normalize(char)
        if key in keys:
            continue
        keys.add(key)
        ordered.append(char)
    return tuple(ordered)


def _recipe_command(
    slug: str, console: RecipeConsole, seen: Mapping[str, ConsoleEntry]
) -> str:
    """给一条配方分配命令字符：**首选优先、候选次之**，取第一个没被占用的。

    工单 `hwcheck-specialize/01` 的让位机制。为什么要有它：命令空间一共 31 个
    字符，而专精件一多，"首字母记法"必然撞车（`sht20` / `sht30` / `sgp30` /
    `servo` / `sr04` 都想用 `s`）——撞车的后果是**构建期 400**，等于"专精面变宽"
    直接兑换成"能勾的组合变少"。让位之后，学生看到的仍是"一件一个字符"。

    三条判据（任一不满足即红，**不静默覆盖**）：

    1. **保留字不碰**（`r/y/g/o/b` 与帮助 `?`）：`_require_command_shape` 之后逐字
       判——**声明即判**，不看这次轮不轮得到它。若等到"轮到它时"才判，同一份配方
       会因为旁边勾了哪几件而时而报错、时而静默通过；
    2. **已占用的不抢**：按声明顺序找第一个空闲字符；
    3. **分不出来当场红**（大声、带数字、给两条出路）：不静默少一条——页面上写着
       "敲这个复测"、板上却不认，是这一层最坏的坏法。

    确定性 = 纯函数：只依赖（声明顺序 + 表里已占的字符），不排序、不看时间、不随机。
    """
    declared = _declared_command_characters(console)
    for char in declared:
        _require_command_shape(slug, char)
        key = _normalize(char)
        if key not in RESERVED_COMMANDS:
            continue
        owner = dict(LEGACY_COMMANDS).get(key)
        origin = (
            f"库内既有命令（{key}：{owner}，已上过板）"
            if owner
            else "固定的帮助命令"
        )
        raise HwCheckError(
            f"{slug!r} 的控制台命令 {key!r} 与{origin}冲突："
            "既有命令的语义一个字节不动，配方命令只能**追加**——"
            "请换一个字符（检测页的帮助文案会列出现有命令）"
        )
    for char in declared:
        key = _normalize(char)
        if key in seen:
            continue
        return key
    occupied = "、".join(
        f"{char!r}（{seen[_normalize(char)].slug!r}）"
        for char in declared
        if _normalize(char) in seen
    )
    candidates = (
        f"，候选 {list(console.candidates)!r}" if console.candidates else "，没有声明候选"
    )
    raise HwCheckError(
        f"配方件 {slug!r} 的控制台命令字符分不出来了：它声明要用的字符 "
        + "、".join(repr(char) for char in declared)
        + f"（首选 {console.command!r}{candidates}）这一趟都已被占用：{occupied}；"
        + _pool_description()
        + f"，这一趟表里已经占了 {len(seen)} 个。"
        "出路：给这一件多加几个候选字符（`console.candidates`）、"
        "给首选换一个字符，或者去掉几件器件再生成一次"
    )


def _assign_custom_command(slug: str, seen: Mapping[str, ConsoleEntry]) -> str:
    """给一件自建件分一个**没被占用**的字符；分不出来 = 构建期大声失败。

    两条判据（与配方那一侧**同一处**）：保留字（`r/y/g/o/b` 与帮助命令）不碰、
    表里已有的字符不抢。分不出来只有一种可能——可用字符真的用完了，那时点名是
    哪一件排不上号、池子多大、已经被占掉几个，并给出出路（去掉几件 / 换个短一点的
    id）。静默少一条是这一层最坏的坏法：页面上写着"敲这个复测"，板上却不认。
    """
    for candidate in _custom_candidates(slug):
        key = _normalize(candidate)
        if key in RESERVED_COMMANDS or key in seen:
            continue
        _require_command_shape(slug, candidate)
        return candidate
    raise HwCheckError(
        f"自建件 {slug!r} 分不到复测字符了：" + _pool_description()
        + f"，现在表里已经占了 {len(seen)} 个（配方命令 + 其它自建件）——"
        "请去掉几件自建件，或者给它们换短一点的 id（字符优先取自 id），再生成一次"
    )


def build_console_table(
    sections: Sequence[RecipeSection],
    custom: Sequence[CustomSection] = (),
) -> ConsoleTable:
    """逐件小节 + 自建件小节 → 命令表（纯函数）。冲突 / 形状不对 → `HwCheckError`。

    三条判据（任一不满足即红，**不静默覆盖**）：

    1. 配方声明（首选与候选）的字符不得是库内既有命令（`r/y/g/o/b`）或帮助命令
       （`?`）——抢了它们的后果是"学生敲 r 不再点灯"，而那是已上过板的既有行为；
    2. **一件一个字符**：先试首选，被占则按 `console.candidates` 的声明顺序让位
       （工单 hwcheck-specialize/01，`_recipe_command`）；候选也用完 = 当场红，
       点名哪一件排不上号、池子多大、已被谁占。**自建件的字符是分配的**，所以它
       与配方命令、与另一件自建件都不会撞；真的分不出来（可用字符用尽）同样当场
       红（`_assign_custom_command`）；
    3. 字符必须是一个可打印 ASCII 字符（`_require_command_shape`）。

    表里的命令一律**规范化为小写**（声明 `L` 就是声明 `l`）：大小写不敏感是
    "同一个命令"而不是两个，规范化之后"判重"与"渲染 `case 'x': case 'X':`"
    才在同一个形态上成立（不规范化会出两个 `case 'L':` 重复标签，编不过）。

    没有 `console` 段的小节不进表（缺段 = 这一件没有复测命令，合法）；
    **自建件一律进表**（它们的探测小节就是"复测"本身，不存在"没声明"这回事）。
    顺序 = 配方命令（配方顺序 = `resolve_sections` 的验证顺序）在前、自建件在后
    ——与 main.c 里小节的顺序同一套"库内验证过的在前"，也是让位结果的唯一依据
    （页面与板上各建一次这张表，因此拿到的是同一组字符）。
    """
    entries: list[ConsoleEntry] = []
    seen: dict[str, ConsoleEntry] = {}
    for section in sections:
        console = section.console
        if console is None:
            continue
        # 分配（工单 hwcheck-specialize/01）：首选可用就用首选；首选被占就按候选
        # 顺序让位；全被占 / 声明了保留字 = 构建期红（`_recipe_command` 三条判据）。
        # 返回值**已经是归一形态**（小写）——声明的 `L` 就是 `l`，也只有一个小写
        # 形态，渲染器才不会出两个重复的 `case` 标签（编译器直接报错）。
        command = _recipe_command(section.slug, console, seen)
        entry = ConsoleEntry(
            command=command, slug=section.slug, description=console.description
        )
        seen[command] = entry
        entries.append(entry)
    for section in custom:
        command = _assign_custom_command(section.slug, seen)
        entry = ConsoleEntry(
            command=command,
            slug=section.slug,
            description=section.plan,
            # 复测入口 = 自建件自己的小节函数（命名规则归 hwcheck_custom：
            # 这里再拼一次 `hwcheck_custom_<id>` 就是第二个真相来源）
            func_name=section.func_name,
            custom=True,
            name=section.device.name,
        )
        seen[_normalize(command)] = entry
        entries.append(entry)
    return ConsoleTable(entries=tuple(entries))
