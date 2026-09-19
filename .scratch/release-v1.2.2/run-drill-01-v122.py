# -*- coding: utf-8 -*-
"""演练包装层：drill-01 一字不改，只在运行前覆盖它的两个**参数**（工单 `release-v1.2.2/05`）。

## 为什么要这一层，而不是直接改 drill

`drill-01-upgrade.py` 是上一轮（B1）立下的**冻结量具**：判据本体（起点/终点版本自证、
保命项、四条隔离判据、`not_in_official == 0`）一个字都不许动，谁动了谁就没法再跟上一轮
的结果比较。而它有两处**参数**是钉死在上一轮的目标版本上的：

| 位置 | 原值 | 为什么要覆盖 |
|---|---|---|
| `TARGET_VERSION` | `"1.2.1"` | 本轮目标是 v1.2.2 |
| `PACK_DIR`（`~/Desktop/firstep-pack`） | 不变 | 官方完整包清单按 `TARGET_VERSION` 拼文件名，所以它跟着一起换 |
| 日志里的字面量 `v1.2.1` / `官方 v1.2.1` | — | 留档用，必须与本轮一致，否则证据自相矛盾 |

做法（照 `.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py` 的先例）：
把 drill **当文本读进来**，只改上面那几处，`exec` 进一个独立命名空间再调 `main()`。
磁盘上那份 drill 全程不动——**跑完复核 sha256**，这就是「量具未被改动」的证据。

## 为什么必须复核 `FC`（冻结指纹）

`__name__` 得设成别的名字，否则 drill 末尾的 `if __name__ == "__main__"` 会自己跑起来
（它带 `finally` 收尾，会把我们要调的那次演练搅乱）。**注意**：`exec` 只让 `__name__`
取到假值，`__file__` 仍然会被设成 drill 的真实路径，所以 drill 里 `HERE = Path(__file__)`
推出来的证据落点、`REPO = HERE.parents[1]` 推出来的仓库根，都还是对的。

## 用法::

    python .scratch/release-v1.2.2/run-drill-01-v122.py --dry-run   # 前置核对，不下载
    python .scratch/release-v1.2.2/run-drill-01-v122.py             # 真跑（下 ~305 MB）
"""

from __future__ import annotations

import hashlib
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
    }
    patched = text.replace(
        f'TARGET_VERSION = "{PREVIOUS_VERSION}"', f'TARGET_VERSION = "{TARGET_VERSION}"', 1
    )
    # `官方 v1.2.1` 先换（它是 `v1.2.1` 的超集，顺序反了会漏掉它自己的那一处）
    patched = patched.replace(f"官方 v{PREVIOUS_VERSION}", f"官方 v{TARGET_VERSION}")
    patched = patched.replace(f"v{PREVIOUS_VERSION}", f"v{TARGET_VERSION}")
    after = {
        "target_version_constant": patched.count(f'TARGET_VERSION = "{TARGET_VERSION}"'),
        "banner_literals": patched.count(f"v{TARGET_VERSION}"),
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

    # ---- 跑 drill（同一进程，__name__ 取假值以免它自己执行 __main__ 分支）----
    print("\n" + "=" * 78)
    print("以下输出全部来自 drill-01 本体（包装层不改它的判据、不加过滤）")
    print("=" * 78 + "\n")
    namespace: dict = {"__name__": "drill01_under_wrapper", "__file__": str(DRILL)}
    code = 1
    try:
        exec(compile(patched, str(DRILL), "exec"), namespace)  # noqa: S102 —— 受控本地脚本
        code = int(namespace["main"]())
    except SystemExit as exc:  # drill 里的 raise SystemExit
        code = int(exc.code or 0)
    finally:
        drill_sha_after = sha256_of(DRILL)
        record["drill_sha256_after"] = drill_sha_after
        record["drill_unchanged"] = drill_sha_after == drill_sha_before
        record["exit_code"] = code
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
