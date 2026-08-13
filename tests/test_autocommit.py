"""写库动作自动 git 提交（工单 01 + 深化）：tmp 下 git init 建伪库实测。

测点：add_module 落盘后自动提交（消息正确、提交只含库根路径）；库根在 git
工作树外静默跳过不炸；空变更不产生空提交；开关关闭不提交；配置损坏默认开；
工单深化补挂的直调写函数（add_reference / delete_reference / delete_topic /
delete_master / update_platform_identity）各一条提交消息断言；归档批次 N 条目
= 1 提交回归；结构测试防漏挂 = 五模块全部公开函数分类注册表（commit /
delegated / read 三类，未知即红，类别与源码事实不符即红）。
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from contest_generator import autocommit
from contest_generator.archive import write_archive_entries
from contest_generator.library import (
    add_module,
    add_platform_files,
    delete_module,
    update_module_description,
    update_platform_identity,
)
from contest_generator.master_store import delete_master
from contest_generator.reference_library import add_reference, delete_reference
from contest_generator.report import (
    ArchiveDecision,
    DistillationReport,
    ProjectComparison,
    ProjectStructure,
)
from contest_generator.topic_library import delete_topic
from tests.fakes import FakeLLM


@pytest.fixture
def default_on_config(monkeypatch, tmp_path) -> None:
    """开关默认开：配置路径指到 tmp 空配置（字段缺失 → 默认开）。"""
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(autocommit, "DEFAULT_CONFIG_PATH", config_path)


def _init_repo(tmp_path: Path) -> Path:
    """tmp 下建伪 git 仓库：配置本地身份，commit 不依赖全局 git 配置。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    return repo


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8"
    )


def _log_messages(repo: Path) -> list[str]:
    """仓库提交消息列表（旧 → 新；git log 默认新在前，反转为时间序）。"""
    return list(reversed(_git(repo, "log", "--format=%s").stdout.splitlines()))


def _modules_dir(repo: Path) -> Path:
    """模块库目录：库根 library/ 下的 modules/（与真实布局一致，提交目标是 library/）。"""
    return repo / "library" / "modules"


def _add_dht11(modules: Path) -> None:
    add_module(
        FakeLLM(),
        modules,
        slug="dht11",
        platform="stm32",
        description="DHT11 温湿度传感器驱动",
        files={
            "dht11.c": '#include "dht11.h"\nfloat dht11_read(void);\n',
            "dht11.h": "#pragma once\nfloat dht11_read(void);\n",
        },
    )


def test_add_module_autocommits(tmp_path, default_on_config):
    """add_module 落盘后自动提交：消息正确、提交只含库根路径。"""
    repo = _init_repo(tmp_path)

    _add_dht11(_modules_dir(repo))

    assert _log_messages(repo) == ["lib: add module dht11"]
    files = [
        line
        for line in _git(repo, "show", "--name-only", "--format=", "HEAD")
        .stdout.splitlines()
        if line
    ]
    assert files
    assert all(name.startswith("library/") for name in files)


def test_platform_writes_commit_in_order(tmp_path, default_on_config):
    """add_platform_files / delete_module 各一次提交，消息带 slug 与平台。"""
    repo = _init_repo(tmp_path)
    modules = _modules_dir(repo)
    _add_dht11(modules)

    add_platform_files(modules, "dht11", "mspm0", files={"mspm0/dht11.c": "/* mspm0 */\n"})
    assert _log_messages(repo)[-1] == "lib: add platform files dht11 mspm0"

    delete_module(modules, "dht11")
    assert _log_messages(repo) == [
        "lib: add module dht11",
        "lib: add platform files dht11 mspm0",
        "lib: delete module dht11",
    ]


def test_update_description_commit_message(tmp_path, default_on_config):
    """update_module_description 提交消息带 slug。"""
    repo = _init_repo(tmp_path)
    modules = _modules_dir(repo)
    _add_dht11(modules)

    update_module_description(FakeLLM(), modules, "dht11", "DHT11 温湿度传感器驱动（修订）")

    assert _log_messages(repo)[-1] == "lib: update module description dht11"


