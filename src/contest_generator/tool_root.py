"""工具根判定单源（工单 full-download/09）。

**为什么需要它**：工具根 = 含 `tools/`、`start-app.vbs`、`sources/`、`library/`
的那一层（更新包与完整包都以它为解压根）。此前四处各自用
`Path(__file__).parent.parent` 推根，在**源码直跑**（`PYTHONPATH=src`，
`start-app.bat` 正是这么起的）时全部算成 `<根>/src`：

- 更新器被拼成 `<根>/src/tools/update-app.py` → 子进程秒退，而编排误报成功；
- 资料库检查去 `<根>/src/sources/materials` 找基线 → 永远 `baseline-missing`；
- 版本更新记录去 `<根>/src/VERSIONS.md` 读 → 前台空态。

真机演练（沙箱）实测三处全中。故本模块是唯一出处：按「哪一层像工具根」判定，
调用方不再自己推。

无第三方依赖，可被任意模块导入（webapp / materials_update / wordlist /
changelog 都引它，避免循环导入）。
"""

from __future__ import annotations

from pathlib import Path

# 工具根的特征目录 / 文件（命中任一即认为是工具根）
ROOT_MARKERS: tuple[str, ...] = ("tools", "library", "sources", "assets")


def _looks_like_root(path: Path) -> bool:
    """该目录是否像工具根：有特征目录，或根级启动脚本。"""
    if (path / "start-app.vbs").is_file() or (path / "start-app.bat").is_file():
        return True
    return any((path / marker).is_dir() for marker in ROOT_MARKERS)


def find_tool_root(package_file: str | Path | None = None) -> Path:
    """定位工具根：候选顺序 = 包的上级 → 上级的上级 → 上级的上级的上级。

    - 源码直跑（`PYTHONPATH=src`）：包在 `<根>/src/contest_generator/` →
      第一候选 `<根>/src` 不像根，第二候选 `<根>` 命中；
    - 源码树正常导入 / 可编辑安装：`<根>/src/contest_generator/` 同上命中 `<根>`；
    - 站点包安装：`<site-packages>/contest_generator/` → 三级候选都不像根 →
      回退第一候选（保持既有可预期行为，调用方按「路径不存在」自处理）。
    """
    base = Path(package_file) if package_file is not None else Path(__file__)
    package_dir = base.resolve().parent
    candidates = [package_dir.parent, package_dir.parent.parent, package_dir.parent.parent.parent]
    for candidate in candidates:
        if _looks_like_root(candidate):
            return candidate
    return candidates[0]


def tool_root() -> Path:
    """本包所在工具的工具根（模块级便捷入口）。"""
    return find_tool_root(__file__)
