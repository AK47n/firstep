# -*- coding: utf-8 -*-
"""资料库路径减肥：把过长的相对路径压回安全区（工单 path-budget/01）。

背景（实测）
------------
完整包 `firstep-full-*.zip` 内最深相对路径原为 **223 字符**，来自两套厂商 LCD 例程
（`lckfb-地阔星移植手册/网盘下载/ili9341|ili9488/…`）。Windows 资源管理器
「全部解压缩」走老 API、硬卡 **259 字符**，于是「解压到桌面」这类常见姿势报
`0x80010135: 路径太长`；点「跳过」会**静默丢文件**。工具自身的解压（Python
zipfile）与 `tar.exe` 都走长路径 API，不受影响——所以病灶只有一个：**包内路径太长**。

规则：显式路径前缀改写表（可审计，不做通配"聪明"匹配）
------------------------------------------------------
1. `…/ili9341/<芯片包名>/1-Demo/`     → 去掉纯序号外壳层 `1-Demo`
2. `…/ili9488/<芯片包名>/1-Demo/`      → 同上
3. `…/Demo_Arduino/Install libraries/` → `…/Demo_Arduino/libs/`
4. `…/Demo_Arduino/Demo_UNO_Software_SPI/` 下 `x/x/` → `x/`（相邻同名层，厂商拷来的冗余）
5. 同 4，另外三个 `Demo_{UNO,Mega2560}_{Hardware,Software}_SPI/`

为什么安全
----------
- **只改目录名，不动任何文件名**：`.ino` 草图名与文件名一致（Arduino 硬要求）；
- 内容逐字节不变：脚本按 (size, sha256) 多重集比对「改名前 == 改名后」，不一致拒绝收工；
- **唯一性校验**：改名前先算全量「旧路径 → 新路径」，任何两个旧路径撞到同一新路径即
  拒绝执行（防止改名把文件覆盖掉）；
- **越界护栏**：每条结果必须满足「是旧路径的有序子序列」且只落在白名单族内；
- 全仓实测无任何代码/清单引用这些路径；`.materials-manifest.json` 由发版时重算。

用法
----
    python .scratch/path-budget/slim_materials_paths.py            # dry-run，只报告
    python .scratch/path-budget/slim_materials_paths.py --write    # 真改（清单自动备份）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MATERIALS = REPO_ROOT / "sources" / "materials"

# 改名前口径 = "sources/materials/<相对路径>"，与包内路径一致
PREFIX = "sources/materials/"

# 清单备份后缀（成功后清理；量具里也排除，免得淹没真信号）
BACKUP_SUFFIX = ".bak-pathbudget"

# 改名前后统一用「包内口径」= sources/materials/<相对路径>（与完整包内路径一致）。
# 规则表按资料库根口径书写，这里补上前缀——口径只有一处，避免两套路径混淆。
FAMILIES = tuple(
    PREFIX + fam
    for fam in (
        "lckfb-地阔星移植手册/网盘下载/ili9341",
        "lckfb-地阔星移植手册/网盘下载/ili9488",
    )
)

# —— 规则 1/2：去掉纯序号外壳层 1-Demo（族根之下紧邻的那一层）——
CHIP_DIRS = (
    "2.8inch_SPI_Module_ILI9341_MSP2807_V1.1",
    "3.5inch_SPI_Module_ILI9488_MSP3520_V1.1",
)
DROP_SHELL = tuple(
    f"{fam}/{chip}/1-Demo/"
    for fam in FAMILIES
    for chip in CHIP_DIRS
)
# 段级形态：`1-Demo`（仅有外壳段本身；判据是「栈里已有芯片包层」→ 见 transform）
DROP_SEGS = frozenset({"1-Demo"})

# —— 规则 3：目录名换短（Arduino 库名不受影响，库名是 LCDWIKI_* 那层）——
RENAME_PREFIXES = tuple(
    (f"{fam}/{chip}/Demo_Arduino/Install libraries/",
     f"{fam}/{chip}/Demo_Arduino/libs/")
    for fam in FAMILIES
    for chip in CHIP_DIRS
)
RENAME_SEGS = {"Install libraries": "libs"}

# —— 规则 4：厂商拷来拷去留下的「相邻同名目录层」，只在示例子树内折叠一层 ——
# 范围刻意收窄到 `Demo_*/` 之下：不碰示例目录名本身（那层是给人看的），
# 也不会造出「顶部示例目录整个折叠」产生的新同名对。
COLLAPSE_PREFIXES = tuple(
    f"{fam}/{chip}/Demo_Arduino/{demo}/"
    for fam in FAMILIES
    for chip in CHIP_DIRS
    for demo in (
        "Demo_UNO_Software_SPI",
        "Demo_UNO_Hardware_SPI",
        "Demo_Mega2560_Software_SPI",
        "Demo_Mega2560_Hardware_SPI",
    )
) + tuple(
    f"{fam}/{chip}/Demo_Arduino/libs/{lib}/Example/"
    for fam in FAMILIES
    for chip in CHIP_DIRS
    for lib in ("LCDWIKI_TOUCH", "LCDWIKI_SPI")
)


def transform(rel: str) -> str:
    """把「包内相对路径」映射成新路径（纯函数、幂等、可审计）。

    算法 = 一次「段栈」扫描，对**目录路径与文件路径同构**（这一点是硬要求：
    两者判据不一致会让算出的新路径与磁盘实际落点分叉，改名碰撞护栏随之失效——
    彩排时正是这么漏掉一处，结果文件停在旧路径上）。三段逻辑：

    1. 外壳段 `1-Demo`：栈里已有该芯片包层就丢弃（即「去掉一层」）；
    2. 换名段 `Install libraries` → `libs`；
    3. 折叠：仅当当前段与栈顶同名**且**已进入某条白名单前缀之内时丢弃。

    绝不用 `str.replace`——它会把路径中任何位置出现的同名段一并换掉。
    """
    segs = rel.split("/")
    stack: list[str] = []
    for seg in segs:
        if seg in DROP_SEGS and stack:
            continue
        name = RENAME_SEGS.get(seg, seg)
        if stack and stack[-1] == name:
            entered = any("/".join(stack).startswith(p) for p in COLLAPSE_PREFIXES)
            if entered:
                continue
        stack.append(name)
    return "/".join(stack)


def _hash(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: pathlib.Path) -> dict[str, tuple[int, str]]:
    """{包内口径相对路径: (size, sha256)}——改名前后逐字节比对用。

    排除脚本自己产生的清单备份（否则成功的那一次也会报「多出一个文件」，
    把真信号淹掉）。
    """
    out: dict[str, tuple[int, str]] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(BACKUP_SUFFIX):
                continue
            path = pathlib.Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            out[PREFIX + rel] = (path.stat().st_size, _hash(path))
    return out


def _is_subsequence(new_segs: list[str], old_segs: list[str]) -> bool:
    """new 必须是 old 的有序子序列（允许删段或按换名表改名，不允许调序或新增）。"""
    it = iter(old_segs)
    for seg in new_segs:
        for old in it:
            if old == seg or RENAME_SEGS.get(old) == seg:
                break
        else:
            return False
    return True


def dedupe(segs: list[str]) -> list[str]:
    """折叠相邻同名段。"""
    fixed: list[str] = []
    for seg in segs:
        if fixed and fixed[-1] == seg:
            continue
        fixed.append(seg)
    return fixed


def plan(root: pathlib.Path) -> tuple[list[tuple[pathlib.Path, pathlib.Path]], dict[str, int]]:
    """返回 (目录移动清单, 统计)；清单按「源深度**降序**」（孩子先落地）。

    排序为什么必须降序：执行模型是「先把子树从被丢弃的外壳里搬出来，再删外壳」，
    所以孩子必须排在父亲前面。用 dst 排序会两头不讨好——折叠让 dst 恒比 src 浅。
    """
    moves: list[tuple[pathlib.Path, pathlib.Path]] = []
    stats = {"files": 0, "dropped": 0, "renamed": 0, "collapsed": 0}
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        here = pathlib.Path(dirpath)
        stats["files"] += len(filenames)
        for name in list(dirnames):
            src = here / name
            rel_dir = src.relative_to(root).as_posix()
            # 规则表按「包内口径」书写 → 比较时补前缀，落盘时去前缀（口径只有一处）
            new_rel_dir = transform(PREFIX + rel_dir)[len(PREFIX):]
            if new_rel_dir == rel_dir:
                continue
            old_segs = rel_dir.split("/")
            new_segs = new_rel_dir.split("/")
            if len(new_segs) > len(old_segs) or not _is_subsequence(new_segs, old_segs):
                raise SystemExit(f"[拒绝] 变换越界：{rel_dir} → {new_rel_dir}")
            if not any((PREFIX + new_rel_dir).startswith(fam) for fam in FAMILIES):
                raise SystemExit(f"[拒绝] 变换越出白名单族：{rel_dir} → {new_rel_dir}")
            if len(new_segs) < len(old_segs):
                stats["dropped"] += 1
            elif new_segs[-1] != old_segs[-1]:
                stats["renamed"] += 1
            else:
                stats["collapsed"] += 1
            moves.append((src, root / new_rel_dir))
    moves.sort(key=lambda pair: pair[0].relative_to(root).as_posix().count("/"), reverse=True)
    return moves, stats


def check_injective(before: dict[str, tuple[int, str]]) -> dict[str, list[str]]:
    """旧路径 → 新路径必须一一对应；返回冲突表（非空 = 拒绝执行）。"""
    seen: dict[str, list[str]] = {}
    for old in before:
        seen.setdefault(transform(old), []).append(old)
    return {new: olds for new, olds in seen.items() if len(olds) > 1}


def affected_families(root: pathlib.Path, before: dict[str, tuple[int, str]]) -> dict[str, int]:
    """受影响文件按「前两段 + 芯片包」归类——人工复核：必须只落在预期的族里。"""
    fam: dict[str, int] = {}
    for old in before:
        if transform(old) == old:
            continue
        key = "/".join(old.replace(PREFIX, "").split("/")[:3])
        fam[key] = fam.get(key, 0) + 1
    return dict(sorted(fam.items(), key=lambda kv: -kv[1]))


def merge_into(src: pathlib.Path, dst: pathlib.Path) -> None:
    """把 src 目录内容递归并进 dst（同名子目录递归、同名文件以 src 为准）。

    为什么必须显式写：`shutil.move(src, dst)` 在 dst 是**已存在的目录**时语义是
    「搬进 dst 里面」（Windows 实测把 `parent/child` 塞进了 `parent`，凭空多出
    两层），而不是「并进 dst」。折叠规则的落点恰恰常是一个刚搬空的同名空壳，
    用错语义就会把目录结构改乱——这正是彩排要抓的那类错误。
    """
    for item in sorted(src.iterdir()):
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                merge_into(item, target)
                item.rmdir()
            else:
                shutil.move(str(item), str(target))
        else:
            if target.exists():
                target.unlink()
            shutil.move(str(item), str(target))
    src.rmdir()


def _prune_if_empty(path: pathlib.Path) -> None:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def apply_moves(moves: list[tuple[pathlib.Path, pathlib.Path]], *, write: bool) -> int:
    """执行改名。

    做法是「**先把子树从被丢弃的外壳里搬出来，再删外壳**」——等价于「子树的每一层
    各自改名」，而不是「父亲搬家时把孩子一起扛走」。区别很关键：

    - 扛走式（早先的实现）会把孩子**留在被丢弃的层里**，且孩子那条改名指令在父亲
      先落地后指向了不存在的旧路径——实测表现是 `…/child/child` 没被折叠、文件停在
      旧路径上，最后自校验报「内容集合发生变化」；
    - 搬出式必须先处理**更深**的层（清单按源深度降序），且在目的地**同位合并**
      （`源.parent == 目的地` 时直接并进去，不能 `shutil.move`——那是"搬进去"语义，
      会凭空多套一层）。

    三条不变式（每条都被彩排撞过，别再简化掉）：

    1. **深度降序**：先把孩子搬出外壳，再对外壳动手；
    2. **目的地已存在 = 同位合并**：`merge_into` 递归并进去；
    3. **其余冲突 = 拒绝**：两个互不相干的目录撞到同一目标会互相覆盖，必须当场炸掉
       而不是「跳过」（跳过 = 静默丢文件，正是本次要治的病）。
    """
    done = 0
    for src, dst in moves:
        if not write:
            continue
        if not src.exists():
            continue
        if src.parent == dst:
            merge_into(src, dst)
            done += 1
            continue
        if dst.exists():
            if not dst.is_dir():
                raise SystemExit(f"[拒绝] 目标不是目录：{src} → {dst}")
            merge_into(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        done += 1
    return done


def prune_empty(root: pathlib.Path) -> list[str]:
    removed: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
        here = pathlib.Path(dirpath)
        if here == root or filenames:
            continue
        if not any(here.iterdir()):
            removed.append(here.relative_to(root).as_posix())
            here.rmdir()
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="资料库路径减肥（只改名，不删内容）")
    parser.add_argument("--root", default=str(MATERIALS), help="资料库根（缺省 sources/materials）")
    parser.add_argument("--write", action="store_true", help="真改；缺省 dry-run 只报告")
    parser.add_argument("--ceiling", type=int, default=200, help="安全上限（字符，缺省 200）")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"资料库根不存在：{root}")

    before = snapshot(root)
    longest_before = max((len(k) for k in before), default=0)
    after_paths = sorted((transform(k) for k in before), key=len, reverse=True)
    longest_after = len(after_paths[0]) if after_paths else 0
    over = [p for p in after_paths if len(p) > args.ceiling]
    conflicts = check_injective(before)
    moves, stats = plan(root)

    print(f"资料库根：{root}")
    print(f"文件数：{len(before)}")
    print(f"最长路径：{longest_before} → {longest_after} 字符（上限 {args.ceiling}）")
    print(f"超上限文件：{sum(1 for k in before if len(k) > args.ceiling)} → {len(over)}")
    print(f"改名目录层：{len(moves)}（去外壳层 {stats['dropped']} / 换名 {stats['renamed']} / "
          f"折叠同名层 {stats['collapsed']}）")
    print(f"受影响文件：{sum(1 for k in before if transform(k) != k)}")
    print("受影响文件按族分布：")
    for key, count in affected_families(root, before).items():
        print(f"  {count:4d}  {key}")
    if conflicts:
        print(f"[拒绝] 新路径冲突 {len(conflicts)} 组——改名会让文件互相覆盖：")
        for new, olds in list(conflicts.items())[:5]:
            print(f"  → {new}")
            for old in olds:
                print(f"      {old}")
        return 2
    if over:
        print("仍然超限（需追加规则）：")
        for rel in over[:8]:
            print(f"  {len(rel):4d}  {rel}")
    print("改名样例：")
    for src, dst in moves[:6]:
        print(f"  {src.relative_to(root).as_posix()}")
        print(f"    → {dst.relative_to(root).as_posix()}")

    if not args.write:
        print("\n[dry-run] 未改动磁盘；确认无误后加 --write 执行。")
        return 0

    manifest = root / ".materials-manifest.json"
    if manifest.is_file():
        backup = manifest.with_name(manifest.name + BACKUP_SUFFIX)
        shutil.copy2(manifest, backup)
        print(f"清单已备份：{backup.name}（清单里仍是旧路径，稍后需重算——失败时用它回滚）")

    applied = apply_moves(moves, write=True)
    pruned = prune_empty(root)
    after = snapshot(root)

    # 判据：改名前路径**按规则映射后**必须与改名后逐一相等（键与 (size,sha256) 都算）。
    # 注意不能拿「改名前路径」直接比——改名就是要让路径变，那样必然不相等
    # （彩排时踩过：脚本误报「内容集合发生变化」，其实只是判据写错了对象）。
    expected = {transform(old): value for old, value in before.items()}
    keys_ok = sorted(expected) == sorted(after)
    values_ok = sorted(expected.values()) == sorted(after.values())
    if not (keys_ok and values_ok):
        print("[失败] 内容集合发生变化：")
        print(f"  路径集合相同：{keys_ok} / (size,sha256) 多重集相同：{values_ok}")
        missing = sorted(set(expected) - set(after))[:5]
        extra = sorted(set(after) - set(expected))[:5]
        print(f"  丢失：{missing}")
        print(f"  多出：{extra}")
        return 1

    report = {
        "root": str(root),
        "files": len(before),
        "moves": applied,
        "pruned_empty_dirs": pruned,
        "longest_before": longest_before,
        "longest_after": max((len(k) for k in after), default=0),
        "affected_files": sum(1 for k in before if transform(k) != k),
        "ceiling": args.ceiling,
    }
    out = pathlib.Path(__file__).with_name("slim-report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # 成功即清掉清单备份：清单本来就该在资料库变化后重算，留个旧路径的备份只会误导。
    backup = manifest.with_name(manifest.name + BACKUP_SUFFIX)
    if backup.is_file():
        backup.unlink()
    print(f"[完成] 改名 {applied} 层 / 清理空目录 {len(pruned)} 个 —— 文件数 {len(after)} 不变、"
          f"(size,sha256) 多重集逐项相等")
    print(f"最长路径：{report['longest_before']} → {report['longest_after']} 字符")
    print(f"报告：{out}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
