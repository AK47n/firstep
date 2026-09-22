# -*- coding: utf-8 -*-
"""会话态归属的结构钉（工单 webapp-state-into-ctx/03；工单 full-update-state-into-ctx/03 扩面）。

**为什么单独一个文件**：这条不变量管的是**模块级形状**（哪些东西不许挂在模块上），不是某条
端点的行为——跟用例住一起会让「改模块边界」与「改端点」两件事抢同一个文件（同款先例：
`tests/test_release_channel_home.py`、`tests/test_hwcheck_assembly_home.py`、`tests/test_llm_run.py`）。
判据是纯函数（源码进、事实出），红证可喂合成片段或**收走前那个提交**的源码，不必手改仓库文件。

不变量：**app 的会话态长在 `AppContext` 上，不长在模块上**。两条腿各管一处落点：

- **webapp 腿**（工单 01/02，收走前是模块级的 `_running_task_execs` / `_MATERIALS_LAST_CHECK` /
  `_materials_task`）；
- **full_task 腿**（工单 full-update-state-into-ctx/01/02，收走前是 `_LAST_CHECK` / `_FULL_TASK`
  加四个 accessor）。

两条腿共用**同一份规则**（`module_state_violations`），各自的目标由 `StateHome` 描述（模块点号名 +
文件显示名 + 搬走的名单 + `AppContext` 该有的字段；**不含磁盘路径**——纯函数不读盘）。模块级
不许再有「会话态形状」的赋值与 `global` 语句；搬走的名字不许回到模块级，也不许以**跨缝 import**、
**monkeypatch 路径字符串**、**模块对象别名**（`import …webapp as w` 后 `w._materials_task = None`）
这三种形状回到测试里。三条腿的「跨缝命中」只有**一个**出处：`cross_seam_hits`（聚合与逐文件
点名的用例都从它派生——2026-09-22 评审的 H1：用例里内联第二份 `|` + 交集就是一份会漂的副本）。

另有一条 `src/` 全域的腿：**整个 `src/` 里 `global` 语句数 = 0**（收走前实测全域只剩
`full_task.py` 一处，那是最后一个入口）。**如实记一条组织上的代价**：这条腿与前两条腿不是
严格同一条不变量（它不限「会话态形状」、不限落点、不看搬走名单），由第三个理由推动本文件变化
（Standards 轴评审的 Divergent Change 判断题）。仍然放在这里的理由：同属「模块级状态形状」
这一族，且**文件不能改名**——C6 的红证探针按 `test_webapp_state_home` 这个名字 import，改名会
破坏「那支探针一字不改」的验收；单列一个文件的收益抵不过这份耦合。将来若要拆，先看那条验收。

**判据面到哪儿为止（如实记账，别把它当万能）**：本文件全是 AST 启发式，抓得住的是**最可能的
回归形状**（`X = set()` / `X = {}` / `X = None` / `global X` / 跨缝 import / 别名直改），
抓不住的是刻意绕开的写法（`globals()[...]`、`setattr(模块, ...)`、f-string 或拼接出来的
monkeypatch 路径、`set() | set()` 这类表达式）。**真正的牙齿是行为判据**：状态一旦搬回模块级，
`tests/test_task_progress.py`、`tests/test_materials_task.py` 与 `tests/test_full_task.py` 里
那四条「两个 app 实例互不可见」的用例立刻变红。这条结构钉的作用是把意图写进源码形状层，
并在最可能的回归上响。

`_parse` 带 `@lru_cache`（判据保持「源码进、事实出」，缓存键就是源码文本）——**内存口径**：
缓存值是整棵 AST，驻留到本场测试结束（上限 512 份），目的是别让两条腿 × 每个测试文件把那
97 + 150 份源码反复解析（实测：扩面前 9s → 各自解析时 34s → 加缓存 6.6s）。调用方只读 AST，
没有副作用面。

`src/` 全域那条腿的**出路**（它是最强的一条，也可能拦下将来正当的写法）：模块级懒加载缓存若
真需要 `global X` 重新赋值，出路是就地改（`X.update(...)` / `X.setdefault(...)`）或把状态收进
`AppContext`——两个方向都已有先例（`syscfg_instances.INSTANCES_BY_SLUG` 就地建表、
`materials_pack._EXTRA_DIR_SLUGS` 就地 `setdefault`）。

判据「会话态形状」的口径：空容器字面量（`{}` / `[]`）、`None` 占位、以及**可变**容器构造
调用（`set()` / `dict()` / `list()` / `bytearray()` / `defaultdict()` / `OrderedDict()` /
`Counter()` / `ChainMap()` / `deque()` / `dict.fromkeys()`）——它们都是「空着起手、靠就地改或
`global` 重新赋值」的进程级状态。**不算**：非空常量表（`PLATFORM_DISPLAY_NAMES`）、算出来的
常量（`STATIC_DIR = Path(...)` / `_EXIT = os._exit`）、不可变容器（`()` / `frozenset()` /
`tuple()`——它们没有「就地改」这一说）。代价：将来若有人写 `SOME_OPTIONAL: Path | None = None`
这类**常量**占位也会被拦下，那时的出路是搬进 ctx 或换成非 None 的形状。

真红证见 `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`（base **显式钉** `5c9fc8b0`）
与 `.scratch/full-update-state-into-ctx/probe-01-pin-red-proof.py`（base **显式钉** `c6040566`，
它同时给 `src/` 全域那条腿出前后读数）——都不写 HEAD：提交之后 HEAD 就是新代码，红证会静默变绿；
两条腿的探针与守卫**共用本文件的聚合判据**（`state_violations` / `full_chain_state_violations`），
不另写一份聚合逻辑。判据强度自检是
`.scratch/webapp-state-into-ctx/probe-02-guard-strength.py`（**一支探针管整个文件**，随本文件
演化维护；当前 17 条腿的读数落在 `.scratch/full-update-state-into-ctx/guard-strength.txt`）。
"""