def test_outside_git_worktree_silently_skips(tmp_path, default_on_config, caplog):
    """库根不在任何 git 工作树内：写库照常、无提交、零日志噪音。"""
    caplog.set_level(logging.INFO)
    modules = tmp_path / "bare" / "library" / "modules"

    _add_dht11(modules)

    assert (modules / "dht11" / "manifest.json").is_file()  # 写库不受影响
    assert caplog.records == []  # 静默跳过，不打印噪音


def test_empty_change_produces_no_commit(tmp_path, default_on_config):
    """无暂存变更不产生空提交。"""
    repo = _init_repo(tmp_path)
    modules = _modules_dir(repo)
    _add_dht11(modules)
    assert len(_log_messages(repo)) == 1

    autocommit.commit_after_write(modules, "lib: noop")

    assert _log_messages(repo) == ["lib: add module dht11"]


def test_switch_off_skips_commit(tmp_path, monkeypatch):
    """config.json 的 autocommit_enabled=false：行为回到现状，不提交。"""
    repo = _init_repo(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"autocommit_enabled": False}), encoding="utf-8")
    monkeypatch.setattr(autocommit, "DEFAULT_CONFIG_PATH", config_path)

    _add_dht11(_modules_dir(repo))

    assert _git(repo, "rev-parse", "--verify", "HEAD").returncode != 0  # 无任何提交


