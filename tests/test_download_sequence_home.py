"""「一次分卷下载」只许有一个家（结构守卫，工单 resumable-download/10）。

**为什么值得单独一个文件**：这是一条**结构**判据，不是行为判据——它不看下载跑得对不对
（那是 `tests/test_full_task.py` / `tests/test_materials_task.py` 的事），只看
**那段动作序列有没有被抄回两条链路**。工单 09 的守卫（
`test_download_status_surface.py::test_retry_observation_has_a_single_home`）踩过一次坑：
第一版判据是**假命题 + 空断言**，看着在守、其实什么都没守。这里按当时学到的两条写：

1. **认形状**，不认名字：判「某个函数体里出现下载缝的装配 / 边车 / 可续判据」，
   而不是「某几个名字只许出现在某文件」——后者在失败路径上本来就是假命题；
2. **反向注入验证它会红**（第二个测试）：把重复抄回去，守卫必须指名道姓地转红。
   守卫自己也要有判据——「守卫只是装饰」正是工单 09 评审翻出来的那一类问题。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from contest_generator import full_task as ft
from contest_generator import materials_task as mt

# 一次下载的**动作集合**。前两个是纯动作（装配注入缝、写断点边车），
# 后两个是决定里的另外半边（判断半成品能不能续、校验失败时清掉它）。
# 之所以四个一起列：**「保留还是删除」这个决定就是这套动作**——把它抄回任务模块的人
# 必然连着装配与边车一起抄（旧正文就是这么写的），所以四者合起来才是「那段序列」的形状；
# 单看任何一个都会漏（判据第一版只列两个，评审指出「只抄清掉那一半不会红」）。
SEQUENCE_CALLS = {
    "as_task_downloader",
    "write_partial_marker",
    "is_resumable_partial",
    "clear_partial",
}


def _task_module_paths() -> list[Path]:
    """两条任务链路的源文件（守卫的扫描面；反向验证会把它换掉）。"""
    return [Path(ft.__file__), Path(mt.__file__)]


def _reaches(node: ast.AST, name: str) -> bool:
    """该函数体里有没有调用 `name`（属性名或裸名都算；注释 / docstring 里提到不算）。"""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute) and func.attr == name:
            return True
        if isinstance(func, ast.Name) and func.id == name:
            return True
    return False


def _defines(node: ast.AST, name: str) -> bool:
    """这棵树里有没有**定义** `name`（查「家在不在这儿」用，与 `_reaches` 的分工：
    前者问「有没有这个东西」，后者问「有没有调用它」）。"""
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
            return True
        if isinstance(child, ast.ClassDef) and child.name == name:
            return True
    return False


def _inlined_functions(source: str) -> list[str]:
    """→ 又抄了那段序列的函数（含行号与命中的动作），空表 = 干净。"""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        hits = sorted(name for name in SEQUENCE_CALLS if _reaches(node, name))
        if hits:
            found.append(f"{node.name}（第 {node.lineno} 行：{'、'.join(hits)}）")
    return found


def test_download_sequence_has_a_single_home() -> None:
    """结构守卫：两条任务链路里不许再出现「组装一次下载」的那段序列。

    代价已经付过（三种写法各付一次，见工单 10 的「先量再动」）：
    工单 03 的「长度到点 → 不发请求」两边各加一次；工单 07 的「复用返回的哈希」两边各改一次；
    工单 08 的三处「清了却没重下」是下载域改了、任务层两侧继续各自维护。
    判定「重复有没有回来」不能靠人眼，故这里机械查三件事：

    1. 任务模块的函数体里不再出现那段动作（装配缝 / 写边车 / 可续判据）；
    2. `task_download` 确实是它的家（三件事都在那里，防「把代码挪走、守卫却留在原地」）；
    3. 两条链路**确实**还在调那个共享原语（防「有人绕过它另写一条路」）。
    """
    from contest_generator import task_download as td

    for path in _task_module_paths():
        offenders = _inlined_functions(path.read_text(encoding="utf-8"))
        assert not offenders, (
            f"{path.name} 又把「一次下载」的动作序列抄回来了：{offenders}"
            "（应走 task_download.download_and_verify；本链路只留路径与卷级记账）"
        )

    home = Path(td.__file__).read_text(encoding="utf-8")
    missing = sorted(name for name in SEQUENCE_CALLS if not _reaches(ast.parse(home), name))
    assert not missing, f"共享件里少了这些动作：{missing}（序列的家不在 task_download 了？）"

    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    for module in (ft, mt):
        calls_home = _reaches(
            ast.parse(Path(module.__file__).read_text(encoding="utf-8")),
            "download_and_verify",
        )
        assert calls_home, (
            f"{Path(module.__file__).name} 不再调用共享原语 download_and_verify"
        )


# ---------------------------------------------------------------------------
# 工单 11：另外两件任务层共享事也各只有一个家
# ---------------------------------------------------------------------------

# 函数名 → 它该调用的那个共享件（**壳**只许剩这一句调用）。
# 口径：`_resolve_download`（注入缝的解析，原两处 7 行逐字相同）与
# `_restore_snapshot`（卷级断点的逐卷恢复，原两处 16 行相同）。
SHELL_ALLOWED = {
    "_resolve_download": "resolve_task_download",
    "_restore_snapshot": "restore_snapshot_parts",
}

# 共享件里必须出现的**形状**（防「壳还在、家搬空了」）。
# 每一项 = (判据说明, 谓词)：谓词吃该共享函数的 AST 节点，返回「家确实在这儿」。
HOME_MUST_HAVE = {
    "resolve_task_download": (
        ("读了实例属性表（`instance.__dict__`）",
         lambda node: any(isinstance(child, ast.Attribute) and child.attr == "__dict__"
                          for child in ast.walk(node))),
        ("按 `_download` 这个名字找注入的下载器",
         lambda node: any(isinstance(child, ast.Constant) and child.value == "_download"
                          for child in ast.walk(node))),
    ),
    "restore_snapshot_parts": (
        ("拿盘上内容哈希与清单比（`file_sha256`）",
         lambda node: any(isinstance(child, ast.Attribute) and child.attr == "file_sha256"
                          for child in ast.walk(node))),
        ("先判文件在不在（`is_file`）",
         lambda node: any(isinstance(child, ast.Attribute) and child.attr == "is_file"
                          for child in ast.walk(node))),
        ("按形状取存档项字段（`Mapping.get`）",
         lambda node: any(isinstance(child, ast.Attribute) and child.attr == "get"
                          for child in ast.walk(node))),
    ),
}


def _fat_shells(source: str) -> list[str]:
    """→「把共享件的规则抄回任务模块」的函数（空表 = 干净）。

    判据**认形状不认名字**（三样都要在同一个函数体里，避开误伤）：

    - 注入缝解析：`self.__dict__` 读 + `self.__dict__.get("_download")` 这个**字面名字**；
    - 逐卷恢复：`file_sha256` 调用 + `is_file` 判 + 读存档项的 `.get(...)`。

    为什么要把三样凑齐才算：单看任何一个都会误伤——`__init__` 里有
    `self._download = …`、`_resolve_download` 的壳里也有 `_download` 这个名字，
    而 `test_resume_rejects_tampered_local_file` 那种用例里到处都有 `is_file`。
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        def _has(predicate) -> bool:  # noqa: ANN001
            return any(predicate(child) for child in ast.walk(node))

        has_dict = _has(lambda c: isinstance(c, ast.Attribute) and c.attr == "__dict__")
        has_download_name = _has(
            lambda c: isinstance(c, ast.Constant) and c.value == "_download"
        )
        has_file_sha = _has(
            lambda c: isinstance(c, ast.Attribute) and c.attr == "file_sha256"
        )
        has_is_file = _has(lambda c: isinstance(c, ast.Attribute) and c.attr == "is_file")
        has_saved_get = _has(
            lambda c: isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute) and c.func.attr == "get"
        )

        shapes = []
        if has_dict and has_download_name:
            shapes.append("实例属性 × 类属性的解析")
        if has_file_sha and has_is_file and has_saved_get:
            shapes.append("逐卷恢复的哈希比对")
        if shapes:
            found.append(f"{node.name}（第 {node.lineno} 行：{'、'.join(shapes)}）")
    return found


