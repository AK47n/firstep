"""项目树遍历原语 —— "绕开噪音遍历工程目录"的唯一出处。

母版扫描 / 旧工程扫描 / 生成摘要 / 语料构建六处各走各的树（.git / 构建产物
目录 / 无三种互相矛盾的跳过规则）——同一棵树下文件是否被找到取决于走哪个
入口（判例：Listings/ 下的 .uvprojx keil 找得到、master 忽略）。本模块收拢：
一次遍历 = 一套统一跳过规则（.git 任意层级 + 构建输出目录顶层 / Keil 输出
目录任意层级，见 skip_project_noise），消费方只问"给我文件"，不再自走树。

不持业务形状（文件类别判定归 master.RuleCategory），纯路径迭代；叶子模块，
master / keil / ccs / generator 共同依赖，反向禁止。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

# 构建产物目录（Keil 编译输出，任意层级忽略；其余只在顶层忽略）
BUILD_ARTIFACT_DIRS = frozenset({"Debug", "Release", "Listings", "Objects"})

# 顶层忽略目录：.git + 构建产物目录
IGNORED_TOP_LEVEL_DIRS = frozenset({".git"}) | BUILD_ARTIFACT_DIRS

# 任意层级组件忽略的目录（其余忽略只在顶层生效，见 skip_project_noise）——
# Keil 把 Listings/Objects 建在 .uvprojx 所在目录，USER/ 工程时产物在
# USER/ 下，顶层匹配会漏
NESTED_IGNORE_DIRS = frozenset({"Listings", "Objects"})


def skip_project_noise(rel: str) -> bool:
    """路径是否命中忽略目录（POSIX 相对路径，目录组件级判定）。

    顶层 .git / Debug / Release / Listings / Objects + Keil 输出目录
    （Listings / Objects）任意层级匹配——六处遍历的同一跳过规则。
    """
    parts = rel.split("/")
    if parts[0] in IGNORED_TOP_LEVEL_DIRS:
        return True
    return any(part in NESTED_IGNORE_DIRS for part in parts)


def iter_project_files(project_dir: Path, *, pattern: str = "*") -> Iterator[Path]:
    """遍历工程目录下的文件（绝对路径、按路径排序，确定性），跳过统一噪音。

    pattern = rglob 通配模式："*" 全文件、"*.h" 头文件、"*.uvprojx" /
    "*.cproject" 工程文件、"*<suffix>" 按后缀。跳过规则见 skip_project_noise；
    消费方如需自定义附加过滤，在迭代结果上自行再筛。
    """
    for path in sorted(project_dir.rglob(pattern)):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if skip_project_noise(rel):
            continue
        yield path
