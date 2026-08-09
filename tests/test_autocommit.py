"""写库动作自动 git 提交（工单 01）：tmp 下 git init 建伪库实测。

测点：add_module 落盘后自动提交（消息正确、提交只含库根路径）；库根在 git
工作树外静默跳过不炸；空变更不产生空提交；开关关闭不提交；配置损坏默认开；
结构测试防漏挂（工单列出的 8 个写函数都挂自动提交，防以后新增写函数漏挂）。
"""

from __future__ import annotations

import inspect
import json
import logging
import subprocess
from pathlib import Path

import pytest

from contest_generator import autocommit
from contest_generator.library import (
    add_module,
    add_platform_files,
    delete_module,
    update_module_description,
)
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


def test_all_write_functions_hook_autocommit():
    """结构防漏挂：工单列出的 8 个写函数源码都含 commit_after_write 调用与消息模板。

    以后新增写函数忘了挂自动提交（或消息模板漂移），此测试红。
    """
    import contest_generator.archive as archive
    import contest_generator.library as library
    import contest_generator.master_store as master_store
    import contest_generator.topic_library as topic_library

    hooks = {
        library.add_module: "lib: add module",
        library.update_module_description: "lib: update module description",
        library.add_platform_files: "lib: add platform files",
        library.remove_platform_files: "lib: remove platform files",
        library.delete_module: "lib: delete module",
        master_store.import_master: "lib: import master",
        topic_library.confirm_topics: "lib: confirm topics",
        archive.write_archive_entries: "lib: archive reference",
    }
    for func, message_fragment in hooks.items():
        source = inspect.getsource(func)
        assert "commit_after_write(" in source, func.__name__
        assert message_fragment in source, func.__name__