def _fat_shell_bodies(source: str) -> list[str]:
    """→ **留了壳、但壳里不止一句转发**的函数（空表 = 壳真的只是壳）。

    判据 = 函数体（去掉 docstring）**只许剩一句**，且那一句必须调用共享件。
    为什么这条不能省（工单 11 评审指出）：上面那条只查「形状在不在」，
    于是**先调共享件、再顺手改一遍 `part.ok`** 这种「半抄」不会红——
    它把规则的一半又搬回了两条链路。壳的契约就一句转发，故这里数语句。
    """
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        helper = SHELL_ALLOWED.get(node.name)
        if helper is None:
            continue
        body = [stmt for stmt in node.body if not (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )]
        if len(body) != 1 or not _reaches(ast.Module(body=body, type_ignores=[]), helper):
            offenders.append(
                f"{node.name}（第 {node.lineno} 行：壳里有 {len(body)} 句，"
                f"应为 1 句 `{helper}(…)`）"
            )
    return offenders


# 判据的**阳性对照**：这段就是工单 11 改之前的旧正文形状，`_fat_shells` 必须抓到它。
# （没有这一段的「空表 = 干净」是假绿：判据写松了也一样是空表。）
FAT_SHELL_CONTROL = '''
class _Control:
    def _resolve_download(self):
        instance = self.__dict__.get("_download")
        if instance is None or instance is resumable_download:
            chosen = getattr(type(self), "_download", None) or resumable_download
            return chosen, chosen is resumable_download
        return instance, False

    def _restore_snapshot(self):
        snapshot = self.task_dir / SNAPSHOT_FILENAME
        if not snapshot.is_file():
            return
        saved_parts = {p["name"]: p for p in data.get("parts") or []}
        for part in self.parts:
            saved = saved_parts.get(part.name)
            dest = Path(str(saved.get("dest") or ""))
            if not dest.is_file():
                continue
            if download_resume.file_sha256(dest) == str(part.sha256 or "").lower():
                part.ok = True
'''

