# -*- coding: utf-8 -*-
"""会话态归属的结构钉（工单 webapp-state-into-ctx/03）。

**为什么单独一个文件**：这条不变量管的是 **webapp 的模块级形状**（哪些东西不许挂在模块上），
不是某条端点的行为——跟 webapp 的用例住一起会让「改模块边界」与「改端点」两件事抢同一个
文件（同款先例：`tests/test_release_channel_home.py`、`tests/test_hwcheck_assembly_home.py`、
`tests/test_llm_run.py`）。判据是纯函数（源码进、事实出），红证可喂合成片段或**收走前那个
提交**的源码，不必手改仓库文件。

不变量：**app 的会话态长在 `AppContext` 上，不长在 webapp 模块上**——模块级不许再有
「会话态形状」的赋值与 `global` 语句；工单 01/02 搬走的那三个名字不许回到模块级，也不许以
**跨缝 import**、**monkeypatch 路径字符串**、**模块对象别名**（`import …webapp as w` 后
`w._materials_task = None`）这三种形状回到测试里。

**判据面到哪儿为止（如实记账，别把它当万能）**：本文件全是 AST 启发式，抓得住的是**最可能的
回归形状**（`X = set()` / `X = {}` / `X = None` / `global X` / 跨缝 import / 别名直改），
抓不住的是刻意绕开的写法（`globals()[...]`、`setattr(模块, ...)`、f-string 或拼接出来的
monkeypatch 路径、`set() | set()` 这类表达式）。**真正的牙齿是行为判据**：状态一旦搬回模块级，
`tests/test_task_progress.py` 与 `tests/test_materials_task.py` 里那两条「两个 app 实例互不
可见」的用例立刻变红。这条结构钉的作用是把意图写进源码形状层，并在最可能的回归上响。

判据「会话态形状」的口径：空容器字面量（`{}` / `[]`）、`None` 占位、以及**可变**容器构造
调用（`set()` / `dict()` / `list()` / `bytearray()` / `defaultdict()` / `OrderedDict()` /
`Counter()` / `ChainMap()` / `deque()` / `dict.fromkeys()`）——它们都是「空着起手、靠就地改或
`global` 重新赋值」的进程级状态。**不算**：非空常量表（`PLATFORM_DISPLAY_NAMES`）、算出来的
常量（`STATIC_DIR = Path(...)` / `_EXIT = os._exit`）、不可变容器（`()` / `frozenset()` /
`tuple()`——它们没有「就地改」这一说）。代价：将来若有人写 `SOME_OPTIONAL: Path | None = None`
这类**常量**占位也会被拦下，那时的出路是搬进 ctx 或换成非 None 的形状。

真红证见 `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`（base **显式钉**收走前
那个提交 `5c9fc8b0`，**不写 HEAD**：提交之后 HEAD 就是新代码，红证会静默变绿；探针与守卫
**共用本文件的 `state_violations`**，不另写一份聚合逻辑）。
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path
from typing import Iterator, Mapping

REPO = Path(__file__).resolve().parents[1]
WEBAPP_PATH = REPO / "src" / "contest_generator" / "webapp.py"
TESTS_DIR = REPO / "tests"

# 工单 01/02 搬进 AppContext 的三个名字。**两种拼法都收**：历史私有拼法（`_running_task_execs`）
# 与现在的字段名（`running_task_execs`）——只查一种会让「换个名字搬回模块级」永不红。
_MOVED_STATE = frozenset({
    "running_task_execs",
    "_running_task_execs",
    "materials_last_check",
    "_MATERIALS_LAST_CHECK",
    "materials_task",
    "_materials_task",
})

# AppContext 上应有的字段名（正向判据：防「把状态删干净」式假绿）。
_EXPECTED_FIELDS = ("running_task_execs", "materials_last_check", "materials_task")

# webapp 模块的两种指代形状：属性路径字符串（monkeypatch）与模块对象别名（import 后直改）。
_WEBAPP_MODULE = "contest_generator.webapp"
_WEBAPP_PATH_PREFIX = _WEBAPP_MODULE + "."

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


def module_object_aliases(source: str) -> set[str]:
    """webapp **模块对象**在本文件里的本地名（`import …webapp as w` / `from … import webapp as w`）。"""
    aliases: set[str] = set()
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _WEBAPP_MODULE:
                    aliases.add(alias.asname or _WEBAPP_MODULE)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in ("contest_generator", "contest_generator.webapp", "") or node.level:
                for alias in node.names:
                    if alias.name == "webapp":
                        aliases.add(alias.asname or "webapp")
    return aliases


def module_object_uses(source: str) -> set[str]:
    """`<webapp 模块对象>.<名字>` 的属性访问拿到的名字（读与写都算）。

    这是**最可能的回归形状**：收走前 `tests/test_materials_task.py` 的 autouse 夹具正是
    `import contest_generator.webapp as webapp_mod` + `webapp_mod._materials_task = None`。
    """
    aliases = module_object_aliases(source) | {_WEBAPP_MODULE}
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


def webapp_attribute_paths(source: str) -> set[str]:
    """`"contest_generator.webapp.<名字>"` 形状的**字符串字面量**（monkeypatch 路径）。

    已知盲区：f-string / 拼接 / 变量拼出来的路径抓不到（见文件头「判据面到哪儿为止」）。
    """
    out: set[str] = set()
    for node in ast.walk(_parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith(_WEBAPP_PATH_PREFIX):
                out.add(node.value[len(_WEBAPP_PATH_PREFIX):])
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


def state_violations(webapp_source: str, test_sources: Mapping[str, str]) -> list[str]:
    """**本文件全部判据的唯一聚合**：webapp 源码 + 各测试文件源码 → 违规清单（空 = 绿）。

    守卫用例与真红证探针**共用这一个函数**（先例 `release-channel-dedupe` 的教训：探针自己
    再写一遍聚合逻辑 = 一份会漂移的副本，评审实测已经漂了一处）。
    """
    out: list[str] = []

    lines = global_statements(webapp_source)
    if lines:
        out.append(f"webapp.py：global 语句 {len(lines)} 处（行 {lines}）")
    state = session_state_assignments(webapp_source)
    if state:
        out.append(f"webapp.py：模块级「会话态形状」赋值 {state}")
    back = (module_level_names(webapp_source) | global_names(webapp_source)) & _MOVED_STATE
    if back:
        out.append(f"webapp.py：会话态名字回到模块级 / global 名单 {sorted(back)}")
    missing = [
        n for n in _EXPECTED_FIELDS if n not in annotated_class_fields(webapp_source, "AppContext")
    ]
    if missing:
        out.append(f"AppContext：缺会话态字段 {missing}")

    for name, source in sorted(test_sources.items()):
        hits = (
            imported_names(source, "webapp")
            | module_object_uses(source)
            | webapp_attribute_paths(source)
        ) & _MOVED_STATE
        if hits:
            out.append(f"{name}：跨缝取会话态 {sorted(hits)}")
    return out


# ---------------------------------------------------------------------------
# 内部件
# ---------------------------------------------------------------------------


def _parse(source: str) -> ast.Module:
    """`ast.parse` + 屏蔽别的测试文件里的 `SyntaxWarning`。

    它们含合法的正则串（如 `"\\m"`），Python 3.14 解析那种字面量会告警；本判据只看
    import / 赋值 / `global` 的形状，不该把别人的告警引进自己的输出。
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


