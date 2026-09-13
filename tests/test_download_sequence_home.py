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
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

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