from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Mapping

REPO = Path(__file__).resolve().parents[1]
WEBAPP_PATH = REPO / "src" / "contest_generator" / "webapp.py"
FULL_TASK_PATH = REPO / "src" / "contest_generator" / "full_task.py"
SRC_DIR = REPO / "src"
TESTS_DIR = REPO / "tests"

# 搬进 AppContext 的名字（**webapp 腿**）。**两种拼法都收**：历史私有拼法（`_running_task_execs`）
# 与现在的字段名（`running_task_execs`）——只查一种会让「换个名字搬回模块级」永不红。
# ⚠ 名字里的 `_MOVED_STATE`（不带 WEBAPP）是**刻意保留**的：C6 的红证探针
# （`.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`）按这个名字 import，工单 03 的
# 验收要求那支探针一字不改仍能跑。
_MOVED_STATE = frozenset({
    "running_task_execs",
    "_running_task_execs",
    "materials_last_check",
    "_MATERIALS_LAST_CHECK",
    "materials_task",
    "_materials_task",
})

# 完整包那半搬走的名字（工单 full-update-state-into-ctx/01）：两个字段名 + 它们的模块级旧拼法
# + 四个退场的 accessor（函数名也算「名字回到模块级」的一种形状——搬回去就意味着状态又有
# 第二个出处）。
_FULL_TASK_MOVED_STATE = frozenset({
    "full_last_check",
    "_LAST_CHECK",
    "full_task",
    "_FULL_TASK",
    "get_full_task",
    "set_full_task",
    "last_check",
    "set_last_check",
})

# AppContext 上应有的字段名（正向判据：防「把状态删干净」式假绿）。两条腿各一份。
_WEBAPP_EXPECTED_FIELDS = ("running_task_execs", "materials_last_check", "materials_task")
_FULL_TASK_EXPECTED_FIELDS = ("full_last_check", "full_task")

# 两个判据落点：模块点号名 + 文件显示名（判据文案里那句「xxx.py：…」）+ 搬走的名单 +
# `AppContext` 该有的字段。两条腿跑**同一份规则**（`module_state_violations`）。
# 模块的磁盘路径不放进 `StateHome`：判据是「源码进、事实出」的纯函数，读盘那一步由用例与探针
# 自己做（用上面两个模块级路径常量）——`StateHome` 里再存一份 path 只会多一个没人读的字段。
_WEBAPP_MODULE = "contest_generator.webapp"
_FULL_TASK_MODULE = "contest_generator.full_task"


@dataclass(frozen=True)
class StateHome:
    """一处「会话态该归 AppContext」的落点（判据的输入，不是判据本身）。"""

    dotted: str
    display: str
    moved: frozenset[str]
    fields: tuple[str, ...]


_WEBAPP_HOME = StateHome(_WEBAPP_MODULE, "webapp.py", _MOVED_STATE, _WEBAPP_EXPECTED_FIELDS)
_FULL_TASK_HOME = StateHome(
    _FULL_TASK_MODULE, "full_task.py", _FULL_TASK_MOVED_STATE, _FULL_TASK_EXPECTED_FIELDS,
)

# 「会话态形状」认的可变容器构造（按函数名末段比：`defaultdict(set)` → `defaultdict()`）。
_SESSION_CONTAINER_CALLS = frozenset({
    "set", "dict", "list", "bytearray", "defaultdict", "OrderedDict", "Counter",
    "ChainMap", "deque", "fromkeys",
})
_EMPTY_CONTAINER_LITERALS = frozenset({"{}", "[]"})

# 模块级的复合语句：往里递归（`try: X = set()` 与直书在模块级是同一种东西）；
# 函数体与类体**不进去**（那里是局部变量）。
_COMPOUND_STATEMENTS = (
    ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While, ast.Match,
)


# ---------------------------------------------------------------------------
# 判据（纯函数：源码进，事实出）
# ---------------------------------------------------------------------------


def global_statements(source: str) -> list[int]:
    """源码里 `global X` 语句的行号（`global` = 函数要改模块里的东西 = 归属错位的症状）。"""
    return sorted(
        node.lineno for node in ast.walk(_parse(source)) if isinstance(node, ast.Global)
    )


def global_names(source: str) -> set[str]:
    """源码里所有 `global` 语句声明的名字（**不看**模块级有没有同名赋值）。

    `def f(): global _materials_task; _materials_task = None` 这种「只靠 global 改」的形状
    由它单独抓——模块级名字那条腿抓不到它。
    """
    return {
        name
        for node in ast.walk(_parse(source))
        if isinstance(node, ast.Global)
        for name in node.names
    }


def module_level_assignments(source: str) -> dict[str, str]:
    """模块级赋值：名字 → 值的形状标签（`set()` / `{}` / `None` / `annotation` / …）。

    覆盖复合语句块内（`try:` / `if:` / `with:` / `for:` / `match:`）与元组展开目标
    （`A, B = set(), None`）、海象（`(X := set())`）——它们与直书在模块级是同一种东西。
    **裸注解**（`_cache: dict[str, int]`，没有值）记成形状 `annotation`：那也是一个
    「没有常量值的模块级槽位」，值稍后再填（就地改，或函数里 `global` 赋值）。
    """
    out: dict[str, str] = {}
    for node in _module_level_statements(_parse(source).body):
        if isinstance(node, ast.Assign):
            pairs = _assign_pairs(node.targets, node.value)
        elif isinstance(node, ast.AnnAssign):
            if node.value is None:
                pairs = [(node.target.id, None)] if isinstance(node.target, ast.Name) else []
            else:
                pairs = _assign_pairs([node.target], node.value)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.NamedExpr)
            and isinstance(node.value.target, ast.Name)
        ):
            pairs = [(node.value.target.id, node.value.value)]
        else:
            continue
        for name, value in pairs:
            out.setdefault(name, "annotation" if value is None else _shape_of(value))
    return out