def _test_sources(root: Path = TESTS_DIR) -> dict[str, str]:
    """`root` 下全部测试源码（缺省 = 仓库 `tests/**/*.py`，含 `conftest.py` 与子目录）。

    键 = 相对 `root.parent` 的 **POSIX** 路径：真树上是 `tests/xxx.py`，合成根上是
    `tests/test_fake.py`——与真红证探针喂进来的键同形（探针用仓库相对路径；`git show
    <rev>:<path>` 只认正斜杠，Windows 的 `str(Path)` 会给反斜杠，那条路会静默取不到文件）。
    `root` 可传：合成红证拿一个临时目录喂进来，证明**这条真树扫描腿有牙齿**（不是对空
    mapping 真空通过）。
    """
    base = root.parent
    return {
        path.relative_to(base).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


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
    missing = [name for name in _EXPECTED_FIELDS if name not in fields]
    assert not missing, f"AppContext 缺会话态字段：{missing}"


def test_tests_do_not_reach_into_the_module_for_state():
    """测试不许跨缝拿这三个名字：跨缝 import / monkeypatch 路径字符串 / 模块对象别名直改。"""
    sources = _test_sources()
    # 前置：扫描面不许塌（否则这条判据对空 mapping 真空通过，红不红都看不出）
    assert len(sources) >= 100, f"测试扫描面只有 {len(sources)} 个文件——判据会真空通过"
    assert "tests/test_webapp.py" in sources, "扫描面认不出 tests/ 下的测试文件"
    offenders: dict[str, list[str]] = {}
    for name, source in sources.items():
        hits = (
            imported_names(source, "webapp")
            | module_object_uses(source)
            | webapp_attribute_paths(source)
        ) & _MOVED_STATE
        if hits:
            offenders[name] = sorted(hits)
    assert not offenders, (
        f"测试又伸手进 webapp 模块取会话态：{offenders}"
        "——测试该在自己构造的 AppContext 上注入与断言（工单 webapp-state-into-ctx/01–02）"
    )


def test_aggregate_shared_with_the_red_proof_probe_is_green():
    """真红证探针跑的就是 `state_violations`——这条给**那个聚合函数**一份自己的绿证。"""
    violations = state_violations(WEBAPP_PATH.read_text(encoding="utf-8"), _test_sources())
    assert not violations, "会话态归属聚合判据不为空：\n" + "\n".join(violations)


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
    assert webapp_attribute_paths(
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
    assert webapp_attribute_paths('x = "contest_generator.webapp" + ".y"\n') == set()

    # 判据④ 认得注解字段（也认得普通类属性 = 不算字段）
    assert annotated_class_fields(
        "@dataclass\nclass AppContext:\n    a: int = 0\n    b: dict = field(default_factory=dict)\n",
        "AppContext",
    ) == {"a", "b"}
    assert annotated_class_fields("class Other:\n    a: int = 0\n", "AppContext") == set()