def test_broken_config_defaults_to_enabled(tmp_path, monkeypatch):
    """配置损坏：默认开，照常提交（lenient 读、绝不抛）。"""
    repo = _init_repo(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text("{broken json", encoding="utf-8")
    monkeypatch.setattr(autocommit, "DEFAULT_CONFIG_PATH", config_path)

    _add_dht11(_modules_dir(repo))

    assert _log_messages(repo) == ["lib: add module dht11"]


# ---------------------------------------------------------------------------
# 工单深化补挂的直调写函数（4 工单清单 + update_platform_identity）
# ---------------------------------------------------------------------------


def _references_dir(repo: Path) -> Path:
    """参考文件库目录：库根 library/ 下的 references/（提交目标是 library/）。"""
    return repo / "library" / "references"


def _topics_dir(repo: Path) -> Path:
    """赛题库目录：库根 library/ 下的 topics/。"""
    return repo / "library" / "topics"


def _masters_dir(repo: Path) -> Path:
    """母版库目录：库根 library/ 下的 masters/。"""
    return repo / "library" / "masters"


def _add_reference_entry(refs: Path) -> str:
    """参考库写一条未锚定条目并返回条目 id（add_reference 落盘 + 自动提交）。"""
    entry = add_reference(
        refs,
        title="DHT11 参考例程",
        type="例程工程",
        description="DHT11 温湿度传感器参考例程",
        anchor_kind="none",
        anchor_value="",
        files={"example.c": "/* 例程 */\n"},
        kit_vocabulary=(),
    )
    return entry.id


def test_add_reference_autocommits(tmp_path, default_on_config):
    """add_reference 落盘后自动提交：消息带条目 id。"""
    repo = _init_repo(tmp_path)
    entry_id = _add_reference_entry(_references_dir(repo))

    assert _log_messages(repo) == [f"lib: add reference {entry_id}"]


def test_delete_reference_autocommits(tmp_path, default_on_config):
    """delete_reference 落盘后自动提交：消息带条目 id。"""
    repo = _init_repo(tmp_path)
    entry_id = _add_reference_entry(_references_dir(repo))

    delete_reference(_references_dir(repo), entry_id)

    assert _log_messages(repo) == [
        f"lib: add reference {entry_id}",
        f"lib: delete reference {entry_id}",
    ]


def test_delete_topic_autocommits(tmp_path, default_on_config):
    """delete_topic 落盘后自动提交：消息带赛题编号。"""
    repo = _init_repo(tmp_path)
    topic_dir = _topics_dir(repo) / "2026C"
    topic_dir.mkdir(parents=True)
    (topic_dir / "topic.md").write_text("题面", encoding="utf-8")
    (topic_dir / "manifest.json").write_text(
        json.dumps(
            {
                "year": "2026",
                "number": "C",
                "problem_md": "topic.md",
                "original_pdf": "",
                "programs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _git(repo, "add", "-A")  # 条目先进历史（真实流程 = confirm_topics 批次提交）
    _git(repo, "commit", "-m", "seed topic")

    delete_topic(_topics_dir(repo), "2026C")

    assert _log_messages(repo) == ["seed topic", "lib: delete topic 2026C"]


def test_delete_master_autocommits(tmp_path, default_on_config):
    """delete_master 落盘后自动提交：消息带平台名。"""
    repo = _init_repo(tmp_path)
    masters = _masters_dir(repo)
    (masters / "stm32").mkdir(parents=True)
    (masters / "stm32.json").write_text(
        json.dumps({"platform": "stm32", "sources": [], "warnings": []}),
        encoding="utf-8",
    )

    _git(repo, "add", "-A")  # 条目先进历史（真实流程 = import_master 自动提交）
    _git(repo, "commit", "-m", "seed master")

    delete_master(masters, "stm32")

    assert _log_messages(repo) == ["seed master", "lib: delete master stm32"]


def test_update_platform_identity_autocommits(tmp_path, default_on_config):
    """update_platform_identity 写回后自动提交：消息带 slug 与平台。

    工单清单外补挂：webapp 直调、save_manifest 是内部辅助不自提（调用方挂）。
    """
    repo = _init_repo(tmp_path)
    modules = _modules_dir(repo)
    _add_dht11(modules)

    update_platform_identity(modules, "dht11", "stm32", kit="ALX-AOA-FIT")

    assert _log_messages(repo) == [
        "lib: add module dht11",
        "lib: update platform identity dht11 stm32",
    ]


def test_archive_batch_single_commit(tmp_path, default_on_config):
    """归档批次 N 条目 = 1 提交（无双提交）：write_archive_entries 批次级单提交。

    批内条目不逐条提交——批次回滚 discard_entry_dirs 后 git 历史不留孤儿提交。
    """
    repo = _init_repo(tmp_path)
    proj = tmp_path / "sources" / "proj-a"
    archived = ("ui/oled_fonts.c", "sensors/dht11.c")
    for rel in archived:
        path = proj / rel
        path.parent.mkdir(parents=True)
        path.write_text(f"/* {rel} */\n", encoding="utf-8")
    comparison = ProjectComparison(
        projects=(
            ProjectStructure(
                project_dir=proj,
                name="proj-a",
                platform="stm32",
                files=archived,
                file_hashes={},
                config_summary=(),
            ),
        ),
        common=(),
        conflicts=(),
        unique=(),
        by_path={rel: ("proj-a",) for rel in archived},
        judgment=(),
    )
    report = DistillationReport(
        platform="stm32",
        projects=("proj-a",),
        keep=(),
        merge=(),
        exclude=(),
        main_c_preview="",
        uvprojx_preview="",
        archive=(
            ArchiveDecision("ui/oled_fonts.c", topic="2026C", reason="例程"),
            ArchiveDecision("sensors/dht11.c", topic="2026C", reason="例程"),
        ),
    )

    write_archive_entries(
        report,
        comparison,
        _references_dir(repo),
        summaries={"ui/oled_fonts.c": "字体表", "sensors/dht11.c": "传感器驱动"},
    )

    assert _log_messages(repo) == [
        "lib: archive reference ui/oled_fonts.c、sensors/dht11.c"
    ]


# ---------------------------------------------------------------------------
# 结构防漏挂（工单深化）：五模块全部公开函数分类注册表（commit / delegated / read）
# ---------------------------------------------------------------------------

# 写原语标记：read 类函数源码含任一即红（新写函数漏挂自动提交的判据）。
# 覆盖五模块全部落盘出口：事务（entry_transaction）、删除（delete_entry /
# rmtree / unlink / discard_entry_dirs）、写文件（write_json / write_text /
# _write_manifest / _write_meta / _write_files / _write_source_files）、
# 复制（copy2 / copytree）、改名（os.replace）、建目录（mkdir）、open。
_WRITE_MARKERS = (
    "entry_transaction(",
    "delete_entry(",
    "write_json(",
    "write_text(",
    "rmtree(",
    "copy2(",
    "copytree(",
    "os.replace(",
    "unlink(",
    "open(",
    "mkdir(",
    "discard_entry_dirs(",
    "_write_manifest(",
    "_write_meta(",
    "_write_files(",
    "_write_source_files(",
)

# 分类注册表：五模块全部公开函数 → (类别, 消息片段)。
# - commit：源码含 commit_after_write( 且含消息片段（写函数直接挂自动提交）
# - delegated：源码不含 commit_after_write(，写盘由调用方链兜底（archive_reference
#   的唯一调用方 write_archive_entries 已批次级提交；save_manifest 的调用方
#   update_module_description / update_platform_identity 均已挂）
# - read：源码不含任何写原语标记（纯读）
# 新增公开函数必须入表（未知即红）；类别与源码事实不符（read 含写原语 /
# delegated 含 commit / commit 缺挂点或缺消息片段）也红。参考 errors.py
# 反射测试先例。
_WRITE_FUNCTION_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    "library": {
        "list_modules": ("read", ""),
        "get_module": ("read", ""),
        "delete_module": ("commit", "lib: delete module"),
        "save_manifest": ("delegated", ""),
        "update_platform_identity": ("commit", "lib: update platform identity"),
        "draft_description": ("read", ""),
        "validate_description": ("read", ""),
        "add_module": ("commit", "lib: add module"),
        "update_module_description": ("commit", "lib: update module description"),
        "add_platform_files": ("commit", "lib: add platform files"),
        "remove_platform_files": ("commit", "lib: remove platform files"),
        "file_label": ("read", ""),
        # 工单 reference-library-hygiene/03 新增的读函数：截断文案单源共享层
        # （纯字符串变换，不落盘——llm / reference_library 共用）
        "truncate_content": ("read", ""),
        # 工单 01（模块普适化）新增的读函数：判据④机械词表扫描（纯文本，不落盘），
        # 结构测试与补录流程共用
        "find_topic_word_hits": ("read", ""),
    },
    "reference_library": {
        "validate_topic_anchor": ("read", ""),
        "module_kit_vocabulary": ("read", ""),
        "list_references": ("read", ""),
        # 在途工单（体量字段 file_count/size_bytes）新增的读函数：预先入表，
        # 两支先后合入 main 都不红
        "entry_stats": ("read", ""),
        "get_reference": ("read", ""),
        "search_references": ("read", ""),
        "delete_reference": ("commit", "lib: delete reference"),
        "read_fulltext": ("read", ""),
        "draft_description": ("read", ""),
        "add_reference": ("commit", "lib: add reference"),
        "archive_reference": ("delegated", ""),
        # 文件名搜索 / 文件打开工单新增的读函数：素材清单解析 + 文件定位，不落盘
        "list_entry_files": ("read", ""),
        "resolve_entry_file": ("read", ""),
        "match_entry_files": ("read", ""),  # 命中文件直出：只读素材清单，不落盘
        # 工单 01（清单域单源化）新增的读函数：素材清单文本生成器——不落
        # reference.json、不触发提交；调用方在 add_reference 前调用、随条目
        # 事务入库（脚本写入口，注册表只管 src 模块内落盘面）
        "build_material_manifest": ("read", ""),
    },
    "topic_library": {
        "validate_topic_key": ("read", ""),
        "confirm_topics": ("commit", "lib: confirm topics"),
        "resolve_number": ("read", ""),
        "list_topics": ("read", ""),
        "delete_topic": ("commit", "lib: delete topic"),
        "parse_confirm_entries": ("read", ""),
        "split_topics_document": ("read", ""),
    },
    "master_store": {
        "master_project_dir": ("read", ""),
        "analyze_structure": ("read", ""),
        "import_master": ("commit", "lib: import master"),
        "list_masters": ("read", ""),
        "get_master": ("read", ""),
        "delete_master": ("commit", "lib: delete master"),
    },
    "archive": {
        "prepare_archive": ("read", ""),
        "write_archive_entries": ("commit", "lib: archive reference"),
    },
}

_MODULES = ("library", "reference_library", "topic_library", "master_store", "archive")


def _module_functions() -> dict[str, dict[str, Callable[..., object]]]:
    """五模块全部函数（含私有，按模块分组）；公开与否在注册表校验时判断。"""
    return {
        module_name: {
            name: func
            for name, func in inspect.getmembers(
                importlib.import_module(f"contest_generator.{module_name}"),
                inspect.isfunction,
            )
            if func.__module__ == f"contest_generator.{module_name}"
        }
        for module_name in _MODULES
    }


def _callers_reach_commit(
    func_name: str, functions: dict[str, dict[str, Callable[..., object]]]
) -> bool:
    """delegated 校验：func_name 的调用方链（五模块内部）最终达 commit 类函数。

    调用图边：模块内任一函数源码含 "<name>(" 即视为调用 name——跨模块同名
    私有函数互认只会多连边、让校验更宽松，不掩盖漏登（未知函数本身即红，
    此处是次一级保证）。BFS 沿调用方方向找 commit 类函数。
    """
    commit_names = {
        name
        for module_name, funcs in functions.items()
        for name, (category, _) in _WRITE_FUNCTION_REGISTRY[module_name].items()
        if category == "commit"
    }
    all_names = {name for funcs in functions.values() for name in funcs}
    callers: dict[str, set[str]] = {}
    for funcs in functions.values():
        for caller_name, caller in funcs.items():
            source = inspect.getsource(caller)
            for name in all_names:
                if f"{name}(" in source:
                    callers.setdefault(name, set()).add(caller_name)
    seen: set[str] = set()
    queue = list(callers.get(func_name, ()))
    while queue:
        caller = queue.pop()
        if caller in seen:
            continue
        seen.add(caller)
        if caller in commit_names:
            return True
        queue.extend(callers.get(caller, ()))
    return False


def test_write_function_classification_registry():
    """结构防漏挂 v2：五模块全部公开函数入分类注册表且类别与源码事实相符。

    未知公开函数即红（新增写函数漏挂无从藏匿）；read 类含写原语即红（纯读
    函数不该落盘）；delegated 类含 commit_after_write( 即红且调用方链须达
    commit 类函数（写盘由调用方兜底）；commit 类须含 commit_after_write( 与
    消息片段（挂点丢失 / 消息漂移即红）。
    """
    functions = _module_functions()
    for module_name, funcs in functions.items():
        registry = _WRITE_FUNCTION_REGISTRY[module_name]
        for func_name, func in funcs.items():
            if func_name.startswith("_"):
                continue  # 私有函数由调用方链覆盖
            category, message_fragment = registry.get(func_name, ("", ""))
            assert category, (
                f"{module_name}.{func_name} 未入分类注册表——新增公开函数必须"
                "声明 commit / delegated / read 之一"
            )
            source = inspect.getsource(func)
            if category == "commit":
                assert "commit_after_write(" in source, (
                    f"{module_name}.{func_name} 分类 commit 却无 commit_after_write("
                )
                assert message_fragment in source, (
                    f"{module_name}.{func_name} 的消息片段 {message_fragment!r} 不在源码中"
                )
            elif category == "delegated":
                assert "commit_after_write(" not in source, (
                    f"{module_name}.{func_name} 分类 delegated 却含 commit_after_write("
                )
                assert _callers_reach_commit(func_name, functions), (
                    f"{module_name}.{func_name} 分类 delegated 但调用方链不达任何 commit 函数"
                )
            else:  # read
                assert not any(marker in source for marker in _WRITE_MARKERS), (
                    f"{module_name}.{func_name} 分类 read 却含写原语（漏挂自动提交？）"
                )
