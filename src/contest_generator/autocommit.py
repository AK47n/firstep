"""写库动作自动 git 提交（录入即进历史，工单 01）。

库 CRUD 落盘成功后自动 git add + commit：变更仅限库根子树（git add 限定
库根相对工作树根的路径，不 git add -A），不碰 src/ 等仓库其他文件。库根
在 git 工作树外（发布后用户自配路径）静默跳过不炸；无暂存变更不产生空
提交；git 命令异常非零只记日志不抛出——写库本身已成功，git 失败不能回滚
写库，宁可留下工作区变更下次人工提交。

库根约定：四库（modules / masters / topics / references）平级共居，调用
点传任一库目录（如 library/modules），库根 = 其父目录（library/）——
toplevel 探测与 git add 目标都按库根算（config.py 布局推导保证四库平级）。

开关：config.json 的 autocommit_enabled（默认 True）。配置缺失 / 损坏 /
字段非布尔 → 默认开——不能依赖 load_config，它缺 api_key 会抛
ConfigError，而自动提交在写库成功后运行，不该因配置问题失败，这里 lenient
读、绝不抛。
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 60  # git 挂起（钩子等）不拖死写库请求


def commit_after_write(library_root: Path, message: str) -> None:
    """写库成功后自动提交本次变更；开关关闭或库根在 git 工作树外时静默跳过。

    library_root 是任一库目录（modules / masters / topics / references 之
    一），库根 = 其父目录：toplevel 探测与 git add 目标都按库根算。写库本身
    已成功，本函数绝不抛——git 失败只记日志，工作区变更留待人工提交。
    """
    if not _autocommit_enabled():
        logger.info(
            "自动提交开关已关闭（config.json autocommit_enabled=false），跳过：%s",
            message,
        )
        return
    library_root = library_root.resolve()  # 相对路径 / 大小写差异 resolve 后统一
    library_root_dir = library_root.parent  # 库根 = 父目录（四库平级共居）
    toplevel = _git_toplevel(library_root_dir)
    if toplevel is None:
        return  # 库根在 git 工作树外：静默跳过，绝不打印噪音
    if library_root_dir == toplevel:
        # 库根就是工作树根：git add 会全仓暂存，违背"变更限库根子树"，拒绝
        logger.warning(
            "库根 %s 就是 git 工作树根，拒绝全仓暂存，跳过自动提交", library_root_dir
        )
        return
    rel_path = library_root_dir.relative_to(toplevel).as_posix()
    if _run_git(["add", "--", rel_path], toplevel) is None:
        return
    diff = _run_git(["diff", "--cached", "--quiet"], toplevel)
    if diff is None:
        return
    if diff.returncode == 0:
        logger.info("无待提交变更，跳过自动提交：%s", message)
        return
    if diff.returncode > 1:
        logger.warning(
            "git diff --cached 失败（rc=%s），跳过自动提交：%s",
            diff.returncode,
            message,
        )
        return
    commit = _run_git(["commit", "-m", message], toplevel)
    if commit is None:
        return
    if commit.returncode != 0:
        logger.warning(
            "自动提交失败（rc=%s）：%s（工作区变更保留，可人工提交）",
            commit.returncode,
            commit.stderr.strip(),
        )
        return
    logger.info("自动提交成功：%s", message)


def _autocommit_enabled() -> bool:
    """配置开关：autocommit_enabled 默认 True；缺失 / 损坏 / 非布尔 → 默认开。

    不能依赖 load_config：它缺 api_key 会抛 ConfigError，而自动提交在写库
    成功后运行，此时不该因配置问题失败。
    """
    try:
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if not isinstance(data, dict):
        return True
    value = data.get("autocommit_enabled", True)
    return value if isinstance(value, bool) else True


def _git_toplevel(path: Path) -> Path | None:
    """path 所在 git 工作树根；不在任何仓库内返回 None（静默，绝不抛）。"""
    result = _run_git(["rev-parse", "--show-toplevel"], path)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip())


def _run_git(
    args: Sequence[str], cwd: Path
) -> subprocess.CompletedProcess[str] | None:
    """运行 git 命令（cwd 限工作树根 / 库根）；执行失败（git 不可用 / 超时）返回 None。"""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(
            "git 命令执行失败（%s）：git %s，跳过自动提交", exc, " ".join(args)
        )
        return None
