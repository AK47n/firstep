# -*- coding: utf-8 -*-
"""量具：把「解压后最深总长」按几种真实解压姿势算出来（工单 path-budget/01）。

为什么需要它：`0x80010135: 路径太长` 只在**资源管理器解压**时出现，上限 259 字符
（含解压根目录）。包内最短只说明一半——必须把用户可能的解压根目录代进去算，
否则「我们这里能解」会一直掩盖「用户那里解不了」。

用法：
    python .scratch/path-budget/measure-extract-budget.py            # 看当前工作树
    python .scratch/path-budget/measure-extract-budget.py --ceiling 259
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MATERIALS = REPO_ROOT / "sources" / "materials"

# 真实解压姿势（用户机器上的三种常见落点 + 一台很坏的情况）
ROOTS = (
    (r"C:\firstep", "解压到盘根短目录（推荐，README 新口径）"),
    (r"C:\Users\luoji\Desktop\firstep", "本机现状（用户名 5 字符）"),
    (r"C:\Users\Administrator\Desktop\firstep", "用户名 13 字符（报障机同量级）"),
    (r"C:\Users\Administrator\Desktop\firstep-v1.2.0\firstep", "浏览器下载多套一层（最坏常见姿势）"),
    (r"C:\Users\一个很长的中文用户名\Desktop\下载\firstep", "中文长用户名 + 中文目录（极端）"),
)


def deepest(root: pathlib.Path) -> tuple[int, str]:
    """返回 (最长「包内口径相对路径」的长度, 该路径)。

    口径 = `sources/materials/<相对 root>`，与完整包内条目路径一致；自定义 `--root`
    （如彩排副本）自动改用其父目录当基准，免得 `relative_to` 直接抛错。
    """
    base = REPO_ROOT if root == MATERIALS else root.parent
    local = root.relative_to(base).as_posix() if root != MATERIALS else "sources/materials"
    longest, longest_len = "", 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".bak-pathbudget"):
                continue
            path = pathlib.Path(dirpath) / name
            rel = f"{local}/{path.relative_to(root).as_posix()}"
            if len(rel) > longest_len:
                longest, longest_len = rel, len(rel)
    return longest_len, longest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="算解压后最深总长（资源管理器上限 259）")
    parser.add_argument("--ceiling", type=int, default=259, help="解压器上限（缺省 259）")
    parser.add_argument("--root", default=str(MATERIALS), help="资料库根")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root)
    rel_len, rel = deepest(root)
    print(f"资料库内最长包内路径：{rel_len} 字符")
    print(f"  {rel}")
    print()
    print(f"{'解压根目录':<52} {'总长':>5}  {'余量':>5}  判定")
    verdict_fail = 0
    for base, note in ROOTS:
        total = len(base) + 1 + rel_len  # +1 = 根目录与相对路径之间的分隔符
        margin = args.ceiling - total
        ok = margin >= 0
        verdict_fail += 0 if ok else 1
        print(f"{base:<52} {total:>5}  {margin:>5}  {'✅ 可解' if ok else '❌ 路径太长'}   {note}")
    print()
    print(f"判定：{[ '全部姿势可解' if verdict_fail == 0 else f'{verdict_fail} 种姿势会报 0x80010135' ]}")
    return 1 if verdict_fail else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
