# -*- coding: utf-8 -*-
"""演练包装层：drill-01 一字不改，只在运行前覆盖它的两个**参数**（工单 `release-v1.2.2/05`）。

## 为什么要这一层，而不是直接改 drill

`drill-01-upgrade.py` 是上一轮（B1）立下的**冻结量具**：判据本体（起点/终点版本自证、
保命项、四条隔离判据、`not_in_official == 0`）一个字都不许动，谁动了谁就没法再跟上一轮
的结果比较。而它有两处**参数**是钉死在上一轮的目标版本上的：

做法（照 `.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py` 的先例）：
把 drill **当文本读进来**，只改下面这几处，`compile` 进一个独立模块的命名空间再调 `main()`。
磁盘上那份 drill 全程不动——**跑完复核 sha256**，这就是「量具未被改动」的证据。

| 位置 | 原值 | 为什么要覆盖 |
|---|---|---|
| `TARGET_VERSION` | `"1.2.1"` | 本轮目标是 v1.2.2 |
| `OUTPUT_STEM`（模块级那个） | `"verify-01-upgrade"` | 两次运行会**互相覆盖证据**；本轮目标版本变了才暴露 |
| 日志里的字面量 `v1.2.1` / `官方 v1.2.1` | — | 留档用，必须与本轮一致，否则证据自相矛盾 |

`PACK_DIR`（`~/Desktop/firstep-pack`）不用改：官方完整包清单按 `TARGET_VERSION` 拼文件名，
跟着一起换。

## 为什么必须先动 `__name__`，以及本层要替 drill 做完哪件事

drill 末尾是 `if __name__ == "__main__": <收尾>`——**收尾（收 8020、写证据、总判）住在那条
分支里**，而本层要跳过它（否则 drill 会自己跑一遍 `main()`）。所以本层必须**把那段收尾
照着做一遍**（见下方 `run_drill_cleanup`）：调 `kill_listener(PORT)`、等一秒复核端口、
`RESULTS["cleanup"] = …`、`finish(exit_code)`、写含总判的证据、按 `problems` 决定退出码。
**漏掉它的后果是本层最坑的一次实测**：演练真跑完了，却一份证据都没落盘。

**别用裸 `exec`**：它在本函数的帧里执行 drill 的模块级代码，drill 顶层若抛 `SystemExit`
会被本函数的 `except` 接住，现象同样是"像什么都没发生"。

## 用法::

    python .scratch/release-v1.2.2/run-drill-01-v122.py --dry-run   # 前置核对，不下载
    python .scratch/release-v1.2.2/run-drill-01-v122.py             # 真跑（下 ~305 MB）
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DRILL = REPO / ".scratch" / "verify-gate-drills" / "drill-01-upgrade.py"

#: 本轮目标（覆盖 drill 里的同名常量）
TARGET_VERSION = "1.2.2"
#: 上一轮 drill 钉的目标版本（用来查「文本里还剩几处旧字面量」）
PREVIOUS_VERSION = "1.2.1"

#: 2026-09-19 冻结时的 drill-01 指纹（本轮开工前实测）。**不是**用来禁止改动 drill 的
#: （那是 git 的事），而是用来在证据里证明「这一次跑的确实是那一支量具」——指纹变了就是
#: 有人动过它，本轮结果与上一轮就不可比了，必须当场说清。
FROZEN_SHA256 = "52b6210061fde3974e3dcf8513f2609a26fa407a41336f1d09ef9bae994c7fe8"

#: 本轮的证据名。drill 的 `OUTPUT_STEM` 是**模块级常量**，两次运行会互相覆盖——
#: 上一轮 B1 的目标版本与 drill 自带的一致，从没暴露过；本轮目标版本变了，
#: 第一次（失败那次）运行的证据差点把第二次成功的覆盖掉（实测踩到）。
#: 改法必须落在**源码文本**上：`exec` 会重新执行模块级赋值，
#: 事先塞进命名空间的同名键会被覆盖（第一版就是这么失效的）。
EVIDENCE_STEM = f"verify-01-upgrade-v{TARGET_VERSION}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_source(text: str) -> tuple[str, dict]:
    """把 drill 源码里的目标版本参数换成本轮值，返回 (新源码, 偏离记账)。"""
    before = {
        "target_version_constant": text.count(f'TARGET_VERSION = "{PREVIOUS_VERSION}"'),
        "banner_literals": text.count(f"v{PREVIOUS_VERSION}"),
        "hardcoded_official": text.count(f"官方 v{PREVIOUS_VERSION}"),
        "evidence_stem": text.count('OUTPUT_STEM = "verify-01-upgrade"'),
    }
    patched = text.replace(
        f'TARGET_VERSION = "{PREVIOUS_VERSION}"', f'TARGET_VERSION = "{TARGET_VERSION}"', 1
    )
    # 证据名。**必须补模块级那一处**（`OUTPUT_STEM = "verify-01-upgrade"`）——
    # `--aftercare` 分支里那句 `global OUTPUT_STEM` 是函数内部的声明，
    # 改它只影响那一个分支（第一版就补错在这里，文件仍写到旧名，实测踩到）。
    patched = patched.replace(
        'OUTPUT_STEM = "verify-01-upgrade"', f'OUTPUT_STEM = "{EVIDENCE_STEM}"', 1
    )
    # `官方 v1.2.1` 先换（它是 `v1.2.1` 的超集，顺序反了会漏掉它自己的那一处）
    patched = patched.replace(f"官方 v{PREVIOUS_VERSION}", f"官方 v{TARGET_VERSION}")
    patched = patched.replace(f"v{PREVIOUS_VERSION}", f"v{TARGET_VERSION}")
    after = {
        "target_version_constant": patched.count(f'TARGET_VERSION = "{TARGET_VERSION}"'),
        "banner_literals": patched.count(f"v{TARGET_VERSION}"),
        "evidence_stem": patched.count(f'OUTPUT_STEM = "{EVIDENCE_STEM}"'),
        "leftover_previous": patched.count(f"v{PREVIOUS_VERSION}"),
    }
    return patched, {"before": before, "after": after}


def preflight(drill_text: str) -> list[str]:
    """开跑前的硬前置（不满足就别跑：白下 305 MB 还要回滚沙箱）。"""
    problems: list[str] = []
    if not DRILL.is_file():
        return [f"drill 不在：{DRILL}"]
    if f'TARGET_VERSION = "{PREVIOUS_VERSION}"' not in drill_text:
        problems.append(
            f"drill 里找不到 `TARGET_VERSION = \"{PREVIOUS_VERSION}\"`——"
            "要么量具被改过，要么上一轮的钉法变了，先看一眼再决定怎么覆盖"
        )
    manifest = Path.home() / "Desktop" / "firstep-pack" / (
        f"firstep-full-v{TARGET_VERSION}.manifest.json"
    )
    if not manifest.is_file():
        problems.append(
            f"官方完整包清单不在：{manifest}\n"
            f"    （drill 第 七 节要拿它量构成，缺了就跳过那一格 = 判据没了）"
        )
    return problems


def run_drill_cleanup(module: object, code: int) -> int:
    """照 drill 自己的 `__main__` 分支做完收尾（本层跳过了那条分支，必须替它做）。

    逐句对应 `drill-01-upgrade.py` 末尾那段：收 8020 → 等一秒复核 → 记 `cleanup` →
    `finish(code)` → 写含总判的证据 → 按 `problems` 定退出码。
    **判据不被本函数改动**：它只做收尾与落盘，``RESULTS["problems"]`` 是 drill 自己填的。
    """
    import time as _time  # noqa: PLC0415 —— 与 drill 末尾同一姿势

    killed = module.kill_listener(module.PORT)          # type: ignore[attr-defined]
    module.log("")                                      # type: ignore[attr-defined]
    module.log("## 收尾")                               # type: ignore[attr-defined]
    module.log(f"  收掉 8020 监听进程：{killed or '（无）'}")  # type: ignore[attr-defined]
    _time.sleep(1.0)
    leftover = module.listen_pids(module.PORT)          # type: ignore[attr-defined]
    module.log(f"  8020 端口{'已释放' if not leftover else f'**仍被占用 {leftover}**'}")  # type: ignore[attr-defined]
    module.log(f"  残留 python 进程：{module.python_processes() or '（无）'}")  # type: ignore[attr-defined]
    module.RESULTS["cleanup"] = {                       # type: ignore[attr-defined]
        "killed": killed, "leftover": leftover,
        "python_left": module.python_processes(),       # type: ignore[attr-defined]
    }
    code = module.finish(code)                          # type: ignore[attr-defined]
    problems = module.RESULTS["problems"]               # type: ignore[attr-defined]
    module.log("")                                      # type: ignore[attr-defined]
    module.log("## 总判")                               # type: ignore[attr-defined]
    module.log(f"  判红 {len(problems)} 条 / 卡住 "      # type: ignore[attr-defined]
               f"{len(module.RESULTS['stuck'])} 条")
    for item in problems:
        module.log(f"    · 判红：{item}")                # type: ignore[attr-defined]
    for item in module.RESULTS["stuck"]:                # type: ignore[attr-defined]
        module.log(f"    · 卡住：{item}")                # type: ignore[attr-defined]
    module.log(f"  B1「沙箱升级到 {module.TARGET_VERSION}」："  # type: ignore[attr-defined]
               f"{'PASS' if not problems else 'FAIL'}")
    module.RESULTS["verdict"] = {                       # type: ignore[attr-defined]
        "problems": problems, "stuck": module.RESULTS["stuck"],  # type: ignore[attr-defined]
        "pass": not problems,
    }
    (module.HERE / f"{module.OUTPUT_STEM}.txt").write_text(  # type: ignore[attr-defined]
        "\n".join(module.LINES) + "\n", encoding="utf-8")   # type: ignore[attr-defined]
    (module.HERE / f"{module.OUTPUT_STEM}.json").write_text(  # type: ignore[attr-defined]
        json.dumps(module.RESULTS, ensure_ascii=False, indent=2),  # type: ignore[attr-defined]
        encoding="utf-8")
    return code if not problems else 1


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    stamp = time.strftime("%Y%m%d-%H%M%S")
    drill_text = DRILL.read_bytes().decode("utf-8")
    drill_sha_before = sha256_of(DRILL)

    print("# drill-01 包装层（工单 release-v1.2.2/05）")
    print(f"  目标版本：v{TARGET_VERSION}（drill 自己钉的是 v{PREVIOUS_VERSION}）")
    print(f"  drill：{DRILL}")
    print(f"  drill sha256（跑前）：{drill_sha_before}")
    if drill_sha_before != FROZEN_SHA256:
        print(f"  **注意**：与上一轮记录的冻结指纹不同（{FROZEN_SHA256[:16]}…）——"
              "量具指纹只作留档，不阻止开跑，但结果与上一轮的可比性要在证据里说明")

    problems = preflight(drill_text)
    if problems:
        print("\n**拒绝开跑**：")
        for item in problems:
            print(f"  · {item}")
        return 2

    patched, deviation = patch_source(drill_text)
    print("\n## 偏离记账（drill 一字不改，只覆盖参数）")
    for key, value in deviation["before"].items():
        print(f"  改前 {key} = {value}")
    for key, value in deviation["after"].items():
        print(f"  改后 {key} = {value}")
    if deviation["after"]["leftover_previous"] != 0:
        print(f"  **注意**：文本里还剩 {deviation['after']['leftover_previous']} 处 "
              f"v{PREVIOUS_VERSION} 字面量——证据里的名字可能自相矛盾，逐条看一眼")

    record = {
        "wrapper": str(Path(__file__).name),
        "drill": str(DRILL),
        "drill_sha256_before": drill_sha_before,
        "frozen_sha256_expected": FROZEN_SHA256,
        "frozen_matches": drill_sha_before == FROZEN_SHA256,
        "target_version": TARGET_VERSION,
        "drill_pinned_version": PREVIOUS_VERSION,
        "deviation": deviation,
        "dry_run": dry_run,
        "started_at": stamp,
    }
    (HERE / f"drill-01-deviation-{stamp}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 跑 drill ----
    print("\n" + "=" * 78)
    print("以下输出全部来自 drill-01 本体（包装层不改它的判据、不加过滤）")
    print("=" * 78 + "\n")
    print(f"  证据名改为 {EVIDENCE_STEM}.txt / .json"
          f"（drill 自带的 OUTPUT_STEM 会与上一轮的证据互相覆盖）")
    print("  收尾由本层代做（drill 的收尾住在它跳过的那条 `__main__` 分支里）\n")

    module_name = "drill01_under_wrapper"
    spec = importlib.util.spec_from_loader(
        module_name, loader=None, origin=str(DRILL))
    module = importlib.util.module_from_spec(spec)
    # `__file__` 得显式给：drill 用它推 `HERE`（证据落点）与 `REPO`（仓库根）。
    # 少了它 drill 在模块级就 `NameError`（`Path(__file__)`），一行都跑不到。
    module.__dict__["__file__"] = str(DRILL)
    sys.modules[module_name] = module
    code = 1
    try:
        exec(compile(patched, str(DRILL), "exec"), module.__dict__)  # noqa: S102 —— 受控本地脚本
        code = int(module.main())
    except SystemExit as exc:  # drill 里若抛 SystemExit（正常路径不抛）
        code = int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 —— drill 崩了也要留原始证据
        import traceback

        print(traceback.format_exc())
        code = 1
        record["drill_exception"] = f"{type(exc).__name__}: {exc}"
    finally:
        drill_sha_after = sha256_of(DRILL)
        record["drill_sha256_after"] = drill_sha_after
        record["drill_unchanged"] = drill_sha_after == drill_sha_before
        record["exit_code"] = code

    # drill 的收尾（收 8020 / 写证据 / 总判）在它自己的 `__main__` 分支里，本层跳过了那条
    # 分支 ⇒ 必须代做一遍。漏掉它 = 演练跑完了却一份证据都不落盘（实测踩过两次）。
    if not dry_run:
        code = run_drill_cleanup(module, code)
    record["exit_code_final"] = code
    (HERE / f"drill-01-deviation-{stamp}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    print("## 包装层收尾")
    print(f"  drill 逐字节未变：{drill_sha_after == drill_sha_before}"
          f"（{drill_sha_before[:16]}…）")
    print(f"  偏离记账：drill-01-deviation-{stamp}.json")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