def module_level_names(source: str) -> set[str]:
    """模块级被赋过值 / 声明过注解的名字（`import` 不算）。"""
    names = set(module_level_assignments(source))
    for node in _module_level_statements(_parse(source).body):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def session_state_assignments(source: str) -> dict[str, str]:
    """模块级的「会话态形状」赋值：空容器 / `None` 占位 / 可变容器构造调用。

    这正是收走前那三样的形状（`_running_task_execs = set()` / `_MATERIALS_LAST_CHECK = {}` /
    `_materials_task = None`）。口径与不算的情形见文件头。
    """
    return {
        name: shape
        for name, shape in module_level_assignments(source).items()
        if _is_session_shape(shape)
    }


def imported_names(source: str, module_suffix: str) -> set[str]:
    """`from …<module_suffix> import …` 拿到的名字（按模块末段比）。"""
    out: set[str] = set()
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == module_suffix:
            out |= {alias.asname or alias.name for alias in node.names}
    return out


def module_object_aliases(source: str, module_dotted: str = _WEBAPP_MODULE) -> set[str]:
    """**模块对象**在本文件里的本地名（`import …webapp as w` / `from … import webapp as w`）。

    `module_dotted` = 判据落点（缺省 = webapp 腿；**尾参数带缺省**是刻意的：C6 的探针与既有
    用例按老签名调用，一个字都不用改）。
    """
    parent, _, leaf = module_dotted.rpartition(".")
    aliases: set[str] = set()
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_dotted:
                    aliases.add(alias.asname or module_dotted)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in (parent, module_dotted, "") or node.level:
                for alias in node.names:
                    if alias.name == leaf:
                        aliases.add(alias.asname or leaf)
    return aliases


def module_object_uses(source: str, module_dotted: str = _WEBAPP_MODULE) -> set[str]:
    """`<模块对象>.<名字>` 的属性访问拿到的名字（读与写都算）。

    这是**最可能的回归形状**：收走前 `tests/test_materials_task.py` 的 autouse 夹具正是
    `import contest_generator.webapp as webapp_mod` + `webapp_mod._materials_task = None`；
    完整包那半同款——`import contest_generator.full_task as ft` + `ft._FULL_TASK = None`。
    """
    aliases = module_object_aliases(source, module_dotted) | {module_dotted}
    out: set[str] = set()
    for node in ast.walk(_parse(source)):
        if not isinstance(node, ast.Attribute):
            continue
        path = _dotted(node)
        if path is None:
            continue
        for alias in aliases:
            head = alias + "."
            if path.startswith(head):
                out.add(path[len(head):].split(".")[0])
    return out


def module_attribute_paths(source: str, module_dotted: str = _WEBAPP_MODULE) -> set[str]:
    """`"<模块点号名>.<名字>"` 形状的**字符串字面量**（monkeypatch 路径）。

    2026-09-22 更名（原 `webapp_attribute_paths`）：判据参数化后它管的是任意落点，名字里的
    webapp 是 Mysterious Name（Standards 轴评审 ③）。C6 的红证探针**不用**这个函数，
    所以更名不影响「那支探针一字不改」那条验收；它的 stub 在强度探针里同步改了名。
    已知盲区：f-string / 拼接 / 变量拼出来的路径抓不到（见文件头「判据面到哪儿为止」）。
    """
    prefix = module_dotted + "."
    out: set[str] = set()
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith(prefix):
                out.add(node.value[len(prefix):])
    return out


def annotated_class_fields(source: str, class_name: str) -> set[str]:
    """类体里带注解的字段名（`x: T` / `x: T = …`；不看装饰器，名字如实叫 annotated）。"""
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    return set()


def cross_seam_hits(
    home: StateHome, test_sources: Mapping[str, str]
) -> dict[str, list[str]]:
    """各测试文件**跨缝取会话态**的名字（逐文件；空 = 干净）。

    这是三条腿（跨缝 import / 模块对象别名直改 / monkeypatch 路径字符串）与搬走名单求交集的
    **唯一出处**：聚合（`module_state_violations`）与「逐文件点名」那两条用例都从它派生——
    2026-09-22 评审抓到的 H1 就是「用例又内联了一份同样的 `|` + 交集」，而那份副本用的是
    **缺省落点**（webapp），参数化后已经是一份会漂的副本。用例要的是 offenders 明细，
    聚合要的是可读文案，两者都该建在这一个原始命中之上。
    """
    suffix = home.dotted.rsplit(".", 1)[-1]
    out: dict[str, list[str]] = {}
    for name, source in sorted(test_sources.items()):
        hits = (
            imported_names(source, suffix)
            | module_object_uses(source, home.dotted)
            | module_attribute_paths(source, home.dotted)
        ) & home.moved
        if hits:
            out[name] = sorted(hits)
    return out