# 判据的**第二段阳性对照**（工单 11 评审补的那条路）：壳在、共享件也调了，
# 但**顺手把规则的一半又写了一遍**。只查「形状在不在」的判据抓不到这种「半抄」。
HALF_SHELL_CONTROL = '''
class _Half:
    def _restore_snapshot(self):
        restore_snapshot_parts(self.task_dir / SNAPSHOT_FILENAME, self._snapshot_pairs)
        for part in self.parts:
            saved = self._saved.get(part.name)
            if saved and saved.get("ok"):
                part.ok = True
                part.downloaded_bytes = part.size
'''


def _checked_task_paths() -> list[Path]:
    """守卫的扫描面（反向验证会换掉它）。"""
    return _task_module_paths()


def _helper_node(source: str, name: str) -> ast.AST | None:
    """共享件里那个函数的 AST 节点（查「家里到底有没有这套形状」）。"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def test_shared_task_helpers_have_a_single_home() -> None:
    """结构守卫：注入缝解析 / 逐卷恢复只能在 `task_download` 里有实现。

    工单 11 量出来的账：`_resolve_download` 两处**7 行逐字相同**（`22d0f643` 同一提交
    各抄一遍）、`_restore_snapshot` 两处 16 行相同。收完之后两条链路各留一行壳；
    本守卫查四件事（照上面那条的形状判据写，不认名字）：

    1. 任务模块里不再出现「解析 / 逐卷恢复」的形状（**整段抄回去**）；
    2. 壳**真的只是壳**——`_resolve_download` / `_restore_snapshot` 的函数体只许一句
       对共享件的转发（**防「先调共享件、再顺手把规则的一半抄一遍」**这种半抄；
       工单 11 评审指出第一版判据漏了这条路）；
    3. `task_download` 确实是它们的家（函数在、且家里的关键形状在）；
    4. 两条链路**确实**还在调共享件（防绕过）。
    """
    from contest_generator import task_download as td

    # 判据先自证（治「守卫只是装饰」）：两段阳性对照都必须被认出来
    control = _fat_shells(FAT_SHELL_CONTROL)
    assert len(control) == 2, f"判据连阳性对照都认不出来（假绿）：{control}"
    half = _fat_shell_bodies(HALF_SHELL_CONTROL)
    assert len(half) == 1, f"壳的语句数判据抓不到「半抄」：{half}"

    for path in _checked_task_paths():
        text = path.read_text(encoding="utf-8")
        offenders = _fat_shells(text) + _fat_shell_bodies(text)
        assert not offenders, (
            f"{path.name} 又把共享件的规则抄回来了：{offenders}"
            "（应走 task_download.resolve_task_download / restore_snapshot_parts；"
            "壳里只许留一句转发）"
        )

    home_source = Path(td.__file__).read_text(encoding="utf-8")
    home = ast.parse(home_source)
    for helper in SHELL_ALLOWED.values():
        assert _defines(home, helper), f"共享件里找不到 {helper}（家搬走了？）"
    for helper, marks in HOME_MUST_HAVE.items():
        node = _helper_node(home_source, helper)
        assert node is not None, f"共享件里找不到 {helper}"
        for label, predicate in marks:
            assert predicate(node), f"{helper} 里少了「{label}」——家搬空了？"

    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    for module in (ft, mt):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for helper in SHELL_ALLOWED.values():
            assert _reaches(tree, helper), (
                f"{Path(module.__file__).name} 不再调用共享件 {helper}"
            )


def test_shell_guard_turns_red_on_reinlined_body(tmp_path: Path) -> None:
    """**反向验证**：把规则抄回任务模块，守卫必须指名道姓转红。

    做法照上面那条反向验证的先例：取**磁盘上那个真守卫函数**的源码，拼上「抄回来的正文」
    （就是工单 11 改之前的旧写法），写进 `%TEMP%` 副本再执行——判据本体是真身那份，
    被扫的文件是副本，真身源码一个字节都不碰。
    """
    real_source = inspect.getsource(test_shared_task_helpers_have_a_single_home)
    injected = real_source + (
        "\n\nclass _Reinlined:\n"
        "    def _resolve_download(self):\n"
        "        instance = self.__dict__.get('_download')\n"
        "        if instance is None or instance is resumable_download:\n"
        "            chosen = getattr(type(self), '_download', None) or resumable_download\n"
        "            return chosen, chosen is resumable_download\n"
        "        return instance, False\n"
        "\n"
        "    def _restore_snapshot(self):\n"
        "        if download_resume.file_sha256(self.dest) == self.sha256:\n"
        "            self.ok = True\n"
    )
    copy_path = tmp_path / "reinlined_task.py"
    copy_path.write_text(injected, encoding="utf-8")

    namespace: dict[str, Any] = dict(globals())
    exec(compile(injected, "<reinlined-shell-guard>", "exec"), namespace)
    guard = namespace["test_shared_task_helpers_have_a_single_home"]
    original = namespace["_checked_task_paths"]
    namespace["_checked_task_paths"] = lambda: [copy_path]
    try:
        with pytest.raises(AssertionError) as caught:
            guard()
    finally:
        namespace["_checked_task_paths"] = original

    message = str(caught.value)
    assert "_Reinlined" in message or "抄回来" in message, message
    # 干净的那份也必须判绿（守卫不是「见谁都红」）
    assert _fat_shells(Path(ft.__file__).read_text(encoding="utf-8")) == []
    assert _fat_shells(Path(mt.__file__).read_text(encoding="utf-8")) == []
    assert _fat_shell_bodies(Path(ft.__file__).read_text(encoding="utf-8")) == []
    assert _fat_shell_bodies(Path(mt.__file__).read_text(encoding="utf-8")) == []


def test_guard_turns_red_on_reinlined_sequence(tmp_path: Path) -> None:
    """**反向验证**：把重复抄回去，守卫必须转红（否则它只是装饰）。

    做法：取**磁盘上那个真守卫函数**的源码，拼上「抄回来的那段序列」，写进 `%TEMP%`
    的副本里再执行——判据本体是真身那份，不另写一套；被扫的文件是副本，
    真身源码一个字节都不碰（本仓库演练脚本的铁律）。
    """
    real_source = inspect.getsource(test_download_sequence_has_a_single_home)
    injected = real_source + (
        "\n\ndef _reinlined(module) -> None:\n"
        "    module._download = download_resume.as_task_downloader(module._download)\n"
        "    download_resume.write_partial_marker(module.task_dir / 'x', 'u', 1)\n"
    )
    copy_path = tmp_path / "reinlined_task.py"
    copy_path.write_text(injected, encoding="utf-8")

    namespace: dict[str, Any] = dict(globals())
    exec(compile(injected, "<reinlined-guard>", "exec"), namespace)
    guard = namespace["test_download_sequence_has_a_single_home"]
    original = namespace["_task_module_paths"]
    namespace["_task_module_paths"] = lambda: [copy_path]
    try:
        with pytest.raises(AssertionError) as caught:
            guard()
    finally:
        namespace["_task_module_paths"] = original

    message = str(caught.value)
    assert "_reinlined" in message, message
    assert "抄回来" in message, message
    # 真身文件必须没被碰过（副本在 %TEMP%，这里再确认一次扫描面没被改）
    for path in _task_module_paths():
        assert path.name in {"full_task.py", "materials_task.py"}, path
