r"""描边守卫轮 · 反证探针的**公共骨架**（工单 03 收口时抽出来）。

为什么要它（03 单双轴评审的两条发现）：
  · **Duplicated Code**：`probe-05` / `probe-06` 各抄了一份"注入 → 跑判据 → 复原 → 比哈希"，
    约 30 行逐字同形；
  · **复原不在 `try/finally` 里**：探针中途抛异常 / 被打断，就会把**注入态留在工作树上**
    （那棵树是 tracked 的守卫文件）；而"读数必须晚于最后一次改产品面"这条纪律，
    正是被这种就地写盘搅浑的（守卫文件 mtime 会晚于读数，虽然哈希与 HEAD 相同）。

用法：
    from probe_lib import inject_and_check, restore_guard
    failures = inject_and_check(GUARD, "名字", anchor_bytes, repl_bytes, check_fn)
"""

from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
# ⚠ `GUARD.parents` = [js, tests, 仓库根, …] —— 仓库根是 **parents[2]**，
#   写成 parents[1] 会落进 `tests/`（两支探针第一版都这么错了，前置检查当场拦下）。
assert (ROOT / "tests" / "js").is_dir(), f"仓库根算错了：{ROOT}"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inject_and_check(target: pathlib.Path, name: str, anchor: bytes, repl: bytes, check) -> int:
    """注入一处漂移 → 跑 `check()` → **无论成败都复原**。返回 0（按预期红）或 1（不符预期）。

    `check()` 要返回 `(退出码, 一句话摘要)`——退出码非 0 才算"判得红"。
    """
    original = target.read_bytes()
    if original.count(anchor) != 1:
        print(f"[跳过] {name}：锚点命中 {original.count(anchor)} 次（应为 1）")
        return 1
    try:
        target.write_bytes(original.replace(anchor, repl))
        code, note = check()
    finally:
        target.write_bytes(original)          # ← 异常 / Ctrl-C 也复原（03 评审点的那条）
    verdict = "红 ✅" if code != 0 else "**没红 ❌**"
    print(f"[{verdict}] {name}（退出码 {code}）{note}")
    return 0 if code != 0 else 1