def module_state_violations(
    home: StateHome,
    *,
    module_source: str,
    test_sources: Mapping[str, str],
    app_context_source: str,
) -> list[str]:
    """**落点 → 违规清单**的唯一聚合（空 = 绿）：模块级形状 + `AppContext` 正向字段 + 测试跨缝。

    两条腿（webapp / full_task）跑的就是这一个函数——判据单源；先例 `release-channel-dedupe`
    的教训：探针自己再写一遍聚合逻辑 = 一份会漂移的副本（评审实测已经漂了一处）。

    **两个源码串做成关键词参数**：它们都是「一段 Python 源码」，位置上挨着极易写反
    （2026-09-22 评审的判断题；本判据第一版就把 `full_task.py` 的源码当成了 `AppContext` 的
    出处，当场假红）。`app_context_source` 单独传（不取 `module_source`）：正向那条腿问的是
    「**`AppContext` 有没有这两个字段**」，而 `AppContext` 定义在 webapp 里；显式传还让红证探针
    在 base 版上跑时能喂 base 版的 webapp，而不是偷偷读当前树。
    """
    out: list[str] = []

    lines = global_statements(module_source)
    if lines:
        out.append(f"{home.display}：global 语句 {len(lines)} 处（行 {lines}）")
    state = session_state_assignments(module_source)
    if state:
        out.append(f"{home.display}：模块级「会话态形状」赋值 {state}")
    back = (module_level_names(module_source) | global_names(module_source)) & home.moved
    if back:
        out.append(f"{home.display}：会话态名字回到模块级 / global 名单 {sorted(back)}")
    missing = [
        n for n in home.fields if n not in annotated_class_fields(app_context_source, "AppContext")
    ]
    if missing:
        out.append(f"AppContext：缺会话态字段 {missing}")

    for name, hits in cross_seam_hits(home, test_sources).items():
        out.append(f"{name}：跨缝取会话态 {hits}")
    return out


def state_violations(webapp_source: str, test_sources: Mapping[str, str]) -> list[str]:
    """**webapp 腿**的聚合（签名与 C6 时一字不差——那条红证探针按它调用，不许改）。"""
    return module_state_violations(
        _WEBAPP_HOME,
        module_source=webapp_source,
        test_sources=test_sources,
        app_context_source=webapp_source,
    )


def full_chain_state_violations(
    full_task_source: str,
    test_sources: Mapping[str, str],
    app_context_source: str,
) -> list[str]:
    """**完整包腿**的聚合（工单 full-update-state-into-ctx/03；探针与守卫共用同一个）。

    `app_context_source` 必传（webapp 的源码）——见 `module_state_violations` 的说明。
    """
    return module_state_violations(
        _FULL_TASK_HOME,
        module_source=full_task_source,
        test_sources=test_sources,
        app_context_source=app_context_source,
    )


def src_global_statements(sources: Mapping[str, str]) -> dict[str, list[int]]:
    """源码映射 → 含 `global` 语句的文件与行号（空 = 全域没有。

    为什么单列一条 `src/` 全域的腿：`global` 是「归属错位」最硬的症状——函数得显式声明
    「我要改模块里的东西」。收走前实测全 `src/` 只剩 `full_task.py` 一处，收走后为 0，
    于是这条判据能把「下一个进程级状态」直接拦在闸门外（出路见文件头）。
    """
    out: dict[str, list[int]] = {}
    for name, source in sorted(sources.items()):
        lines = global_statements(source)
        if lines:
            out[name] = lines
    return out


# ---------------------------------------------------------------------------
# 内部件
# ---------------------------------------------------------------------------


@lru_cache(maxsize=512)
def _parse(source: str) -> ast.Module:
    """`ast.parse` + 屏蔽别的测试文件里的 `SyntaxWarning`。

    它们含合法的正则串（如 `"\\m"`），Python 3.14 解析那种字面量会告警；本判据只看
    import / 赋值 / `global` 的形状，不该把别人的告警引进自己的输出。

    **带缓存**（工单 full-update-state-into-ctx/03）：两条腿 × 每个测试文件 × 三条腿各
    `_parse` 一次 = 同一份源码被反复解析（本文件因此从 9s 涨到 34s）。键就是源码文本本身，
    同一场测试里同一个文件内容相同 → 命中缓存；纯函数，无副作用。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source)


def _module_level_statements(body: list[ast.stmt]) -> Iterator[ast.stmt]:
    """模块级语句 + 复合语句块内的语句（函数体 / 类体不进去）。"""
    for node in body:
        yield node
        if isinstance(node, _COMPOUND_STATEMENTS):
            for block in _nested_blocks(node):
                yield from _module_level_statements(block)


def _nested_blocks(node: ast.stmt) -> Iterator[list[ast.stmt]]:
    for attr in ("body", "orelse", "finalbody"):
        block = getattr(node, attr, None)
        if isinstance(block, list):
            yield block
    for handler in getattr(node, "handlers", None) or []:
        yield handler.body
    for case in getattr(node, "cases", None) or []:
        yield case.body


def _assign_pairs(targets: list[ast.expr], value: ast.expr) -> list[tuple[str, ast.expr]]:
    """(名字, 值) 对；元组 / 列表目标按位置与元组 / 列表值对齐（`A, B = set(), None`）。"""
    pairs: list[tuple[str, ast.expr]] = []
    for target in targets:
        if isinstance(target, ast.Name):
            pairs.append((target.id, value))
        elif isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts):
                sub_values = value.elts
            else:
                sub_values = [value] * len(target.elts)
            for element, sub_value in zip(target.elts, sub_values):
                pairs.extend(_assign_pairs([element], sub_value))
    return pairs


def _dotted(node: ast.expr) -> str | None:
    """`a.b.c` 形状的属性链 → `"a.b.c"`（不是纯 Name/Attribute 链 → None）。"""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _shape_of(value: ast.expr) -> str:
    """值的形状标签（判据只认形状，不认语义）。"""
    if isinstance(value, ast.Constant):
        return "None" if value.value is None else repr(value.value)[:20]
    if isinstance(value, ast.Dict):
        return "{}" if not value.keys else "{…}"
    if isinstance(value, ast.List):
        return "[]" if not value.elts else "[…]"
    if isinstance(value, ast.Call):
        func = value.func
        if isinstance(func, ast.Name):
            return f"{func.id}()"
        if isinstance(func, ast.Attribute):
            return f"{func.attr}()"
    return type(value).__name__


def _is_session_shape(shape: str) -> bool:
    if shape in ("None", "annotation") or shape in _EMPTY_CONTAINER_LITERALS:
        return True
    return shape.endswith("()") and shape[:-2] in _SESSION_CONTAINER_CALLS


def _python_sources(root: Path) -> dict[str, str]:
    """`root` 下全部 `.py` 源码（键 = 相对 `root.parent` 的 **POSIX** 路径，含子目录）。"""
    base = root.parent
    return {
        path.relative_to(base).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _test_sources(root: Path = TESTS_DIR) -> dict[str, str]:
    """`root` 下全部测试源码（缺省 = 仓库 `tests/**/*.py`，含 `conftest.py` 与子目录）。

    键 = 相对 `root.parent` 的 **POSIX** 路径：真树上是 `tests/xxx.py`，合成根上是
    `tests/test_fake.py`——与真红证探针喂进来的键同形（探针用仓库相对路径；`git show
    <rev>:<path>` 只认正斜杠，Windows 的 `str(Path)` 会给反斜杠，那条路会静默取不到文件）。
    `root` 可传：合成红证拿一个临时目录喂进来，证明**这条真树扫描腿有牙齿**（不是对空
    mapping 真空通过）。
    """
    return _python_sources(root)


def _src_sources(root: Path = SRC_DIR) -> dict[str, str]:
    """`src/**/*.py`（键 = `src/…`），给「全域没有 `global`」那条腿用。"""
    return _python_sources(root)


# ---------------------------------------------------------------------------
# 守卫
# ---------------------------------------------------------------------------


def test_webapp_has_no_global_statements():
    """模块级不许再出现 `global`：会话态与配置都经 ctx 读写（收走前实测 3 处）。"""
    source = WEBAPP_PATH.read_text(encoding="utf-8")
    lines = global_statements(source)
    assert not lines, f"webapp 又出现 global 语句（行 {lines}）——有状态的东西该归 AppContext"


def test_webapp_module_level_has_no_session_state():
    """模块级不许再有「会话态形状」的赋值（空容器 / None 占位 / 可变容器构造）。"""
    source = WEBAPP_PATH.read_text(encoding="utf-8")
    found = session_state_assignments(source)
    assert not found, (
        f"webapp 模块级又出现会话态形状的赋值：{found}"
        "——进程级可变状态该归 AppContext（工单 webapp-state-into-ctx/01–02）"
    )


def test_moved_state_names_stay_out_of_the_module():
    """工单 01/02 搬走的那三个名字不许回到模块级或 `global` 名单（含历史私有拼法）。"""
    source = WEBAPP_PATH.read_text(encoding="utf-8")
    back = (module_level_names(source) | global_names(source)) & _MOVED_STATE
    assert not back, f"会话态又回到 webapp 模块级：{sorted(back)}"


def test_app_context_owns_the_session_state():
    """正向判据：`AppContext` 必须持有这三样（防「把状态删干净」式假绿）。"""
    fields = annotated_class_fields(WEBAPP_PATH.read_text(encoding="utf-8"), "AppContext")
    missing = [name for name in _WEBAPP_EXPECTED_FIELDS if name not in fields]
    assert not missing, f"AppContext 缺会话态字段：{missing}"


def test_tests_do_not_reach_into_the_module_for_state():
    """测试不许跨缝拿这三个名字：跨缝 import / monkeypatch 路径字符串 / 模块对象别名直改。

    逐文件 offenders 走 `cross_seam_hits`（与聚合**同一份**原始命中）——2026-09-22 评审 H1：
    这里原先内联着第二份 `|` + 交集，是文件头点名禁止的「会漂的副本」。
    """
    sources = _test_sources()
    # 前置：扫描面不许塌（否则这条判据对空 mapping 真空通过，红不红都看不出）
    assert len(sources) >= 100, f"测试扫描面只有 {len(sources)} 个文件——判据会真空通过"
    assert "tests/test_webapp.py" in sources, "扫描面认不出 tests/ 下的测试文件"
    offenders = cross_seam_hits(_WEBAPP_HOME, sources)
    assert not offenders, (
        f"测试又伸手进 webapp 模块取会话态：{offenders}"
        "——测试该在自己构造的 AppContext 上注入与断言（工单 webapp-state-into-ctx/01–02）"
    )


def test_aggregate_shared_with_the_red_proof_probe_is_green():
    """真红证探针跑的就是 `state_violations`——这条给**那个聚合函数**一份自己的绿证。"""
    violations = state_violations(WEBAPP_PATH.read_text(encoding="utf-8"), _test_sources())
    assert not violations, "会话态归属聚合判据不为空：\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# 完整包腿（工单 full-update-state-into-ctx/01–03）
# ---------------------------------------------------------------------------


def test_full_task_module_level_has_no_session_state():
    """`full_task` 模块级不许再有「会话态形状」的赋值（收走前是 `_LAST_CHECK` / `_FULL_TASK`）。"""
    source = FULL_TASK_PATH.read_text(encoding="utf-8")
    found = session_state_assignments(source)
    assert not found, (
        f"full_task 模块级又出现会话态形状的赋值：{found}"
        "——完整包的会话态该归 AppContext（工单 full-update-state-into-ctx/01）"
    )


def test_full_task_has_no_global_statements():
    """`full_task` 不许再有 `global`（收走前实测 1 处 = `global _FULL_TASK`）。"""
    lines = global_statements(FULL_TASK_PATH.read_text(encoding="utf-8"))
    assert not lines, f"full_task 又出现 global 语句（行 {lines}）——有状态的东西该归 AppContext"


def test_full_task_moved_names_stay_out_of_the_module():
    """搬走的那批名字不许回到 `full_task` 模块级或 `global` 名单（含四个 accessor 的名字）。"""
    source = FULL_TASK_PATH.read_text(encoding="utf-8")
    back = (module_level_names(source) | global_names(source)) & _FULL_TASK_MOVED_STATE
    assert not back, f"完整包会话态又回到 full_task 模块级：{sorted(back)}"


def test_app_context_owns_the_full_chain_session_state():
    """正向判据：`AppContext` 必须持有 `full_last_check` / `full_task`（防删干净式假绿）。"""
    fields = annotated_class_fields(WEBAPP_PATH.read_text(encoding="utf-8"), "AppContext")
    missing = [name for name in _FULL_TASK_EXPECTED_FIELDS if name not in fields]
    assert not missing, f"AppContext 缺完整包会话态字段：{missing}"


def test_tests_do_not_reach_into_full_task_for_state():
    """测试不许跨缝拿完整包那批名字：跨缝 import / monkeypatch 路径 / 模块对象别名直改。

    注意「合法用法不算违规」：`import contest_generator.full_task as ft` 之后用
    `ft.FullDownloadTask` / `ft.SNAPSHOT_FILENAME` / `ft.TaskState` 是正当的——判据只认
    **搬走的那批名字**（交集）。
    """
    sources = _test_sources()
    assert len(sources) >= 100, f"测试扫描面只有 {len(sources)} 个文件——判据会真空通过"
    offenders = cross_seam_hits(_FULL_TASK_HOME, sources)
    assert not offenders, (
        f"测试又伸手进 full_task 模块取会话态：{offenders}"
        "——测试该在自己构造的 AppContext 上注入与断言（工单 full-update-state-into-ctx/01）"
    )


def test_full_chain_aggregate_shared_with_its_red_proof_probe_is_green():
    """完整包那条腿的红证探针跑的就是 `full_chain_state_violations`——给它一份自己的绿证。"""
    violations = full_chain_state_violations(
        FULL_TASK_PATH.read_text(encoding="utf-8"),
        _test_sources(),
        WEBAPP_PATH.read_text(encoding="utf-8"),
    )
    assert not violations, "完整包腿的聚合判据不为空：\n" + "\n".join(violations)


def test_src_has_no_global_statements_at_all():
    """整个 `src/` 不许有 `global` 语句（收走前实测只剩 `full_task.py` 一处，收走后 0 处）。

    这是本文件最有牙齿的一条：下一个「进程级状态」入口会当场在这里变红（出路见文件头）。
    """
    sources = _src_sources()
    # 下限 90：实测 `src/**/*.py` 是 **97** 个（2026-09-22）——原计划的 100 会当场假红；
    # 这条前置只防「扫描面塌成空/个位数」，不是版本快照。
    assert len(sources) >= 90, f"src 扫描面只有 {len(sources)} 个文件——判据会真空通过"
    assert "src/contest_generator/webapp.py" in sources, "扫描面认不出 src/ 下的模块"
    offenders = src_global_statements(sources)
    assert not offenders, (
        f"src 里又出现 global 语句：{offenders}"
        "——有状态的东西该归 AppContext，或就地改（见本文件头的「出路」）"
    )


def test_full_chain_state_pin_is_not_vacuous(tmp_path):
    """合成红证：把完整包收走前的写法（与各种回归形状）喂进同一套判据 → 当场认出。

    每条新腿各有自己的断言（含「只靠 `global`」「裸注解」「模块对象别名直改」「真树扫描」
    「老签名仍成立」这五条容易被别的腿兜住的）。真源码那份红证见
    `.scratch/full-update-state-into-ctx/probe-01-pin-red-proof.py`（base 显式钉 `c6040566`）。
    """
    before = (
        "_LAST_CHECK: dict[str, Any] = {}\n"
        "_FULL_TASK: FullDownloadTask | None = None\n"
        "SNAPSHOT_FILENAME = 'full-task.json'\n"
        "\n"
        "def set_full_task(task) -> None:\n"
        "    global _FULL_TASK\n"
        "    _FULL_TASK = task\n"
    )
    assert session_state_assignments(before) == {
        "_LAST_CHECK": "{}",
        "_FULL_TASK": "None",
    }
    assert global_statements(before) == [6]
    assert module_level_names(before) & _FULL_TASK_MOVED_STATE == {"_LAST_CHECK", "_FULL_TASK"}
    assert full_chain_state_violations(before, {}, "") == [
        "full_task.py：global 语句 1 处（行 [6]）",
        "full_task.py：模块级「会话态形状」赋值 {'_LAST_CHECK': '{}', '_FULL_TASK': 'None'}",
        "full_task.py：会话态名字回到模块级 / global 名单 ['_FULL_TASK', '_LAST_CHECK']",
        "AppContext：缺会话态字段 ['full_last_check', 'full_task']",
    ]

    # 「只靠 `global`」那一格（模块级**没有**同名赋值：`def f(): global X; X = …`）——不许靠
    # 「模块级名字」那条腿兜（2026-09-22 评审：这一格原先只有 webapp 腿有）
    global_only = (
        "def set_full_task(task) -> None:\n"
        "    global _FULL_TASK\n"
        "    _FULL_TASK = task\n"
    )
    assert global_names(global_only) == {"_FULL_TASK"}
    assert session_state_assignments(global_only) == {}  # 模块级确实没有赋值
    assert "full_task.py：会话态名字回到模块级 / global 名单 ['_FULL_TASK']" in (
        full_chain_state_violations(global_only, {}, "")
    )

    # 「裸注解」那一格（`_cache: dict[str, int]` = 没有常量值的模块级槽位，值稍后再填）
    assert session_state_assignments("_cache: dict[str, int]\n") == {"_cache": "annotation"}
    assert full_chain_state_violations("_cache: dict[str, int]\n", {}, "") == [
        "full_task.py：模块级「会话态形状」赋值 {'_cache': 'annotation'}",
        "AppContext：缺会话态字段 ['full_last_check', 'full_task']",
    ]

    # 判据② 的口径：非空常量表 / 算出来的常量 / 不可变容器都不算——完整包这半的常量照旧安全
    assert session_state_assignments("SNAPSHOT_FILENAME = 'full-task.json'\n") == {}
    assert session_state_assignments("DISK_HEADROOM_FACTOR = 1.5\n") == {}
    assert session_state_assignments("free_bytes = _free_bytes\n") == {}

    # 判据③ 的三种回归形状：跨缝 import / monkeypatch 路径字符串 / 模块对象别名直改
    assert imported_names(
        "from contest_generator.full_task import set_last_check\n", "full_task"
    ) == {"set_last_check"}
    assert module_attribute_paths(
        'monkeypatch.setattr("contest_generator.full_task.set_full_task", None)\n',
        _FULL_TASK_MODULE,
    ) == {"set_full_task"}
    alias_source = (
        "import contest_generator.full_task as ft\n"
        "\n"
        "def f() -> None:\n"
        "    ft._FULL_TASK = None\n"
        "    ft.get_full_task()\n"
    )
    assert module_object_aliases(alias_source, _FULL_TASK_MODULE) == {"ft"}
    assert module_object_uses(alias_source, _FULL_TASK_MODULE) & _FULL_TASK_MOVED_STATE == {
        "_FULL_TASK", "get_full_task",
    }
    # 另一条同样常见的写法：`from contest_generator import full_task as ft`
    from_import = (
        "from contest_generator import full_task as ft\n"
        "\n"
        "def test_x() -> None:\n"
        "    ft._LAST_CHECK.clear()\n"
    )
    assert module_object_aliases(from_import, _FULL_TASK_MODULE) == {"ft"}
    assert "tests/x_test.py：跨缝取会话态 ['_LAST_CHECK']" in full_chain_state_violations(
        "", {"tests/x_test.py": from_import}, ""
    )
    # 合法用法不该被认成违规（同一份源码里 ft.FullDownloadTask / ft.TaskState 就该放行）
    legal = (
        "from contest_generator import full_task as ft\n"
        "\n"
        "def test_x() -> None:\n"
        "    assert ft.SNAPSHOT_FILENAME\n"
        "    ft.FullDownloadTask\n"
        "    ft.TaskState.DOWNLOADING\n"
    )
    assert module_object_uses(legal, _FULL_TASK_MODULE) & _FULL_TASK_MOVED_STATE == set()

    # 判据③ 的「真树扫描」腿也要有牙齿：扫描根指到一个**真含**跨缝引用的目录 → 当场认出
    fake_root = tmp_path / "tests"
    fake_root.mkdir()
    (fake_root / "test_fake.py").write_text(
        "import contest_generator.full_task as ft\n"
        "\n"
        "\n"
        "def test_x() -> None:\n"
        "    ft._FULL_TASK = None\n",
        encoding="utf-8",
    )
    scanned = _test_sources(fake_root)
    assert list(scanned) == ["tests/test_fake.py"]
    assert "tests/test_fake.py：跨缝取会话态 ['_FULL_TASK']" in full_chain_state_violations(
        "", scanned, ""
    )

    # **兼容腿**：三个判据函数的尾参数带缺省 = C6 那条红证探针按老签名（一个位置参数）调用，
    # 一个字都不用改。这条不许靠别的腿兜（stub 掉缺省值它就该红）。
    assert module_object_uses(
        "import contest_generator.webapp as w\n"
        "\n"
        "w._materials_task = None\n"
    ) & _MOVED_STATE == {"_materials_task"}
    assert module_attribute_paths(
        'monkeypatch.setattr("contest_generator.webapp._materials_task", None)\n'
    ) == {"_materials_task"}
    assert module_object_aliases("import contest_generator.webapp as w\n") == {"w"}

    # 全域 global 腿自己的红证（真树那份在 `test_src_has_no_global_statements_at_all`）
    assert src_global_statements(
        {"src/a.py": "def f():\n    global X\n    X = 1\n", "src/b.py": "X = {}\n"}
    ) == {"src/a.py": [2]}
    assert src_global_statements({"src/b.py": "X = {}\n"}) == {}


def test_webapp_state_pin_is_not_vacuous(tmp_path):
    """合成红证：把收走前的写法（与各种回归形状）喂进同一套判据 → 当场认出。

    每条判据腿都有自己的用例——**包括「只靠 `global`」「裸注解」「真树扫描」这三条容易被
    别的腿兜住的腿**（对抗性验证实测：stub 掉 `global_names` 或 `_test_sources` 之后，早期
    版本仍 7 passed 全绿 = 那两条腿没有红证）。

    真源码那份红证见 `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`
    （收走前那个提交的 webapp.py + 全部测试文件 → 6 条违规 / 4 类）。
    """
    before = (
        "_running_task_execs: set[str] = set()\n"
        "_MATERIALS_LAST_CHECK: dict = {}\n"
        "_materials_task: ApplyTask | None = None\n"
        "PLATFORM_DISPLAY_NAMES = {'a': 'b'}\n"
        "\n"
        "def f() -> None:\n"
        "    global _MATERIALS_LAST_CHECK\n"
        "    _MATERIALS_LAST_CHECK.update({})\n"
    )
    assert session_state_assignments(before) == {
        "_running_task_execs": "set()",
        "_MATERIALS_LAST_CHECK": "{}",
        "_materials_task": "None",
    }
    assert global_statements(before) == [7]
    assert module_level_names(before) & _MOVED_STATE == {
        "_running_task_execs", "_MATERIALS_LAST_CHECK", "_materials_task",
    }
    assert state_violations(before, {}) == [
        "webapp.py：global 语句 1 处（行 [7]）",
        "webapp.py：模块级「会话态形状」赋值 "
        "{'_running_task_execs': 'set()', '_MATERIALS_LAST_CHECK': '{}', '_materials_task': 'None'}",
        "webapp.py：会话态名字回到模块级 / global 名单 "
        "['_MATERIALS_LAST_CHECK', '_materials_task', '_running_task_execs']",
        "AppContext：缺会话态字段 ['running_task_execs', 'materials_last_check', 'materials_task']",
    ]

    # 判据② 的口径：非空常量表 / 算出来的常量 / 不可变容器都不算
    assert session_state_assignments("PLATFORM_DISPLAY_NAMES = {'a': 'b'}\n") == {}
    assert session_state_assignments("STATIC_DIR = Path(__file__).parent / 'static'\n") == {}
    assert session_state_assignments("_EXIT: Callable[[int], Any] = os._exit\n") == {}
    assert session_state_assignments("EMPTY = ()\n") == {}          # 不可变：没有「就地改」
    assert session_state_assignments("EMPTY_FS = frozenset()\n") == {}

    # 判据② 的真实回归形状（评审实测过的那批）：注解式 / 容器构造 / 复合语句内 / 元组展开 / 海象
    assert set(session_state_assignments("_cache: dict = dict()\n")) == {"_cache"}
    assert set(session_state_assignments("_c = defaultdict(set)\n")) == {"_c"}
    assert set(session_state_assignments("_c = dict.fromkeys([])\n")) == {"_c"}
    assert set(session_state_assignments("try:\n    _c = set()\nexcept Exception:\n    _c = None\n")) == {"_c"}
    assert set(session_state_assignments("_a, _b = set(), None\n")) == {"_a", "_b"}
    assert set(session_state_assignments("(_w := set())\n")) == {"_w"}
    # 裸注解 = 没有常量值的模块级槽位：判据② 自己就要管（不许靠「模块级名字」那条腿兜）
    assert session_state_assignments("_cache: dict[str, int]\n") == {"_cache": "annotation"}
    assert state_violations("_hole: dict[str, int]\n", {}) == [
        "webapp.py：模块级「会话态形状」赋值 {'_hole': 'annotation'}",
        "AppContext：缺会话态字段 ['running_task_execs', 'materials_last_check', 'materials_task']",
    ]

    # 判据④ 的腿：`global` 只声明、模块级没有同名赋值那种形状（不许靠「模块级名字」那条腿兜）
    global_only = "def f() -> None:\n    global _materials_task\n    _materials_task = None\n"
    assert global_names(global_only) == {"_materials_task"}
    assert session_state_assignments(global_only) == {}   # 模块级确实没有赋值
    assert "webapp.py：会话态名字回到模块级 / global 名单 ['_materials_task']" in state_violations(
        global_only, {}
    )

    # 判据③ 的三种回归形状：跨缝 import / monkeypatch 路径字符串 / 模块对象别名直改
    assert imported_names("from contest_generator.webapp import _running_task_execs\n", "webapp") == {
        "_running_task_execs"
    }
    assert imported_names(
        "from contest_generator.webapp import AppContext, create_app\n", "webapp"
    ) == {"AppContext", "create_app"}
    assert module_attribute_paths(
        'monkeypatch.setattr("contest_generator.webapp._materials_task", None)\n'
    ) == {"_materials_task"}
    alias_source = (
        "import contest_generator.webapp as webapp_mod\n"
        "\n"
        "def f() -> None:\n"
        "    webapp_mod._materials_task = None\n"
        "    webapp_mod._MATERIALS_LAST_CHECK.update({})\n"
    )
    assert module_object_aliases(alias_source) == {"webapp_mod"}
    assert module_object_uses(alias_source) & _MOVED_STATE == {
        "_materials_task", "_MATERIALS_LAST_CHECK",
    }
    # 别名直改这一腿要能独立抓到（红证不许靠别的腿兜）：喂一个「模块级干净、只有测试伸手」的组合
    alias_use = (
        "import contest_generator.webapp as w\n"
        "\n"
        "def test_x() -> None:\n"
        "    w.running_task_execs.add('t')\n"
    )
    assert "tests/x_test.py：跨缝取会话态 ['running_task_execs']" in state_violations(
        "", {"tests/x_test.py": alias_use}
    )

    # 判据③ 的「真树扫描」腿也要有牙齿：把扫描根指到一个**真含**跨缝引用的目录 → 当场认出
    # （喂空 mapping / stub 掉 `_test_sources` 都会让这条红，见工单 Comments 的 stub 普查）
    fake_root = tmp_path / "tests"
    fake_root.mkdir()
    (fake_root / "test_fake.py").write_text(
        "import contest_generator.webapp as w\n"
        "\n"
        "\n"
        "def test_x() -> None:\n"
        "    w._materials_task = None\n",
        encoding="utf-8",
    )
    scanned = _test_sources(fake_root)
    assert list(scanned) == ["tests/test_fake.py"]
    assert "tests/test_fake.py：跨缝取会话态 ['_materials_task']" in state_violations("", scanned)

    # 已知盲区——**这一组不是契约，是边界记录**：判据面到哪儿为止写清楚，免得它悄悄存在。
    # 哪天判据变强到能抓它们，就该把这几条断言**反过来写**（那是好事，不是回归）。
    assert session_state_assignments("_c = set() | set()\n") == {}
    assert module_object_uses('setattr(w, "_materials_task", None)\n') == set()
    assert module_attribute_paths('x = "contest_generator.webapp" + ".y"\n') == set()

    # 判据④ 认得注解字段（也认得普通类属性 = 不算字段）
    assert annotated_class_fields(
        "@dataclass\nclass AppContext:\n    a: int = 0\n    b: dict = field(default_factory=dict)\n",
        "AppContext",
    ) == {"a", "b"}
    assert annotated_class_fields("class Other:\n    a: int = 0\n", "AppContext") == set()
